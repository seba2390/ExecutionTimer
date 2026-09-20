"""Tests for the execution timer, using only the public API."""

import asyncio
import builtins
import inspect
import json
import logging
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from execution_timer import (
    DEFAULT_CATEGORY,
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


@pytest.fixture(autouse=True)
def reset_timer() -> Iterator[None]:
    clear_execution_timings()
    clear_forbidden_nesting()
    yield


def raw_timings() -> dict[tuple[str, ...], TimingReport]:
    return get_execution_timings(flatten=False)


class TestSingleAndNestedContexts:
    def test_single_context(self) -> None:
        with TimerContext("test_single"):
            pass

        timings = raw_timings()
        assert ("test_single",) in timings
        assert timings["test_single",]["time"] >= 0

    def test_multiple_contexts(self) -> None:
        with TimerContext("context1"):
            pass
        with TimerContext("context2"):
            pass

        timings = raw_timings()
        assert ("context1",) in timings
        assert ("context2",) in timings

    def test_nested_context(self) -> None:
        with TimerContext("root"):
            time.sleep(0.01)
            with TimerContext("nested"):
                time.sleep(0.001)
            with TimerContext("another_nested"):
                time.sleep(0.0001)

        with TimerContext("another_root"):
            time.sleep(0.011)

        timings = raw_timings()
        assert ("root",) in timings
        assert ("root", "nested") in timings
        assert ("root", "another_nested") in timings
        assert ("another_root",) in timings

        assert timings["root",]["time"] > 0
        assert timings["root", "nested"]["time"] < timings["root",]["time"]
        assert timings["root", "another_nested"]["time"] < timings["root",]["time"]

        ref_total = timings["root",]["time"] + timings["another_root",]["time"]
        assert get_total_time() == pytest.approx(ref_total)


class TestCounters:
    def test_nested_context_with_counter(self) -> None:
        with TimerContext("root"):
            for i in range(3):
                with TimerContext("step", counter=i):
                    pass

        timings = raw_timings()
        for i in range(3):
            assert ("root", f"step[{i}]") in timings
        assert ("root", "step[3]") not in timings

        flat = get_execution_timings(flatten=True)
        assert ("root", "step") in flat
        assert ("root", "step[0]") not in flat
        assert flat["root", "step"]["time"] == pytest.approx(
            sum(timings["root", f"step[{i}]"]["time"] for i in range(3))
        )

    def test_brackets_in_name_only_stripped_when_trailing(self) -> None:
        with TimerContext("arr[0]worker"):
            pass
        with TimerContext("weird]"):
            pass

        flat = get_execution_timings(flatten=True)
        assert ("arr[0]worker",) in flat
        assert ("weird]",) in flat


class TestCategories:
    def test_default_category(self) -> None:
        with TimerContext("section"):
            pass

        assert raw_timings()["section",]["category"] == DEFAULT_CATEGORY

    def test_forbidden_nesting_raises(self) -> None:
        register_forbidden_nesting(outer="gpu", inner="cpu")
        with pytest.raises(ValueError, match="not allowed inside"), TimerContext("root"):  # noqa: SIM117
            with TimerContext("nested", category="gpu"), TimerContext("inner", category="cpu"):
                pass

    def test_allowed_nesting_does_not_raise(self) -> None:
        register_forbidden_nesting(outer="gpu", inner="cpu")
        with TimerContext("root"):  # noqa: SIM117
            with TimerContext("nested", category="gpu"), TimerContext("inner", category="gpu"):
                pass

        assert ("root", "nested", "inner") in raw_timings()

    def test_clear_forbidden_nesting(self) -> None:
        register_forbidden_nesting(outer="gpu", inner="cpu")
        clear_forbidden_nesting()
        with TimerContext("outer", category="gpu"), TimerContext("inner", category="cpu"):
            pass

    def test_total_category_time_counts_only_top_most_entries(self) -> None:
        with TimerContext("root"):
            time.sleep(0.01)
            with TimerContext("nested", category="gpu"):
                time.sleep(0.001)
            with TimerContext("another_nested"):
                time.sleep(0.0001)

        with TimerContext("another_root", category="gpu"):
            time.sleep(0.011)

        with TimerContext("third_root"):
            time.sleep(0.01)
            with TimerContext("gpu_nested", category="gpu"):
                time.sleep(0.001)
                with TimerContext("gpu_inside_gpu", category="gpu"):
                    time.sleep(0.001)
            with TimerContext("cpu_section", category="cpu"):
                time.sleep(0.001)

        timings = raw_timings()

        ref_gpu = timings["root", "nested"]["time"]
        ref_gpu += timings["another_root",]["time"]
        ref_gpu += timings["third_root", "gpu_nested"]["time"]
        assert get_total_category_time("gpu") == pytest.approx(ref_gpu)

        assert get_total_category_time("cpu") == pytest.approx(timings["third_root", "cpu_section"]["time"])

        ref_total = timings["root",]["time"] + timings["another_root",]["time"] + timings["third_root",]["time"]
        assert get_total_time() == pytest.approx(ref_total)


class TestReporting:
    def test_report_timings(self) -> None:
        with TimerContext("context_report"):
            pass

        with TimerContext("context_report_nested"):
            for i in range(3):
                with TimerContext(f"context_sub_{i}"), TimerContext(f"context_subsub_{i}"):
                    pass

        report = get_execution_times_report()

        assert "Total calculation time" in report
        assert "context_report:" in report
        assert "context_report_nested:" in report
        for i in range(3):
            assert f"..  context_sub_{i}:" in report
            assert f"..  ..  context_subsub_{i}:" in report

    def test_report_empty_when_no_timings(self) -> None:
        assert get_execution_times_report() == ""

    def test_report_flatten_flag(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 1, 2]):
            for i in range(2):
                with TimerContext("foo", counter=i):
                    pass

        non_flat = get_execution_times_report(flatten=False)
        assert "foo[0]" in non_flat
        assert "foo:" not in non_flat

        flat = get_execution_times_report(flatten=True)
        assert "foo[0]" not in flat
        assert "foo:" in flat

    def test_get_execution_timings_flatten_aggregates_and_strips_counters(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 1, 2]):
            for i in range(2):
                with TimerContext("foo", counter=i, category="cpu"):
                    pass

        result = get_execution_timings(flatten=True)
        assert len(result) == 1
        assert result["foo",]["time"] == pytest.approx(2.0)
        assert result["foo",]["category"] == "cpu"

    def test_get_execution_timings_non_flatten_preserves_counters(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 0.5, 1, 1.5]):
            with TimerContext("bar", counter=0, category="gpu"):
                pass
            with TimerContext("bar", counter=1, category="gpu"):
                pass

        result = get_execution_timings(flatten=False)
        assert len(result) == 2
        assert result["bar[0]",]["time"] == pytest.approx(0.5)
        assert result["bar[0]",]["category"] == "gpu"

    def test_get_execution_timings_with_mixed_categories(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 2, 3]):
            with TimerContext("c1", category="cpu"):
                pass
            with TimerContext("g1", category="gpu"):
                pass

        result = get_execution_timings(flatten=True)
        assert result["c1",]["time"] == pytest.approx(1.0)
        assert result["c1",]["category"] == "cpu"
        assert result["g1",]["time"] == pytest.approx(1.0)
        assert result["g1",]["category"] == "gpu"

    def test_get_total_category_time(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 2, 3]):
            with TimerContext("c1", category="cpu"):
                pass
            with TimerContext("g1", category="gpu"):
                pass

        assert get_total_category_time("cpu") == pytest.approx(1.0)
        assert get_total_category_time("gpu") == pytest.approx(1.0)
        assert get_total_time() == pytest.approx(2.0)


