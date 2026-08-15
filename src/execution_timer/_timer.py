"""Hierarchical execution timing with user-defined categories.

Timings are stored in a process-wide registry. The active-context stack is thread-local,
so sections recorded concurrently on different threads nest independently and merge into
one report. Recording the *same* section path from overlapping threads is not meaningful.
"""

from __future__ import annotations

import functools
import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Final, ParamSpec, TypedDict, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_CATEGORY: Final = "default"


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
    start_time: float
    elapsed_time: float
    category: str


class _ExecutionTimer:
    """Singleton registry of named, nestable timing sections."""

    _instance: ClassVar[_ExecutionTimer | None] = None
    timings: ClassVar[dict[tuple[str, ...], _TimesDict]] = {}
    forbidden_nesting: ClassVar[set[tuple[str, str]]] = set()

    _local: threading.local
    _lock: threading.Lock

    def __new__(cls) -> _ExecutionTimer:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # __init__ runs on every call, so initialize per-instance state only once.
        if not hasattr(self, "_local"):
            self._local = threading.local()
            self._lock = threading.Lock()

    @property
    def _context(self) -> list[str]:
        if not hasattr(self._local, "context"):
            self._local.context = []
        return cast(list[str], self._local.context)

    @property
    def _categories(self) -> list[str]:
        if not hasattr(self._local, "categories"):
            self._local.categories = []
        return cast(list[str], self._local.categories)

    @property
    def _full_name(self) -> tuple[str, ...]:
        return tuple(self._context)

    def start_timer(self, name: str, category: str) -> None:
        """Start timing a section under the given name within the active context."""
        self._add_context(name, category)
        full_name = self._full_name
        start_time = time.perf_counter()
        with self._lock:
            if full_name not in self.timings:
                self.timings[full_name] = {"start_time": start_time, "elapsed_time": 0.0, "category": category}
            else:
                entry = self.timings[full_name]
                entry["start_time"] = start_time
                entry["category"] = category

    def stop_timer(self, name: str) -> None:
        """Stop timing a section and accumulate its elapsed time."""
        end_time = time.perf_counter()
        full_name = self._full_name
        with self._lock:
            self.timings[full_name]["elapsed_time"] += end_time - self.timings[full_name]["start_time"]
        self._remove_context(name)

    def _add_context(self, name: str, category: str) -> None:
        if self._categories and (self._categories[-1], category) in self.forbidden_nesting:
            msg = f"Category '{category}' is not allowed inside category '{self._categories[-1]}'."
            raise ValueError(msg)
        self._context.append(name)
        self._categories.append(category)

    def _remove_context(self, name: str) -> None:
        """Pop the innermost context, restoring the stack to its state before ``name`` was entered."""
        context = self._context
        if not context:
            return
        # Pop through the matching frame so a mismatched or out-of-order exit cannot corrupt the stack.
        while context:
            popped = context.pop()
            del self._categories[-1]
            if popped == name:
                break

    def compute_flattened_timings(self) -> dict[tuple[str, ...], _TimesDict]:
        """Aggregate elapsed times with counter suffixes removed from section names.

        When counter variants of one section are merged, elapsed times are summed and the
        most recently recorded category is kept.
        """
        flat_map: dict[tuple[str, ...], _TimesDict] = {}
        for key, info in self.timings.items():
            flat_key = tuple(_basic_name_without_counter(part) for part in key)
            if flat_key in flat_map:
                existing = flat_map[flat_key]
                existing["elapsed_time"] += info["elapsed_time"]
                existing["category"] = info["category"]
            else:
                flat_map[flat_key] = info.copy()
        return flat_map

    def report_timings(self, *, flatten: bool = True) -> str:
        """Build a report of all sections with duration and percentage of total time."""
        timings = self.compute_flattened_timings() if flatten else self.timings

        total_time = self.compute_total_time(flatten=flatten)
        if not total_time:
            logging.warning("No timings to report.")
            return ""

        report = [f"\nTotal calculation time: {total_time:.4f} s.\n"]
        for key, info in timings.items():
            elapsed_time = info["elapsed_time"]
            percentage = (elapsed_time / total_time) * 100
            report.append(f"{'..  ' * (len(key) - 1)}{key[-1]}: {elapsed_time:.4f} s ({percentage:.2f}%)")
        return "\n".join(report)

    def compute_total_time(self, *, flatten: bool = True) -> float:
        """Compute total elapsed time across all top-level sections."""
        timings = self.compute_flattened_timings() if flatten else self.timings
        return sum(info["elapsed_time"] for key, info in timings.items() if len(key) == 1)

    def compute_total_category_time(self, category: str) -> float:
        """Compute total elapsed time in a category, counting only top-most entries of that category."""
        total_time = 0.0
        for key, info in self.timings.items():
            if info["category"] != category or self._has_ancestor_with_category(key, category):
                continue
            total_time += info["elapsed_time"]
        return total_time

    def _has_ancestor_with_category(self, key: tuple[str, ...], category: str) -> bool:
        return any(
            key[:i] in self.timings and self.timings[key[:i]]["category"] == category for i in range(1, len(key))
        )

    def get_execution_timings(self, *, flatten: bool = True) -> dict[tuple[str, ...], TimingReport]:
        """Return elapsed seconds and category for every recorded section."""
        timings = self.compute_flattened_timings() if flatten else self.timings
        return {key: {"time": info["elapsed_time"], "category": info["category"]} for key, info in timings.items()}


