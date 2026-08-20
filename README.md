<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/seba2390/ExecutionTimer/main/assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/seba2390/ExecutionTimer/main/assets/logo-light.svg">
    <img src="https://raw.githubusercontent.com/seba2390/ExecutionTimer/main/assets/logo-light.svg" alt="executiontimer" width="520">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/executiontimer/"><img src="https://img.shields.io/pypi/v/executiontimer?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/executiontimer/"><img src="https://img.shields.io/pypi/pyversions/executiontimer" alt="Python versions"></a>
  <a href="https://github.com/seba2390/ExecutionTimer/actions/workflows/ci.yml"><img src="https://github.com/seba2390/ExecutionTimer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/seba2390/ExecutionTimer/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <img src="https://img.shields.io/badge/types-py.typed-blue" alt="Typed">
</p>

Time named sections of your code with a `with` block or a decorator. Nested sections
automatically form a hierarchy, so you get a breakdown of where time actually went — not
just a single number.

Zero dependencies. Fully type annotated. Works with threads and `asyncio`.

## Features

- ⏱️ **One primitive** — `TimerContext` is both a context manager and a decorator
- 🌳 **Automatic hierarchy** — nesting `with` blocks nests the report, no wiring required
- 🏷️ **User-defined categories** — tag sections with any string (`"gpu"`, `"io"`, `"db"`) and get per-category totals
- ⚡ **Native async** — decorating an `async def` times the whole `await`, not the coroutine object
- 🧵 **Thread and task safe** — context stacks are isolated per thread and per asyncio task
- 🔢 **Loop counters** — time each iteration separately, then merge them back together
- 📤 **JSON export** — structured output for dashboards, CI, or an LLM
- 🚫 **Nesting rules** — optionally forbid one category inside another to catch mistakes early
- 📦 **Zero dependencies**

## Installation

```bash
pip install executiontimer
```

```bash
uv add executiontimer
```

Requires Python 3.12+.

> **Note** — the install name is `executiontimer`, the import name is `execution_timer`:
>
> ```python
> from execution_timer import TimerContext
> ```

## Quick start

```python
import time

from execution_timer import TimerContext, get_execution_times_report

with TimerContext("load_data"):
    time.sleep(0.12)

with TimerContext("solve"):
    for i in range(3):
        with TimerContext("step", category="gpu", counter=i):
            time.sleep(0.05)
    with TimerContext("postprocess", category="cpu"):
        time.sleep(0.03)

print(get_execution_times_report())
```

```text
Total calculation time: 0.3156 s.

load_data: 0.1219 s (38.62%)
solve: 0.1937 s (61.38%)
..  step: 0.1585 s (50.24%)
..  postprocess: 0.0350 s (11.10%)
```

Indentation reflects nesting. Percentages are relative to the total of all top-level
sections, so nested entries show their share of the whole run.

## Usage

### As a decorator

```python
from execution_timer import TimerContext


@TimerContext("preprocess")
def preprocess(rows: list[str]) -> list[str]:
    return [row.strip() for row in rows]
```

Coroutine functions are supported natively — the timing spans the entire `await`:

```python
@TimerContext("fetch", category="io")
async def fetch(url: str) -> bytes: ...
```

### Counters

Pass `counter=i` to time loop iterations separately. The report merges them by default
(`flatten=True`) and keeps them apart when you ask for it:

```python
for i in range(3):
    with TimerContext("step", counter=i):
        ...

get_execution_timings(flatten=True)  # {("step",): {"time": 0.158, ...}}
get_execution_timings(flatten=False)  # {("step[0]",): ..., ("step[1]",): ..., ...}
```

### Categories

Categories are plain strings — use whatever fits your domain:

```python
from execution_timer import get_total_category_time

with TimerContext("matmul", category="gpu"):
    ...

get_total_category_time("gpu")
```

`get_total_category_time` counts only the *top-most* section of a category, so a `gpu`
section nested inside another `gpu` section is not double-counted.

You can also forbid a category from appearing inside another, which raises a `ValueError`
as soon as the invalid nesting happens:

```python
from execution_timer import register_forbidden_nesting

register_forbidden_nesting(outer="gpu", inner="cpu")

with TimerContext("kernel", category="gpu"):
    with TimerContext("reduce", category="cpu"):  # ValueError
        ...
```

### JSON export

`get_execution_times_json` and `save_execution_timings_json` emit a structured snapshot —
convenient for dashboards, CI artifacts, or handing to a language model:

```python
from execution_timer import save_execution_timings_json

save_execution_timings_json("timings.json")
```

```json
{
  "total_time": 0.31556,
  "total_category_time": { "cpu": 0.035024, "default": 0.31556, "gpu": 0.158528 },
  "sections": [
    { "name": "load_data", "path": ["load_data"], "time": 0.121869, "category": "default" },
    { "name": "solve", "path": ["solve"], "time": 0.193691, "category": "default" },
    { "name": "step", "path": ["solve", "step"], "time": 0.158528, "category": "gpu" },
    { "name": "postprocess", "path": ["solve", "postprocess"], "time": 0.035024, "category": "cpu" }
  ]
}
```

### Concurrency

The recorded timings live in one process-wide registry guarded by a lock. The *active
context stack* is stored in a `ContextVar`, so it is isolated per thread and per asyncio
task: concurrently recorded sections nest independently and merge into a single report.

```python
async def worker(n: int) -> None:
    with TimerContext(f"task{n}"):
        await fetch(...)  # recorded as ("task{n}", "fetch")


await asyncio.gather(worker(0), worker(1))
```

Recording the *same* section path from overlapping threads or tasks is not meaningful —
the elapsed times would overlap and sum to more than the wall-clock duration. Give
concurrent sections distinct names (or use `counter=`).

## API

| Function | Description |
| --- | --- |
| `TimerContext(name, category=DEFAULT_CATEGORY, counter=None)` | Context manager **and** decorator for timing a section. |
| `get_execution_times_report(*, flatten=True)` | Formatted, indented report of all sections. |
| `log_execution_times(*, flatten=True, logger=None)` | Log that report at `INFO` level. |
| `get_execution_timings(*, flatten=True)` | Timings as `dict[tuple[str, ...], TimingReport]`. |
| `get_execution_times_json(*, flatten=True, indent=2)` | All timings as a JSON string. |
| `save_execution_timings_json(path, *, flatten=True, indent=2)` | Write timings to a JSON file; returns the `Path`. |
| `get_total_time(*, flatten=True)` | Total seconds across all top-level sections. |
| `get_total_category_time(category)` | Total seconds in a category (top-most entries only). |
| `clear_execution_timings()` | Reset all recorded timings. |
| `register_forbidden_nesting(outer, inner)` | Forbid `inner` category directly inside `outer`. |
| `clear_forbidden_nesting()` | Remove all nesting rules. |

`flatten=True` merges `counter` variants of a section back together; `flatten=False`
keeps each `name[i]` separate.

Exported types: `TimingReport`, `SectionRecord`, `TimingsPayload`, and `DEFAULT_CATEGORY`.
The package ships a `py.typed` marker, so type checkers use the inline annotations.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest --cov
uv run ruff check --fix && uv run ruff format
uv run basedpyright
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, and
[CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT — see [LICENSE](LICENSE).