class TestOutput:
    def test_log_execution_times_logs_report(self, caplog: pytest.LogCaptureFixture) -> None:
        with TimerContext("logged"):
            pass

        with caplog.at_level(logging.INFO):
            log_execution_times()

        assert "Total calculation time" in caplog.text
        assert "logged:" in caplog.text

    def test_get_execution_times_json_is_valid_and_structured(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 1, 2, 2, 3]):
            with TimerContext("root", category="gpu"):
                pass
            with TimerContext("child_root"):  # noqa: SIM117
                with TimerContext("child", category="cpu"):
                    pass

        payload = cast(TimingsPayload, json.loads(get_execution_times_json()))

        # Total time is the sum of top-level sections only.
        assert payload["total_time"] == pytest.approx(get_total_time())
        assert set(payload["total_category_time"]) == {"gpu", "default", "cpu"}
        by_path = {tuple(s["path"]): s for s in payload["sections"]}
        assert set(by_path) == {("root",), ("child_root",), ("child_root", "child")}
        assert by_path["root",]["category"] == "gpu"
        assert by_path["child_root", "child"]["category"] == "cpu"

    def test_get_execution_times_json_flattens_counters(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 1, 2]):
            for i in range(2):
                with TimerContext("step", counter=i):
                    pass

        flat_payload = cast(TimingsPayload, json.loads(get_execution_times_json(flatten=True)))
        paths = {tuple(s["path"]) for s in flat_payload["sections"]}
        assert ("step",) in paths
        assert ("step[0]",) not in paths

    def test_save_execution_timings_json_writes_file(self, tmp_path: Path) -> None:
        with TimerContext("saved", category="gpu"):
            pass

        out = save_execution_timings_json(tmp_path / "timings.json")

        assert out.exists()
        file_payload = cast(TimingsPayload, json.loads(out.read_text(encoding="utf-8")))
        assert {tuple(s["path"]) for s in file_payload["sections"]} == {("saved",)}

    def test_save_execution_timings_json_accepts_str_path(self, tmp_path: Path) -> None:
        with TimerContext("saved"):
            pass

        out = save_execution_timings_json(str(tmp_path / "t.json"))

        assert isinstance(out, Path)
        assert out.exists()


