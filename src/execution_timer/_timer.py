"""Hierarchical execution timing with user-defined categories.

Timings are stored in a process-wide registry guarded by a lock. The active-context stack
lives in a :class:`~contextvars.ContextVar`, so it is isolated per thread *and* per asyncio
task: sections recorded concurrently nest independently and merge into one report.
Overlapping calls to the same section accumulate their individual durations.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import threading
import time
import warnings
from collections.abc import Callable, Coroutine, Iterable, Iterator
from contextvars import ContextVar
from itertools import count
from pathlib import Path
from types import TracebackType
from typing import Final, NamedTuple, ParamSpec, TypedDict, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")

DEFAULT_CATEGORY: Final = "default"
"""The category of sections created without one."""

_LOGGER: Final = logging.getLogger(__name__)


class TimingReport(TypedDict):
    """Timing entry for one section, as returned by :func:`get_execution_timings`."""

    time: float
    """Accumulated elapsed seconds."""
    category: str
    """The section's category."""


class SectionRecord(TypedDict):
    """One section in the JSON export, see :class:`TimingsPayload`."""

    name: str
    """The section's own name, the last element of :attr:`path`."""
    path: list[str]
    """Names from the top-level section down to this one."""
    time: float
    """Accumulated elapsed seconds, rounded to microseconds."""
    category: str
    """The section's category."""


class TimingsPayload(TypedDict):
    """Top-level object of the JSON export from :func:`get_execution_times_json`."""

    total_time: float
    """Seconds across all top-level sections, as returned by :func:`get_total_time`."""
    total_category_time: dict[str, float]
    """Seconds per category, counting only the top-most section of each category."""
    sections: list[SectionRecord]
    """Every section, ordered depth-first so children follow their parent."""


class _TimesDict(TypedDict):
    sequence: int
    elapsed_time: float
    category: str


class _Frame(NamedTuple):
    """Per-invocation state, with a cached path and an immutable parent link."""

    path: tuple[str, ...]
    category: str
    start_time: float
    entry: _TimesDict
    parent: _Frame | None


_ACTIVE_CONTEXT: ContextVar[_Frame | None] = ContextVar("execution_timer_context", default=None)


def _ordered_by_hierarchy(keys: Iterable[tuple[str, ...]]) -> list[tuple[tuple[str, ...], int]]:
    """Order section paths depth-first so children always follow their parent.

    Returns each path with its depth in the recorded tree, which is shallower than the path
    length when an ancestor is missing. Insertion order is preserved within each level, so a
    parent revisited after an unrelated sibling still renders with its own children rather
    than beneath the sibling.
    """
    keys = list(keys)
    known = set(keys)
    children: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    roots: list[tuple[str, ...]] = []
    for key in keys:
        parent = key[:-1]
        # Treat a section whose parent was never recorded as a root so it cannot be dropped.
        if parent and parent in known:
            children.setdefault(parent, []).append(key)
        else:
            roots.append(key)

    ordered: list[tuple[tuple[str, ...], int]] = []
    # Explicit stack rather than recursion: nesting depth is user-controlled.
    stack = [(key, 0) for key in reversed(roots)]
    while stack:
        key, depth = stack.pop()
        ordered.append((key, depth))
        stack.extend((child, depth + 1) for child in reversed(children.get(key, [])))
    return ordered


def _top_level_time(timings: dict[tuple[str, ...], _TimesDict]) -> float:
    """Sum the sections with no recorded parent, matching the roots of ``_ordered_by_hierarchy``.

    A parent goes missing when timings are cleared while it is active; its children that
    finish afterwards are then top-level and must count toward the total.
    """
    return sum(
        (info["elapsed_time"] for key, info in timings.items() if len(key) == 1 or key[:-1] not in timings),
        0.0,
    )


