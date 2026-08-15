# execution-timer

Hierarchical execution timing with user-defined categories, via a singleton timer and a `TimerContext` context manager / decorator.

## Installation

```bash
pip install execution-timer
```

## Usage

```python
from execution_timer import TimerContext, get_execution_times_report

with TimerContext("load_data"):
    ...

with TimerContext("solve"):
    for i in range(3):
        with TimerContext("step", category="gpu", counter=i):
            ...


@TimerContext("preprocess")
def preprocess() -> None: ...


print(get_execution_times_report())
```

Section names reflect nesting, an optional `counter` appends `[i]` to the name (merged again when `flatten=True`), and `category` is any user-chosen string.

### Categories

Categories are plain strings — use whatever fits your domain. Optionally forbid nesting one category inside another:

```python
from execution_timer import register_forbidden_nesting

register_forbidden_nesting(outer="gpu", inner="cpu")
```

### Thread safety

The active-context stack is thread-local, so sections recorded concurrently on different threads nest independently and merge into one process-wide report. Recording the *same* section path from overlapping threads is not meaningful.

## API

- `TimerContext(name, category=DEFAULT_CATEGORY, counter=None)` — context manager / decorator.
- `get_execution_times_report(flatten=True)` — formatted report of all sections.
- `get_execution_timings(flatten=True)` — timings as a `dict[tuple[str, ...], TimingReport]`.
- `get_total_time(flatten=True)` — total seconds across all top-level sections.
- `get_total_category_time(category)` — total seconds spent in a category (top-level entries only).
- `clear_execution_timings()` — reset all recorded timings.
- `register_forbidden_nesting(outer, inner)` / `clear_forbidden_nesting()` — manage nesting rules.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
uv sync
uv run pytest
uv run ruff check --fix && uv run ruff format
uv run basedpyright
```