class TestTimerContextDecorator:
    def test_decorator_records_timing(self) -> None:
        @TimerContext("decorated")
        def work() -> None:
            pass

        work()
        timings = raw_timings()
        assert ("decorated",) in timings
        assert timings["decorated",]["time"] >= 0

    def test_decorator_preserves_return_value(self) -> None:
        @TimerContext("decorated")
        def compute() -> int:
            return 42

        assert compute() == 42

    def test_decorator_preserves_function_metadata(self) -> None:
        @TimerContext("decorated")
        def my_function() -> None:
            """My docstring."""

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_decorator_accumulates_time_across_calls(self) -> None:
        @TimerContext("step")
        def step() -> None:
            pass

        with patch.object(time, "perf_counter", side_effect=[0, 1, 1, 2]):
            step()
            step()

        assert raw_timings()["step",]["time"] == pytest.approx(2.0)

    def test_decorator_with_category(self) -> None:
        @TimerContext("gpu_work", category="gpu")
        def gpu_work() -> None:
            pass

        gpu_work()
        assert raw_timings()["gpu_work",]["category"] == "gpu"

    def test_decorator_inside_context_manager_creates_nested_timing(self) -> None:
        @TimerContext("inner")
        def inner_work() -> None:
            pass

        with TimerContext("outer"):
            inner_work()

        timings = raw_timings()
        assert ("outer",) in timings
        assert ("outer", "inner") in timings


class TestExceptions:
    def test_timing_recorded_when_body_raises(self) -> None:
        with pytest.raises(RuntimeError), TimerContext("failing"):
            raise RuntimeError("boom")

        timings = raw_timings()
        assert ("failing",) in timings
        assert timings["failing",]["time"] >= 0

    def test_context_stack_recovered_after_exception(self) -> None:
        with pytest.raises(RuntimeError), TimerContext("outer"):  # noqa: SIM117
            with TimerContext("inner"):
                raise RuntimeError("boom")

        # A subsequent top-level section must not be nested under the failed ones.
        with TimerContext("clean"):
            pass

        timings = raw_timings()
        assert ("clean",) in timings
        assert ("outer", "clean") not in timings

    def test_decorator_propagates_exception_and_records_timing(self) -> None:
        @TimerContext("failing")
        def failing() -> None:
            raise ValueError("bad")

        with pytest.raises(ValueError):
            failing()

        assert ("failing",) in raw_timings()