class _ExecutionTimer:
    """Registry of named, nestable timing sections, shared through ``_TIMER``."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self.timings: dict[tuple[str, ...], _TimesDict] = {}
        self.forbidden_nesting: set[tuple[str, str]] = set()
        self._sequence: Iterator[int] = count()

    def snapshot(self) -> dict[tuple[str, ...], _TimesDict]:
        """Copy the registry under the lock so readers never iterate a mutating dict."""
        with self._lock:
            return {key: info.copy() for key, info in self.timings.items()}

    def start_timer(self, name: str, category: str) -> None:
        """Start timing a section under the given name within the active context."""
        parent = _ACTIVE_CONTEXT.get()
        full_name = (*parent.path, name) if parent is not None else (name,)
        with self._lock:
            if parent is not None and (parent.category, category) in self.forbidden_nesting:
                msg = f"Category '{category}' is not allowed inside category '{parent.category}'."
                raise ValueError(msg)
            sequence = next(self._sequence)
            entry: _TimesDict | None = self.timings.get(full_name)
            if entry is None:
                entry = {"sequence": sequence, "elapsed_time": 0.0, "category": category}
                self.timings[full_name] = entry
            else:
                entry["sequence"] = sequence
                entry["category"] = category
        _ = _ACTIVE_CONTEXT.set(_Frame(full_name, category, time.perf_counter(), entry, parent))

    def stop_timer(self, name: str) -> None:
        """Stop timing a section and accumulate its elapsed time.

        Never raises, unless warnings are configured as errors: an exception here would replace
        one already propagating from the timed block. Exiting past still-active inner sections
        (typically a suspended generator that holds one open) discards them with a warning,
        after recording the exit, so the stack cannot stay corrupted.
        Exiting a section that is no longer active, such as one discarded that way when its
        generator is finally closed, does nothing.
        """
        end_time = time.perf_counter()
        active = _ACTIVE_CONTEXT.get()
        frame = active
        while frame is not None and frame.path[-1] != name:
            frame = frame.parent
        if frame is None:
            return
        with self._lock:
            # A clear detaches this entry from the registry. Updating the detached object
            # cannot resurrect an old sample or add it to a replacement at the same path.
            frame.entry["elapsed_time"] += end_time - frame.start_time
        _ = _ACTIVE_CONTEXT.set(frame.parent)
        if frame is not active and active is not None:
            # Warn only once the state is consistent: warnings configured as errors raise here.
            msg = (
                f"Section '{name}' exited while '{active.path[-1]}' was still active; discarding the "
                "unfinished inner sections. Close sections before a generator yields."
            )
            warnings.warn(msg, RuntimeWarning, stacklevel=3)

    def _resolve(self, *, flatten: bool) -> dict[tuple[str, ...], _TimesDict]:
        snapshot = self.snapshot()
        return _flatten(snapshot) if flatten else snapshot

    def report_timings(self, *, flatten: bool = True) -> str:
        """Build a report of all sections with duration and percentage of total time."""
        snapshot = self.snapshot()
        if not snapshot:
            return ""

        # Total the unflattened paths, like get_total_time and the JSON export.
        total_time = _top_level_time(snapshot)
        timings = _flatten(snapshot) if flatten else snapshot
        report = [f"Total time: {total_time:.4f} s.\n"]
        for key, depth in _ordered_by_hierarchy(timings):
            elapsed_time = timings[key]["elapsed_time"]
            percentage = (elapsed_time / total_time) * 100 if total_time else 0.0
            report.append(f"{'..  ' * depth}{key[-1]}: {elapsed_time:.4f} s ({percentage:.2f}%)")
        return "\n".join(report)

    def compute_total_time(self) -> float:
        """Compute total elapsed time across all top-level sections."""
        # Counter merging cannot change the sum, so there is no snapshot to copy or flatten.
        with self._lock:
            return _top_level_time(self.timings)

    def compute_total_category_time(self, category: str) -> float:
        """Compute total elapsed time in a category, counting only top-most entries of that category."""
        timings = self.snapshot()
        total_time = 0.0
        for key, info in timings.items():
            if info["category"] != category or _has_ancestor_with_category(timings, key, category):
                continue
            total_time += info["elapsed_time"]
        return total_time

    def get_execution_timings(self, *, flatten: bool = True) -> dict[tuple[str, ...], TimingReport]:
        """Return elapsed seconds and category for every recorded section."""
        timings = self._resolve(flatten=flatten)
        return {key: {"time": info["elapsed_time"], "category": info["category"]} for key, info in timings.items()}

    def clear(self) -> None:
        """Drop every recorded section."""
        with self._lock:
            self.timings.clear()

    def register_forbidden_nesting(self, outer: str, inner: str) -> None:
        with self._lock:
            self.forbidden_nesting.add((outer, inner))

    def clear_forbidden_nesting(self) -> None:
        with self._lock:
            self.forbidden_nesting.clear()


_TIMER: Final = _ExecutionTimer()


def _flatten(timings: dict[tuple[str, ...], _TimesDict]) -> dict[tuple[str, ...], _TimesDict]:
    flat_map: dict[tuple[str, ...], _TimesDict] = {}
    for key, info in timings.items():
        flat_key = tuple(_basic_name_without_counter(part) for part in key)
        existing = flat_map.get(flat_key)
        if existing is None:
            flat_map[flat_key] = info.copy()
        else:
            existing["elapsed_time"] += info["elapsed_time"]
            if info["sequence"] > existing["sequence"]:
                existing["category"] = info["category"]
                existing["sequence"] = info["sequence"]
    return flat_map


def _has_ancestor_with_category(
    timings: dict[tuple[str, ...], _TimesDict], key: tuple[str, ...], category: str
) -> bool:
    return any(key[:i] in timings and timings[key[:i]]["category"] == category for i in range(1, len(key)))


class TimerContext:
    """Context manager and decorator for timing a named section of code.

    Sections entered inside another section are recorded beneath it, so nesting ``with``
    blocks or decorated calls builds the hierarchy shown in reports. Repeated entries of the
    same section accumulate their durations. A context can be reused, re-entered while it is
    active, and shared between threads and asyncio tasks.

    Args:
        name: The section's name within its parent.
        category: Any string used to group sections, for example ``"io"`` or ``"gpu"``.
        counter: Records the section as ``name[counter]``, typically a loop index. Reports
            merge these variants unless you pass ``flatten=False``.

    Raises:
        ValueError: On entry, if a rule from :func:`register_forbidden_nesting` forbids this
            category directly inside the enclosing section's category.

    Example:
        .. code-block:: python

            with TimerContext("load", category="io"):
                data = load()

            @TimerContext("solve")
            def solve(data): ...
    """

    def __init__(self, name: str, category: str = DEFAULT_CATEGORY, counter: int | None = None) -> None:
        self.name: str = _build_name_with_counter(name, counter)
        self.category: str = category
        self._timer: _ExecutionTimer = _TIMER

    def __enter__(self) -> TimerContext:
        self._timer.start_timer(self.name, self.category)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self._timer.stop_timer(self.name)

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorate a function to time its execution under this context.

        Coroutine functions are wrapped so the timing spans the entire ``await``, not just
        creation of the coroutine object. So is a coroutine returned by a plain function,
        typically another decorator stacked on an ``async def``.

        Raises:
            TypeError: If ``func`` is a generator or async generator function. A wrapper
                would time only creation of the generator object, not its iteration.
        """
        if inspect.isgeneratorfunction(func) or inspect.isasyncgenfunction(func):
            msg = (
                f"Cannot decorate generator function {func.__qualname__!r}: only creating the generator "
                "would be timed. Time the loop that consumes it, or its body between yields, with a "
                "'with TimerContext(...)' block instead."
            )
            raise TypeError(msg)
        if inspect.iscoroutinefunction(func):
            # ``iscoroutinefunction`` narrows nothing useful for the type checker, so bridge
            # through an explicitly typed helper instead of leaking ``Any`` into the signature.
            async_func = cast("Callable[P, Coroutine[object, object, object]]", func)
            return cast("Callable[P, R]", self._wrap_async(async_func))

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with self:
                result = func(*args, **kwargs)
            if inspect.iscoroutine(result):
                # A decorator between this one and an ``async def`` hides the coroutine function,
                # so the call above only created the coroutine. Time awaiting it as well.
                return cast("R", self._time_await(result))
            return result

        return wrapper

    async def _time_await(self, coroutine: Coroutine[object, object, T]) -> T:
        """Await a coroutine that was created outside this context, timing the whole await."""
        with self:
            return await coroutine

    def _wrap_async(self, func: Callable[P, Coroutine[object, object, T]]) -> Callable[P, Coroutine[object, object, T]]:
        """Wrap a coroutine function so the timing spans the whole await."""

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            with self:
                return await func(*args, **kwargs)

        return async_wrapper


