# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-10-01

### Documentation

- The threads section of the concurrency guide was wrong for free-threaded Python 3.14.
  There, a new thread starts in a copy of the context that started it, so its sections
  nest under the section that was open at that moment. A thread pool reuses its workers,
  so each worker keeps the section it started under: work submitted later from another
  section was reported under the first one. The guide said pool work is always reported at
  the top level, and that free-threaded builds nest thread work correctly with no extra
  work. Neither was true on every build. The guide now explains the difference and shows
  how to get the same report on every build: run each call in
  `contextvars.copy_context().run` to nest it under the current section, or in
  `contextvars.Context().run` to keep it at the top level. Behaviour is unchanged.
- Tests cover how threads and reused pool workers nest on each kind of build, and both
  recipes. The guide's examples assert their results on every build.

## [1.1.0] - 2026-09-30

### Changed

- The text report, from `get_execution_times_report()` and `log_execution_times()`, shows
  each time with three decimals in `µs`, `ms` or `s`, whichever keeps the number below
  1000: `48.213 µs`, `315.612 ms`, `2.500 s`. It used to show seconds with four
  decimals, so any section under 50 µs read `0.0000 s`, and fast sections, including a
  whole recursive call tree, looked like zeros. Code that parses the report text needs
  updating. `get_execution_timings()` and the JSON export are unchanged and still return
  seconds.

## [1.0.3] - 2026-09-30

### Changed

- Entering and exiting a section is 20–25% faster, about 0.25 µs less per section on
  CPython 3.14. Each active section's state is now a plain tuple rather than a named
  tuple, whose constructor cost more than the rest of section entry. Behaviour is
  unchanged.

### Documentation

- A documentation site at <https://seba2390.github.io/ExecutionTimer/>, with a getting
  started guide, a user guide and an API reference generated from the docstrings. It is
  built with Sphinx and deployed to GitHub Pages whenever `main` changes. The package's
  `Documentation` link points to it from this release on.
- The README is shorter and links to the site for details.
- Public functions and types have full docstrings, with parameters, return values and
  exceptions.
- The Python examples in the README and the documentation run as part of the test suite,
  and CI builds the site on every pull request, failing on any warning.
- Refresh the overhead benchmark, comparing 0.1.0, 1.0.2 and 1.0.3.

## [1.0.2] - 2026-09-30

### Fixed

- Decorating a function that returns a coroutine, typically because another decorator
  sits between `TimerContext` and an `async def`, now times the `await`. Previously the
  section recorded only the call that created the coroutine, a few microseconds however
  long the coroutine ran. Other awaitables, such as futures and tasks, are returned
  unchanged.

### Changed

- The test suite fails on any warning, and CI requires 100% statement and branch coverage
  rather than 95%.

### Documentation

- Note that flattening also merges sections whose own names end in an integer, such as
  `"row[1]"` and `"row[2]"`.
- The release steps in the contributing guide describe the pull-request flow that the
  protected `main` branch requires.
- Refresh the overhead benchmark against version 1.0.2.

## [1.0.1] - 2026-09-30

### Fixed

- Exiting a section while an inner one is still active no longer leaves the active stack
  corrupted when warnings are configured as errors (for example pytest's
  `filterwarnings = ["error"]`). The `RuntimeWarning` was emitted before the exit was
  recorded, so raising it skipped the cleanup that 1.0.0 introduced. The section is now
  recorded and the stack unwound before the warning is emitted.
- Sections whose parent was cleared while active now count as top-level. Previously,
  clearing timings inside an outer section, such as a periodic clear in a long-running
  loop, made `get_total_time()`, the report and the JSON `total_time` read `0`, every
  percentage `0.00%`, and indented the sections beneath an unrelated one in the report.

### Changed

- The build requires `hatchling>=1.27`, the first release that supports the PEP 639
  `license-files` metadata the project declares.
- Dependabot groups its monthly updates into one pull request per ecosystem.

## [1.0.0] - 2026-09-30

First stable release. The public API is now covered by semantic versioning: breaking
changes will wait for 2.0. Three changes below are breaking; they clean up the API before
it is frozen.

### Changed

- **Breaking:** the report from `get_execution_times_report()` no longer starts with a
  blank line, and its header reads `Total time:` rather than `Total calculation time:`.
  `log_execution_times()` still starts the report on its own line.
- **Breaking:** `TimerContext.timer` is now private (`_timer`). It exposed the internal
  registry, which is not part of the public API.
- `get_execution_times_report()` no longer logs a warning when there are no timings; it
  returns `""`. `log_execution_times()` warns instead, on the logger it was given, so
  building an empty report no longer prints to stderr when logging is not configured.
- The package is classified as `Development Status :: 5 - Production/Stable`.

### Removed

- **Breaking:** the `flatten` parameter of `get_total_time()`, which had no effect.

### Documentation

- README links to the changelog, contributing guide, benchmarks and license are absolute,
  so they work on PyPI.
- Note that each `counter=` value is kept as a separate section until the timings are
  cleared.

### Fixed

- Exiting a section while an inner one is still active, typically because a paused
  generator holds a section open, no longer raises `RuntimeError`. The raise replaced any
  exception already propagating from the timed block and left the active stack corrupted
  for the rest of the thread. The timer now emits a `RuntimeWarning`, records the exited
  section, and discards the unfinished inner sections. Exiting a section that is no longer
  active does nothing, so closing the paused generator later no longer raises either.

### Security

- Workflows pin every action to a full commit SHA, with the release as a comment that
  Dependabot keeps current, and CI installs dependencies with `uv sync --locked` so a
  stale lockfile fails the build.

## [0.2.0] - 2026-09-30

### Changed

- Decorating a generator function or an async generator function now raises `TypeError`.
  Previously it silently timed only the creation of the generator object, which recorded
  microseconds regardless of how long iteration took.
- Python 3.11 is now supported; the minimum was 3.12 although nothing required it.

### Fixed

- `log_execution_times()` no longer logs an empty `INFO` record, after its warning, when
  there are no timings.

### Documentation

- Explain that threads do not inherit the timing context, and how to nest thread work under
  a section.
- Explain how a section held open across a generator's `yield` absorbs the caller's sections.
- Note that `flatten` has no effect on `get_total_time`.

### Added

- CI tests Python 3.11 and free-threaded Python 3.14t, and the package declares
  free-threading support.
- Workflows run with a read-only token by default and do not persist checkout credentials.

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

[Unreleased]: https://github.com/seba2390/ExecutionTimer/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/seba2390/ExecutionTimer/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/seba2390/ExecutionTimer/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/seba2390/ExecutionTimer/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/seba2390/ExecutionTimer/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/seba2390/ExecutionTimer/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/seba2390/ExecutionTimer/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/seba2390/ExecutionTimer/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/seba2390/ExecutionTimer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seba2390/ExecutionTimer/releases/tag/v0.1.0