class TestCategoryAttribution:
    def test_revisit_updates_category(self) -> None:
        with TimerContext("a", category="gpu"):
            pass
        with TimerContext("a", category="cpu"):
            pass

        assert raw_timings()["a",]["category"] == "cpu"

    def test_flatten_uses_latest_category(self) -> None:
        with TimerContext("s", category="gpu", counter=0):
            pass
        with TimerContext("s", category="cpu", counter=1):
            pass

        assert get_execution_timings(flatten=True)["s",]["category"] == "cpu"

    def test_total_category_time_unknown_category_is_zero(self) -> None:
        with TimerContext("a", category="gpu"):
            pass

        assert get_total_category_time("nonexistent") == 0.0

    def test_forbidden_nesting_error_message(self) -> None:
        register_forbidden_nesting(outer="gpu", inner="cpu")
        with pytest.raises(ValueError, match=r"'cpu'.*inside.*'gpu'"), TimerContext("gpu_sec", category="gpu"):  # noqa: SIM117
            with TimerContext("cpu_sec", category="cpu"):
                pass

    def test_multiple_forbidden_rules(self) -> None:
        register_forbidden_nesting(outer="gpu", inner="cpu")
        register_forbidden_nesting(outer="gpu", inner="io")
        with pytest.raises(ValueError), TimerContext("gpu_sec", category="gpu"):  # noqa: SIM117
            with TimerContext("io_sec", category="io"):
                pass


class TestClearAndReuse:
    def test_clear_execution_timings(self) -> None:
        with TimerContext("a"):
            pass
        clear_execution_timings()

        assert raw_timings() == {}
        assert get_total_time() == 0.0

    def test_timing_works_after_clear(self) -> None:
        with TimerContext("a"):
            pass
        clear_execution_timings()
        with TimerContext("b"):
            pass

        timings = raw_timings()
        assert list(timings) == [("b",)]

    def test_deep_nesting(self) -> None:
        with TimerContext("l0"), TimerContext("l1"), TimerContext("l2"), TimerContext("l3"):
            pass

        timings = raw_timings()
        assert ("l0", "l1", "l2", "l3") in timings


