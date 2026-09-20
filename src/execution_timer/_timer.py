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

_LOGGER: Final = logging.getLogger(__name__)


class TimingReport(TypedDict):
    """Timing entry for one section: elapsed seconds and its category."""

    time: float
    category: str


class SectionRecord(TypedDict):
    """One section in the JSON export."""

    name: str
    path: list[str]
    time: float
    category: str


class TimingsPayload(TypedDict):
    """Top-level JSON export payload."""

    total_time: float
    total_category_time: dict[str, float]
    sections: list[SectionRecord]


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


def _ordered_by_hierarchy(keys: Iterable[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Order section paths depth-first so children always follow their parent.

    Insertion order is preserved within each level, so a parent revisited after an unrelated
    sibling still renders with its own children rather than beneath the sibling.
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

    ordered: list[tuple[str, ...]] = []
    # Explicit stack rather than recursion: nesting depth is user-controlled.
    stack = list(reversed(roots))
    while stack:
        key = stack.pop()
        ordered.append(key)
        stack.extend(reversed(children.get(key, [])))
    return ordered


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
        """Stop timing a section and accumulate its elapsed time."""
        end_time = time.perf_counter()
        frame = _ACTIVE_CONTEXT.get()
        if frame is None:
            return
        if frame.path[-1] != name:
            raise RuntimeError(f"Cannot stop '{name}' while '{frame.path[-1]}' is active.")
        with self._lock:
            # A clear detaches this entry from the registry. Updating the detached object
            # cannot resurrect an old sample or add it to a replacement at the same path.
            frame.entry["elapsed_time"] += end_time - frame.start_time
        _ = _ACTIVE_CONTEXT.set(frame.parent)

    def _resolve(self, *, flatten: bool) -> dict[tuple[str, ...], _TimesDict]:
        snapshot = self.snapshot()
        return _flatten(snapshot) if flatten else snapshot

    def report_timings(self, *, flatten: bool = True) -> str:
        """Build a report of all sections with duration and percentage of total time."""
        timings = self._resolve(flatten=flatten)
        if not timings:
            _LOGGER.warning("No timings to report.")
            return ""

        total_time = sum(info["elapsed_time"] for key, info in timings.items() if len(key) == 1)
        report = [f"\nTotal calculation time: {total_time:.4f} s.\n"]
        for key in _ordered_by_hierarchy(timings):
            elapsed_time = timings[key]["elapsed_time"]
            percentage = (elapsed_time / total_time) * 100 if total_time else 0.0
            report.append(f"{'..  ' * (len(key) - 1)}{key[-1]}: {elapsed_time:.4f} s ({percentage:.2f}%)")
        return "\n".join(report)

    def compute_total_time(self, *, flatten: bool = True) -> float:
        """Compute total elapsed time across all top-level sections."""
        # Counter merging cannot change the sum. Avoid allocating and flattening a snapshot.
        _ = flatten
        with self._lock:
            return sum((info["elapsed_time"] for key, info in self.timings.items() if len(key) == 1), 0.0)

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
    """Context manager and decorator for timing a named section of code."""

    def __init__(self, name: str, category: str = DEFAULT_CATEGORY, counter: int | None = None) -> None:
        self.name: str = _build_name_with_counter(name, counter)
        self.category: str = category
        self.timer: _ExecutionTimer = _TIMER

    def __enter__(self) -> TimerContext:
        self.timer.start_timer(self.name, self.category)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.timer.stop_timer(self.name)

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorate a function to time its execution under this context.

        Coroutine functions are wrapped so the timing spans the entire ``await``, not just
        creation of the coroutine object.
        """
        if inspect.iscoroutinefunction(func):
            # ``iscoroutinefunction`` narrows nothing useful for the type checker, so bridge
            # through an explicitly typed helper instead of leaking ``Any`` into the signature.
            async_func = cast("Callable[P, Coroutine[object, object, object]]", func)
            return cast("Callable[P, R]", self._wrap_async(async_func))

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with self:
                return func(*args, **kwargs)

        return wrapper

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
    """Get a formatted report of all recorded sections; flatten counters if requested."""
    return _TIMER.report_timings(flatten=flatten)


def log_execution_times(*, flatten: bool = True, logger: logging.Logger | None = None) -> None:
    """Log the execution-times report at INFO level; flatten counters if requested."""
    target = logger if logger is not None else _LOGGER
    if target.isEnabledFor(logging.INFO):
        target.info(get_execution_times_report(flatten=flatten))


def get_execution_timings(*, flatten: bool = True) -> dict[tuple[str, ...], TimingReport]:
    """Get elapsed seconds and category for every recorded section; flatten counters if requested."""
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
        for key in _ordered_by_hierarchy(timings)
    ]
    category_totals: dict[str, float] = {}
    for key, info in snapshot.items():
        category = info["category"]
        if not _has_ancestor_with_category(snapshot, key, category):
            category_totals[category] = category_totals.get(category, 0.0) + info["elapsed_time"]
    return {
        "total_time": round(sum((info["elapsed_time"] for key, info in snapshot.items() if len(key) == 1), 0.0), 6),
        "total_category_time": {cat: round(category_totals[cat], 6) for cat in sorted(category_totals)},
        "sections": sections,
    }


def get_execution_times_json(*, flatten: bool = True, indent: int | None = 2) -> str:
    """Get all timings as a JSON string (LLM-friendly); flatten counters if requested."""
    return json.dumps(_build_payload(flatten=flatten), indent=indent)


def save_execution_timings_json(path: str | Path, *, flatten: bool = True, indent: int | None = 2) -> Path:
    """Write all timings to a JSON file and return its path; flatten counters if requested."""
    out = Path(path)
    _ = out.write_text(get_execution_times_json(flatten=flatten, indent=indent) + "\n", encoding="utf-8")
    return out


def get_total_time(*, flatten: bool = True) -> float:
    """Get total elapsed seconds across all top-level sections."""
    return _TIMER.compute_total_time(flatten=flatten)


def get_total_category_time(category: str) -> float:
    """Get total elapsed seconds in a category, counting only top-most entries of that category."""
    return _TIMER.compute_total_category_time(category)


def clear_execution_timings() -> None:
    """Reset all recorded timings."""
    _TIMER.clear()


def register_forbidden_nesting(outer: str, inner: str) -> None:
    """Forbid timing sections of category ``inner`` directly inside sections of category ``outer``."""
    _TIMER.register_forbidden_nesting(outer, inner)


def clear_forbidden_nesting() -> None:
    """Remove all forbidden-nesting rules."""
    _TIMER.clear_forbidden_nesting()