class TimerContext:
    """Context manager and decorator for timing a named section of code."""

    def __init__(self, name: str, category: str = DEFAULT_CATEGORY, counter: int | None = None) -> None:
        self.name: str = _build_name_with_counter(name, counter)
        self.category: str = category
        self.timer: _ExecutionTimer = _ExecutionTimer()

    def __enter__(self) -> None:
        self.timer.start_timer(self.name, self.category)

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.timer.stop_timer(self.name)

    def __call__(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorate a function to time its execution under this context."""

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with TimerContext(self.name, self.category):
                return func(*args, **kwargs)

        return wrapper


def _build_name_with_counter(name: str, counter: int | None = None) -> str:
    """Append ``[counter]`` to a section name if a counter is provided."""
    if counter is None:
        return name
    return f"{name}[{counter}]"


def _basic_name_without_counter(name: str) -> str:
    """Strip a trailing ``[counter]`` from a section name if present."""
    if "[" in name and name.endswith("]"):
        return name[: name.rfind("[")]
    return name


def get_execution_times_report(*, flatten: bool = True) -> str:
    """Get a formatted report of all recorded sections; flatten counters if requested."""
    return _ExecutionTimer().report_timings(flatten=flatten)


def log_execution_times(*, flatten: bool = True, logger: logging.Logger | None = None) -> None:
    """Log the execution-times report at INFO level; flatten counters if requested."""
    (logger or logging.getLogger(__name__)).info(get_execution_times_report(flatten=flatten))


def get_execution_timings(*, flatten: bool = True) -> dict[tuple[str, ...], TimingReport]:
    """Get elapsed seconds and category for every recorded section; flatten counters if requested."""
    return _ExecutionTimer().get_execution_timings(flatten=flatten)


def _build_payload(*, flatten: bool = True) -> TimingsPayload:
    """Build a JSON-serializable snapshot of all timings, including totals and per-category sums."""
    timer = _ExecutionTimer()
    timings = timer.get_execution_timings(flatten=flatten)
    sections: list[SectionRecord] = [
        {"name": key[-1], "path": list(key), "time": round(info["time"], 6), "category": info["category"]}
        for key, info in timings.items()
    ]
    categories = sorted({info["category"] for info in timings.values()})
    return {
        "total_time": round(timer.compute_total_time(flatten=flatten), 6),
        "total_category_time": {cat: round(timer.compute_total_category_time(cat), 6) for cat in categories},
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
    return _ExecutionTimer().compute_total_time(flatten=flatten)


def get_total_category_time(category: str) -> float:
    """Get total elapsed seconds in a category, counting only top-most entries of that category."""
    return _ExecutionTimer().compute_total_category_time(category)


def clear_execution_timings() -> None:
    """Reset all recorded timings."""
    _ExecutionTimer.timings = {}


def register_forbidden_nesting(outer: str, inner: str) -> None:
    """Forbid timing sections of category ``inner`` directly inside sections of category ``outer``."""
    _ExecutionTimer.forbidden_nesting.add((outer, inner))


def clear_forbidden_nesting() -> None:
    """Remove all forbidden-nesting rules."""
    _ExecutionTimer.forbidden_nesting = set()