class TestThreading:
    def test_concurrent_recording_does_not_crash(self) -> None:
        """Concurrent recording from multiple threads must not raise."""
        import threading

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def worker(name: str) -> None:
            try:
                _ = barrier.wait()
                with TimerContext(name):
                    time.sleep(0.005)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_per_thread_nesting_is_independent(self) -> None:
        """Each thread keeps its own context stack; both nest correctly into the shared registry."""
        import threading

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def worker(root: str, child: str) -> None:
            try:
                _ = barrier.wait()
                with TimerContext(root):
                    time.sleep(0.002)
                    with TimerContext(child):
                        time.sleep(0.002)
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=("t0", "c0")),
            threading.Thread(target=worker, args=("t1", "c1")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        timings = raw_timings()
        assert ("t0",) in timings
        assert ("t0", "c0") in timings
        assert ("t1",) in timings
        assert ("t1", "c1") in timings
        # No cross-thread nesting.
        assert ("t0", "c1") not in timings
        assert ("t1", "c0") not in timings


class TestAsyncDecorator:
    def test_async_decorator_times_the_await_not_coroutine_creation(self) -> None:
        @TimerContext("async_work")
        async def work() -> None:
            await asyncio.sleep(0.05)

        asyncio.run(work())

        # Timing only the coroutine object's creation records ~1e-06 s, so any threshold
        # orders of magnitude above that proves the await was covered. Kept well below the
        # sleep duration because Windows' ~15.6 ms timer granularity lets short sleeps
        # return early -- a threshold near 0.05 makes this test flaky rather than stricter.
        assert raw_timings()["async_work",]["time"] >= 0.01

    def test_async_decorator_preserves_return_value(self) -> None:
        @TimerContext("async_compute")
        async def compute() -> int:
            await asyncio.sleep(0)
            return 42

        assert asyncio.run(compute()) == 42

    def test_async_decorator_preserves_function_metadata(self) -> None:
        @TimerContext("decorated")
        async def my_coro() -> None:
            """My async docstring."""

        assert my_coro.__name__ == "my_coro"
        assert my_coro.__doc__ == "My async docstring."
        assert inspect.iscoroutinefunction(my_coro)

    def test_async_decorator_propagates_exception_and_records_timing(self) -> None:
        @TimerContext("async_failing")
        async def failing() -> None:
            await asyncio.sleep(0)
            raise ValueError("bad")

        with pytest.raises(ValueError):
            asyncio.run(failing())

        assert ("async_failing",) in raw_timings()

    def test_async_decorator_with_category(self) -> None:
        @TimerContext("gpu_work", category="gpu")
        async def gpu_work() -> None:
            await asyncio.sleep(0)

        asyncio.run(gpu_work())
        assert raw_timings()["gpu_work",]["category"] == "gpu"

    def test_concurrent_tasks_nest_independently(self) -> None:
        """Each asyncio task gets its own context stack, so gathered tasks do not cross-nest."""

        @TimerContext("child")
        async def child() -> None:
            await asyncio.sleep(0.01)

        async def parent(index: int) -> None:
            with TimerContext(f"task{index}"):
                await child()

        async def main() -> None:
            _ = await asyncio.gather(parent(0), parent(1))

        asyncio.run(main())

        timings = raw_timings()
        assert ("task0", "child") in timings
        assert ("task1", "child") in timings
        # No cross-task nesting or leakage to the top level.
        assert ("task0", "task1") not in timings
        assert ("child",) not in timings


class TestContextManagerProtocol:
    def test_enter_returns_the_context(self) -> None:
        with TimerContext("named", category="gpu", counter=2) as ctx:
            assert isinstance(ctx, TimerContext)
            assert ctx.name == "named[2]"
            assert ctx.category == "gpu"


class TestReportOrdering:
    def test_children_follow_their_parent_after_revisit(self) -> None:
        """A parent re-entered after an unrelated sibling still renders its own children."""
        with TimerContext("a"), TimerContext("b"):
            pass
        with TimerContext("x"):
            pass
        with TimerContext("a"), TimerContext("c"):
            pass

        lines = [line for line in get_execution_times_report(flatten=False).splitlines() if ":" in line]
        names = [line.split(":")[0] for line in lines if not line.startswith("Total")]

        assert names == ["a", "..  b", "..  c", "x"]

    def test_report_renders_when_all_elapsed_times_are_zero(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0.0, 0.0]), TimerContext("instant"):
            pass

        report = get_execution_times_report()
        assert "instant: 0.0000 s (0.00%)" in report