def _build_name_with_counter(name: str, counter: int | None = None) -> str:
    """Append ``[counter]`` to a section name if a counter is provided."""
    if counter is None:
        return name
    return f"{name}[{counter}]"


def _basic_name_without_counter(name: str) -> str:
    """Strip a trailing ``[counter]`` from a section name if present."""
    if "[" in name and name.endswith("]"):
        prefix, _, suffix = name.rpartition("[")
        digits = suffix[:-1].removeprefix("-")
        if digits.isascii() and digits.isdecimal():
            return prefix
    return name


def get_execution_times_report(*, flatten: bool = True) -> str:
    """Get a formatted, indented report of all recorded sections.

    Each line shows a section's accumulated seconds and its share of the total time.
    Indentation reflects nesting.

    Args:
        flatten: Merge ``counter`` variants such as ``step[0]`` and ``step[1]`` into ``step``.

    Returns:
        The report, or ``""`` if nothing has been recorded.
    """
    return _TIMER.report_timings(flatten=flatten)


def log_execution_times(*, flatten: bool = True, logger: logging.Logger | None = None) -> None:
    """Log the report from :func:`get_execution_times_report` at ``INFO`` level.

    Logs a warning instead if nothing has been recorded. Does nothing, and skips building
    the report, if the logger has ``INFO`` disabled.

    Args:
        flatten: Merge ``counter`` variants of a section.
        logger: The logger to use. Defaults to the ``execution_timer._timer`` logger.
    """
    target = logger if logger is not None else _LOGGER
    if target.isEnabledFor(logging.INFO):
        report = get_execution_times_report(flatten=flatten)
        if report:
            # Start the multi-line report on its own line, after the log record's prefix.
            target.info("\n%s", report)
        else:
            target.warning("No timings to report.")


