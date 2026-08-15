"""Hierarchical execution timing with user-defined categories."""

from execution_timer._timer import (
    DEFAULT_CATEGORY,
    SectionRecord,
    TimerContext,
    TimingReport,
    TimingsPayload,
    clear_execution_timings,
    clear_forbidden_nesting,
    get_execution_times_json,
    get_execution_times_report,
    get_execution_timings,
    get_total_category_time,
    get_total_time,
    log_execution_times,
    register_forbidden_nesting,
    save_execution_timings_json,
)

__all__ = [
    "DEFAULT_CATEGORY",
    "SectionRecord",
    "TimerContext",
    "TimingReport",
    "TimingsPayload",
    "clear_execution_timings",
    "clear_forbidden_nesting",
    "get_execution_times_json",
    "get_execution_times_report",
    "get_execution_timings",
    "get_total_category_time",
    "get_total_time",
    "log_execution_times",
    "register_forbidden_nesting",
    "save_execution_timings_json",
]