class TestRobustness:
    def test_clear_during_active_section_does_not_raise(self) -> None:
        """Clearing mid-section drops the sample rather than raising out of the ``with`` block."""
        with TimerContext("live"):
            clear_execution_timings()

        assert raw_timings() == {}

        # The context stack is still usable afterwards.
        with TimerContext("after"):
            pass
        assert list(raw_timings()) == [("after",)]

    def test_reading_reports_while_another_thread_records(self) -> None:
        """Readers snapshot under the lock, so concurrent recording cannot break iteration."""
        import threading

        stop = threading.Event()
        errors: list[BaseException] = []

        def writer() -> None:
            index = 0
            while not stop.is_set():
                with TimerContext(f"s{index % 20}"):
                    pass
                index += 1

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            for _ in range(200):
                try:
                    _ = get_execution_times_report()
                    _ = get_execution_times_json()
                    _ = get_total_category_time(DEFAULT_CATEGORY)
                    _ = get_total_time()
                except BaseException as exc:  # pragma: no cover - only on regression
                    errors.append(exc)
                    break
        finally:
            stop.set()
            thread.join()

        assert errors == []

    def test_logging_uses_the_package_logger_not_the_root_logger(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            assert get_execution_times_report() == ""

        assert [record.name for record in caplog.records] == ["execution_timer._timer"]


class TestRegressions:
    @pytest.mark.parametrize("clear_between_calls", [False, True])
    def test_overlapping_tasks_keep_independent_start_times(self, clear_between_calls: bool) -> None:
        now = 0.0
        shared = TimerContext("shared")

        async def main() -> None:
            nonlocal now
            started = [asyncio.Event(), asyncio.Event()]
            release = [asyncio.Event(), asyncio.Event()]

            async def worker(index: int) -> None:
                with shared:
                    started[index].set()
                    _ = await release[index].wait()

            first = asyncio.create_task(worker(0))
            _ = await started[0].wait()
            if clear_between_calls:
                clear_execution_timings()
            now = 2.0
            second = asyncio.create_task(worker(1))
            _ = await started[1].wait()
            now = 5.0
            release[0].set()
            await first
            now = 9.0
            release[1].set()
            await second

        with patch.object(time, "perf_counter", side_effect=lambda: now):
            asyncio.run(main())

        assert raw_timings() == {("shared",): {"time": 7.0 if clear_between_calls else 12.0, "category": "default"}}

    def test_overlapping_thread_decorator_calls_accumulate_each_duration(self) -> None:
        now = 0.0
        started = [threading.Event(), threading.Event()]
        release = [threading.Event(), threading.Event()]

        @TimerContext("shared")
        def worker(index: int) -> None:
            started[index].set()
            assert release[index].wait(timeout=5)

        with patch.object(time, "perf_counter", side_effect=lambda: now), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worker, 0)
            try:
                assert started[0].wait(timeout=5)
                now = 2.0
                second = pool.submit(worker, 1)
                assert started[1].wait(timeout=5)
                now = 5.0
                release[0].set()
                first.result(timeout=5)
                now = 9.0
                release[1].set()
                second.result(timeout=5)
            finally:
                for event in release:
                    event.set()

        assert raw_timings()["shared",]["time"] == 12.0

    def test_flatten_category_follows_latest_revisit_even_with_equal_clock_readings(self) -> None:
        with patch.object(time, "perf_counter", return_value=0.0):
            for counter, category in [(0, "gpu"), (1, "cpu"), (0, "io")]:
                with TimerContext("step", counter=counter, category=category):
                    pass

        assert get_execution_timings()["step",]["category"] == "io"

    @pytest.mark.parametrize("name", ["array[index]", "empty[]", "label[+1]", "label[1.5]", "label[\uff11\uff12]"])
    def test_flatten_preserves_non_counter_brackets(self, name: str) -> None:
        with TimerContext(name):
            pass
        assert list(get_execution_timings()) == [(name,)]

    @pytest.mark.parametrize("counter", [-12, 0, 12])
    def test_signed_counters_flatten_only_the_last_suffix(self, counter: int) -> None:
        with TimerContext("array[index]", counter=counter):
            pass
        assert list(get_execution_timings()) == [("array[index]",)]

    @pytest.mark.parametrize("flatten", [False, True])
    def test_json_keeps_categories_hidden_by_flattening(self, flatten: bool) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 2, 3, 6]):
            with TimerContext("step", counter=0, category="gpu"):
                pass
            with TimerContext("step", counter=1, category="cpu"):
                pass

        payload = cast(TimingsPayload, json.loads(get_execution_times_json(flatten=flatten)))
        assert payload["total_category_time"] == {"gpu": 2.0, "cpu": 3.0}
        assert payload["total_time"] == 5.0

    @pytest.mark.parametrize("flatten", [False, True])
    def test_json_uses_one_snapshot_for_sections_and_totals(self, flatten: bool) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 2]), TimerContext("section", category="cpu"):
            pass

        original_round = round

        def clear_while_formatting(value: float, digits: int) -> float:
            # Deterministically simulate another thread clearing the registry after the
            # sections were read but before totals are formatted, through the public API.
            clear_execution_timings()
            return original_round(value, digits)

        with patch.object(builtins, "round", side_effect=clear_while_formatting):
            payload = cast(TimingsPayload, json.loads(get_execution_times_json(flatten=flatten)))

        assert payload["sections"] == [{"name": "section", "path": ["section"], "time": 2.0, "category": "cpu"}]
        assert payload["total_time"] == 2.0
        assert payload["total_category_time"] == {"cpu": 2.0}

    def test_disabled_logging_does_not_warn_about_empty_report(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("executiontimer.test.disabled")
        with caplog.at_level(logging.WARNING), patch.object(logger, "isEnabledFor", return_value=False):
            log_execution_times(logger=logger)
        assert caplog.records == []


class TestLifecycle:
    def test_reusing_one_context_accumulates_exact_durations(self) -> None:
        context = TimerContext("reused")
        with patch.object(time, "perf_counter", side_effect=[0, 2, 5, 8]):
            with context:
                pass
            with context:
                pass
        assert raw_timings()["reused",]["time"] == 5.0

    def test_one_context_can_be_reentered(self) -> None:
        context = TimerContext("recursive")
        with patch.object(time, "perf_counter", side_effect=[0, 1, 3, 7]), context, context:
            pass
        assert raw_timings() == {
            ("recursive",): {"time": 7.0, "category": "default"},
            ("recursive", "recursive"): {"time": 2.0, "category": "default"},
        }

    def test_recursive_decorator_preserves_arguments_and_hierarchy(self) -> None:
        @TimerContext("recursive", category="cpu", counter=0)
        def recurse(depth: int, *, value: int) -> int:
            return recurse(depth - 1, value=value + 1) if depth else value

        with patch.object(time, "perf_counter", side_effect=range(6)):
            assert recurse(2, value=40) == 42
        assert [info["time"] for info in raw_timings().values()] == [5.0, 3.0, 1.0]
        assert list(raw_timings()) == [("recursive[0]",) * depth for depth in range(1, 4)]

    def test_failed_entry_leaves_parent_and_its_next_child_intact(self) -> None:
        register_forbidden_nesting("gpu", "cpu")
        with TimerContext("parent", category="gpu"):
            with pytest.raises(ValueError), TimerContext("forbidden", category="cpu"):
                pytest.fail("A forbidden section must not be entered")
            with TimerContext("allowed", category="io"):
                pass
        with TimerContext("after"):
            pass
        assert list(raw_timings()) == [("parent",), ("parent", "allowed"), ("after",)]

    def test_nesting_rules_only_apply_to_the_direct_parent(self) -> None:
        register_forbidden_nesting("gpu", "cpu")
        with (
            TimerContext("gpu", category="gpu"),
            TimerContext("io", category="io"),
            TimerContext("cpu", category="cpu"),
        ):
            pass
        assert ("gpu", "io", "cpu") in raw_timings()

    def test_out_of_order_exit_raises_without_changing_the_active_section(self) -> None:
        outer = TimerContext("outer")
        inner = TimerContext("inner")
        with (
            patch.object(time, "perf_counter", side_effect=[0, 1, 2, 3, 4]),
            outer,
            inner,
            pytest.raises(RuntimeError, match="Cannot stop 'outer' while 'inner' is active"),
        ):
            outer.__exit__(None, None, None)
        assert raw_timings()["outer",]["time"] == 4.0
        assert raw_timings()["outer", "inner"]["time"] == 2.0

    def test_exit_without_an_active_section_is_a_noop(self) -> None:
        TimerContext("unused").__exit__(None, None, None)
        assert raw_timings() == {}

    def test_reports_preserve_orphaned_children_after_clear(self) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 1, 3, 5]), TimerContext("parent"):
            clear_execution_timings()
            with TimerContext("child", category="cpu"):
                pass
        assert list(raw_timings()) == [("parent", "child")]
        assert "child: 2.0000 s (0.00%)" in get_execution_times_report()
        payload = cast(TimingsPayload, json.loads(get_execution_times_json()))
        assert payload["total_time"] == 0.0
        assert payload["total_category_time"] == {"cpu": 2.0}
        assert payload["sections"][0]["path"] == ["parent", "child"]

    def test_deep_reports_do_not_depend_on_python_recursion_limit(self) -> None:
        with ExitStack() as stack:
            for _ in range(1_100):
                _ = stack.enter_context(TimerContext("level"))
        assert len(get_execution_times_report(flatten=False).splitlines()) == 1_103

    def test_async_cancellation_records_time_and_restores_parent(self) -> None:
        @TimerContext("cancelled")
        async def work(*, value: int) -> int:
            assert value == 42
            await asyncio.sleep(0)
            raise asyncio.CancelledError

        async def main() -> None:
            with TimerContext("parent"):
                with pytest.raises(asyncio.CancelledError):
                    _ = await work(value=42)
                with TimerContext("after"):
                    pass

        with patch.object(time, "perf_counter", side_effect=range(6)):
            asyncio.run(main())
        assert raw_timings()["parent", "cancelled"]["time"] == 1.0
        assert list(raw_timings()) == [("parent",), ("parent", "cancelled"), ("parent", "after")]

    def test_child_tasks_inherit_the_parent_without_modifying_its_context(self) -> None:
        @TimerContext("child")
        async def child(value: int, *, increment: int) -> int:
            await asyncio.sleep(0)
            return value + increment

        async def main() -> None:
            with TimerContext("parent"):
                assert await asyncio.gather(child(1, increment=1), child(2, increment=1)) == [2, 3]
                with TimerContext("after"):
                    pass

        asyncio.run(main())
        assert list(raw_timings()) == [("parent",), ("parent", "child"), ("parent", "after")]


