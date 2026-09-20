"""Measure recording and reporting costs; run with ``uv run python benchmarks/overhead.py``.

Use the same interpreter, machine, iteration count, and repeat count for comparisons.
Results are medians in nanoseconds per operation; they are not CI pass/fail thresholds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import platform
import statistics
import time
import timeit
from collections.abc import Callable

from execution_timer import (
    TimerContext,
    clear_execution_timings,
    get_execution_times_json,
    get_total_time,
    log_execution_times,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--number", type=int, default=100_000)
    _ = parser.add_argument("--repeat", type=int, default=7)
    args = parser.parse_args()
    number = int(args.number)
    repeat = int(args.repeat)
    if number < 1 or repeat < 1:
        parser.error("--number and --repeat must be positive")

    results: dict[str, float] = {}

    def measure(name: str, operation: Callable[[], object], count: int = number) -> None:
        clear_execution_timings()
        results[name] = statistics.median(timeit.repeat(operation, number=count, repeat=repeat)) * 1e9 / count

    def plain() -> None:
        pass

    def context() -> None:
        with TimerContext("section"):
            pass

    shared = TimerContext("section")

    def reused_context() -> None:
        with shared:
            pass

    @TimerContext("section")
    def decorated() -> None:
        pass

    def nested() -> None:
        with shared, shared, shared, shared, shared:
            pass

    measure("plain_call", plain)
    measure("new_context", context)
    measure("reused_context", reused_context)
    measure("decorated_call", decorated)
    measure("five_nested_contexts", nested)

    async def plain_async() -> None:
        pass

    decorated_async = TimerContext("async_section")(plain_async)

    async def measure_async() -> None:
        for name, function in (("plain_await", plain_async), ("decorated_await", decorated_async)):
            samples: list[float] = []
            for _ in range(repeat):
                clear_execution_timings()
                started = time.perf_counter()
                for _ in range(number):
                    await function()
                samples.append((time.perf_counter() - started) * 1e9 / number)
            results[name] = statistics.median(samples)

    asyncio.run(measure_async())

    clear_execution_timings()
    for index in range(1_000):
        with TimerContext("section", category=f"category{index % 10}", counter=index):
            pass
    quiet_logger = logging.getLogger("executiontimer.benchmark")
    quiet_logger.setLevel(logging.WARNING)
    reporting_count = max(1, number // 1_000)
    for name, operation in (
        ("total_1000_sections", get_total_time),
        ("json_1000_sections", get_execution_times_json),
        ("disabled_logging_1000_sections", lambda: log_execution_times(logger=quiet_logger)),
    ):
        results[name] = (
            statistics.median(timeit.repeat(operation, number=reporting_count, repeat=repeat)) * 1e9 / reporting_count
        )

    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "number": number,
                "repeat": repeat,
                "nanoseconds_per_operation": {name: round(value, 1) for name, value in results.items()},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
