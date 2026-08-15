"""Hierarchical execution timing with user-defined categories."""

from execution_timer._timer import (
    DEFAULT_CATEGORY,
    TimerContext,
    TimingReport,
    clear_execution_timings,
    clear_forbidden_nesting,
    get_execution_times_report,
    get_execution_timings,
    get_total_category_time,
    get_total_time,
    register_forbidden_nesting,
)

__all__ = [
    "DEFAULT_CATEGORY",
    "TimerContext",
    "TimingReport",
    "clear_execution_timings",
    "clear_forbidden_nesting",
    "get_execution_times_report",
    "get_execution_timings",
    "get_total_category_time",
    "get_total_time",
    "register_forbidden_nesting",
]