def get_execution_timings(*, flatten: bool = True) -> dict[tuple[str, ...], TimingReport]:
    """Get elapsed seconds and category for every recorded section.

    Args:
        flatten: Merge ``counter`` variants of a section.

    Returns:
        A new dictionary keyed by section path, such as ``("solve", "step")``. Changing it
        does not affect the recorded timings.
    """
    return _TIMER.get_execution_timings(flatten=flatten)


def _build_payload(*, flatten: bool = True) -> TimingsPayload:
    """Build a JSON-serializable snapshot of all timings, including totals and per-category sums."""
    snapshot = _TIMER.snapshot()
    timings = _flatten(snapshot) if flatten else snapshot
    sections: list[SectionRecord] = [
        {
            "name": key[-1],
            "path": list(key),
            "time": round(timings[key]["elapsed_time"], 6),
            "category": timings[key]["category"],
        }
        for key, _ in _ordered_by_hierarchy(timings)
    ]
    category_totals: dict[str, float] = {}
    for key, info in snapshot.items():
        category = info["category"]
        if not _has_ancestor_with_category(snapshot, key, category):
            category_totals[category] = category_totals.get(category, 0.0) + info["elapsed_time"]
    return {
        "total_time": round(_top_level_time(snapshot), 6),
        "total_category_time": {cat: round(category_totals[cat], 6) for cat in sorted(category_totals)},
        "sections": sections,
    }


def get_execution_times_json(*, flatten: bool = True, indent: int | None = 2) -> str:
    """Get all timings as a JSON document shaped like :class:`TimingsPayload`.

    Args:
        flatten: Merge ``counter`` variants of a section.
        indent: Passed to :func:`json.dumps`; ``None`` gives the most compact output.

    Returns:
        The JSON text.
    """
    return json.dumps(_build_payload(flatten=flatten), indent=indent)


def save_execution_timings_json(path: str | Path, *, flatten: bool = True, indent: int | None = 2) -> Path:
    """Write the JSON from :func:`get_execution_times_json` to a UTF-8 file.

    Args:
        path: The file to write, replacing it if it exists. Its directory must exist.
        flatten: Merge ``counter`` variants of a section.
        indent: Passed to :func:`json.dumps`.

    Returns:
        The path written to.
    """
    out = Path(path)
    _ = out.write_text(get_execution_times_json(flatten=flatten, indent=indent) + "\n", encoding="utf-8")
    return out


def get_total_time() -> float:
    """Get total elapsed seconds across all top-level sections.

    Nested sections are part of their parent's time, so they are not added again.

    Returns:
        The total, or ``0.0`` if nothing has been recorded.
    """
    return _TIMER.compute_total_time()


def get_total_category_time(category: str) -> float:
    """Get total elapsed seconds in a category.

    Only the top-most section of the category counts: a section nested inside another of
    the same category is part of that section's time and is not added again.

    Args:
        category: The category to total.

    Returns:
        The total, or ``0.0`` for a category with no sections.
    """
    return _TIMER.compute_total_category_time(category)


def clear_execution_timings() -> None:
    """Discard all recorded timings.

    A section that is active during the clear is not recorded when it exits. Sections
    started inside it afterwards are recorded as top-level sections. Nesting rules are kept;
    see :func:`clear_forbidden_nesting`.
    """
    _TIMER.clear()


def register_forbidden_nesting(outer: str, inner: str) -> None:
    """Forbid sections of category ``inner`` directly inside sections of category ``outer``.

    Entering such a section raises :class:`ValueError`. Only the direct parent is checked.

    Args:
        outer: The enclosing section's category.
        inner: The category that may not appear directly inside it.
    """
    _TIMER.register_forbidden_nesting(outer, inner)


def clear_forbidden_nesting() -> None:
    """Remove all forbidden-nesting rules."""
    _TIMER.clear_forbidden_nesting()
