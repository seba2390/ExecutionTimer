# execution-timer

Hierarchical execution timing with user-defined categories, via a singleton timer and a `TimerContext` context manager / decorator.

## Installation

Not yet on PyPI. Install into another project one of three ways:

**From git (recommended)** — always latest `main`:

```bash
uv pip install "git+https://github.com/seba2390/ExecutionTimer.git"
# or pin a commit/tag:
uv pip install "git+https://github.com/seba2390/ExecutionTimer.git@v0.1.0"
```

Or in the other project's `pyproject.toml`:

```toml
dependencies = ["execution-timer @ git+https://github.com/seba2390/ExecutionTimer.git"]
```

**From a wheel** — build once, then install the artifact anywhere:

```bash
./build.sh                                   # produces dist/execution_timer-<ver>-py3-none-any.whl
uv pip install dist/execution_timer-*-py3-none-any.whl
```

Or reference the wheel in the other project's `pyproject.toml`:

```toml
dependencies = ["execution-timer @ file:///absolute/path/to/execution_timer-0.1.0-py3-none-any.whl"]
```

**From CI** — every push to `main` builds a wheel; download it from the workflow's "execution-timer-dist" artifact and install as above.

Requires Python 3.14+.

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
- `log_execution_times(flatten=True, logger=None)` — log the report at INFO level.
- `get_execution_timings(flatten=True)` — timings as a `dict[tuple[str, ...], TimingReport]`.
- `get_execution_times_json(flatten=True, indent=2)` — all timings as a JSON string.
- `save_execution_timings_json(path, flatten=True, indent=2)` — write timings to a JSON file (LLM-friendly).
- `get_total_time(flatten=True)` — total seconds across all top-level sections.
- `get_total_category_time(category)` — total seconds spent in a category (top-level entries only).
- `clear_execution_timings()` — reset all recorded timings.
- `register_forbidden_nesting(outer, inner)` / `clear_forbidden_nesting()` — manage nesting rules.

### Exporting results

The JSON export is structured for easy inspection by a language model or other tooling:

```python
from execution_timer import save_execution_timings_json

save_execution_timings_json("timings.json")
```

```json
{
  "total_time": 2.5,
  "total_category_time": { "gpu": 1.2, "cpu": 1.3 },
  "sections": [
    { "name": "solve", "path": ["solve"], "time": 2.5, "category": "default" },
    { "name": "step", "path": ["solve", "step"], "time": 1.2, "category": "gpu" }
  ]
}
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
uv sync
uv run pytest
uv run ruff check --fix && uv run ruff format
uv run basedpyright
```
