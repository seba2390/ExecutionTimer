# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-09-20

### Fixed

- Overlapping calls to the same section now accumulate each call's actual duration in
  threads and asyncio tasks, including calls sharing one context or decorator.
- Clearing active timings cannot add a discarded sample to a new entry at the same path.
- JSON sections and totals now use one consistent snapshot, and category totals retain
  categories that disappear when counter variants are merged.
- Flattened categories follow the most recently entered section, including revisited counters.
- Flattening preserves non-integer bracket suffixes such as `array[index]` and `empty[]`.
- An out-of-order context exit raises `RuntimeError` without changing another section's
  elapsed time or active stack.

### Performance

- Cache each active section's path and parent, and reuse decorator contexts to reduce
  recording allocations and avoid rebuilding paths on exit.
- Sum total time directly without copying and flattening the registry.
- Calculate all JSON category totals in one pass over a shared snapshot.
- Skip report generation when logging at `INFO` is disabled.

### Added

- Deterministic regression tests for concurrency, clearing, category attribution, and
  snapshot consistency, plus coverage for recursion, cancellation, and deep nesting.
- A repeatable benchmark for recording and reporting overhead in `benchmarks/overhead.py`.
- Expanded the suite from 53 to 88 tests, achieving 100% statement and branch coverage.

## [0.1.0] - 2026-08-20

First public release on PyPI.

### Added

- `TimerContext` — context manager and decorator for timing a named section of code, with
  optional `category` and `counter` arguments.
- Automatic hierarchical nesting: section names reflect the enclosing timing contexts.
- Native `async def` support — decorating a coroutine function times the whole `await`
  rather than the creation of the coroutine object.
- Per-task and per-thread context isolation via `contextvars`, so concurrently recorded
  sections nest independently and merge into one process-wide report.
- Reporting and export helpers: `get_execution_times_report`, `log_execution_times`,
  `get_execution_timings`, `get_execution_times_json`, `save_execution_timings_json`,
  `get_total_time`, `get_total_category_time`.
- Optional nesting rules via `register_forbidden_nesting` / `clear_forbidden_nesting`.
- `clear_execution_timings` to reset the registry.
- Exported `TimingReport`, `SectionRecord` and `TimingsPayload` typed dictionaries, plus a
  `py.typed` marker so type checkers use the inline annotations.
- `__version__` attribute on the package.

[Unreleased]: https://github.com/seba2390/ExecutionTimer/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/seba2390/ExecutionTimer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seba2390/ExecutionTimer/releases/tag/v0.1.0
