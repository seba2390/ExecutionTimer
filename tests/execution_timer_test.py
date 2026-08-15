"""Tests for the execution timer, using only the public API."""

import time
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from execution_timer import (
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