class TestSnapshotSemantics:
    @pytest.mark.parametrize("flatten", [False, True])
    def test_mutating_a_returned_report_does_not_change_the_registry(self, flatten: bool) -> None:
        with patch.object(time, "perf_counter", side_effect=[0, 2]), TimerContext("section"):
            pass
        report = get_execution_timings(flatten=flatten)
        report["section",]["time"] = -1
        report["section",]["category"] = "changed"
        report.clear()
        assert raw_timings() == {("section",): {"time": 2.0, "category": "default"}}

    @pytest.mark.parametrize("flatten", [False, True])
    def test_json_category_totals_exclude_matching_ancestors_across_other_categories(self, flatten: bool) -> None:
        with (
            patch.object(time, "perf_counter", side_effect=range(6)),
            TimerContext("outer", category="cpu", counter=1),
            TimerContext("middle", category="io"),
            TimerContext("inner", category="cpu"),
        ):
            pass
        payload = cast(TimingsPayload, json.loads(get_execution_times_json(flatten=flatten)))
        assert payload["total_category_time"] == {"cpu": 5.0, "io": 3.0}
        assert get_total_category_time("cpu") == 5.0
        assert get_total_time(flatten=flatten) == 5.0

    def test_empty_json(self) -> None:
        assert json.loads(get_execution_times_json(indent=None)) == {
            "total_time": 0.0,
            "total_category_time": {},
            "sections": [],
        }

    def test_unicode_json_file_round_trip(self, tmp_path: Path) -> None:
        with TimerContext("计算", category="数据"):
            pass
        out = tmp_path / "timings.json"
        assert save_execution_timings_json(str(out), indent=None) == out
        text = out.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert len(text.splitlines()) == 1
        payload = cast(TimingsPayload, json.loads(text))
        assert payload["sections"][0]["name"] == "计算"
        assert payload["sections"][0]["category"] == "数据"

    def test_custom_logger_receives_the_requested_report(self, caplog: pytest.LogCaptureFixture) -> None:
        with TimerContext("section", counter=0):
            pass
        logger = logging.getLogger("executiontimer.test.custom")
        with caplog.at_level(logging.INFO, logger=logger.name):
            log_execution_times(flatten=False, logger=logger)
        assert [(record.name, record.message) for record in caplog.records] == [
            (logger.name, get_execution_times_report(flatten=False))
        ]
