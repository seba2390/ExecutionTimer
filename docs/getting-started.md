# Getting started

This page takes you from installing the package to reading your first report. It takes
about five minutes.

## Install

`executiontimer` needs Python 3.11 or newer and has no dependencies.

::::{tab-set}
:::{tab-item} pip
```bash
pip install executiontimer
```
:::
:::{tab-item} uv
```bash
uv add executiontimer
```
:::
::::

The install name is `executiontimer`, but the module you import is `execution_timer`:

```python
from execution_timer import TimerContext
```

## Time a section

Wrap the code you want to measure in a `with TimerContext(...)` block and give it a name:

```python
import time

from execution_timer import TimerContext, get_execution_times_report

with TimerContext("load_data"):
    time.sleep(0.1)

print(get_execution_times_report())
```

```text
Total time: 0.1035 s.

load_data: 0.1035 s (100.00%)
```

Timings are recorded in one registry for the whole process. Every section you time, in any
module, ends up in the same report.

## Nest sections

A section started inside another one is recorded beneath it. You don't pass parents around:
the nesting of your code is the nesting of the report.

```python
from execution_timer import clear_execution_timings

clear_execution_timings()

with TimerContext("pipeline"):
    with TimerContext("load"):
        time.sleep(0.02)
    with TimerContext("transform"):
        time.sleep(0.05)
        with TimerContext("validate"):
            time.sleep(0.01)

print(get_execution_times_report())
```

```text
Total time: 0.0905 s.

pipeline: 0.0905 s (100.00%)
..  load: 0.0232 s (25.60%)
..  transform: 0.0673 s (74.32%)
..  ..  validate: 0.0126 s (13.88%)
```

How to read the report:

- **Indentation** shows nesting. `validate` ran inside `transform`, which ran inside
  `pipeline`.
- **Total time** is the sum of the top-level sections. Nested sections are part of their
  parent's time, so they aren't added again.
- **Percentages** are shares of the total, at every level. `validate` took 13.88% of the
  whole run, not 13.88% of `transform`.

Calling {func}`~execution_timer.clear_execution_timings` starts over with an empty
registry.

## Use it as a decorator

The same object works as a decorator. Every call to the function is timed and added to the
same section:

```python
@TimerContext("parse")
def parse(line: str) -> list[str]:
    return line.split(",")


for line in ["a,b", "c,d", "e,f"]:
    parse(line)
```

Decorated calls nest like `with` blocks: calling `parse` inside `pipeline` records it as
`pipeline` › `parse`. `async def` functions work too, and the timing covers the whole
`await`. See {doc}`guide/timing-code`.

## Group sections with categories

Tag sections with a category to total them across the tree:

```python
from execution_timer import get_total_category_time

with TimerContext("download", category="io"):
    time.sleep(0.02)
with TimerContext("save", category="io"):
    time.sleep(0.01)

print(f"{get_total_category_time('io'):.2f} s spent on I/O")
```

```text
0.03 s spent on I/O
```

Categories are plain strings, so use whatever fits your code. See {doc}`guide/categories`.

## Get the numbers out

Besides the text report, you can get the timings as data:

```python
from execution_timer import get_execution_timings, get_total_time, log_execution_times

get_total_time()  # seconds across all top-level sections
get_execution_timings()  # {("pipeline", "load"): {"time": 0.02, "category": "default"}, ...}
log_execution_times()  # the report, logged at INFO level
```

Or as JSON for a dashboard, a CI artifact or a language model:

```python
from execution_timer import save_execution_timings_json

save_execution_timings_json("timings.json")
```

See {doc}`guide/reports` for the formats.

## Next steps

- {doc}`guide/timing-code`: decorators, async functions, exceptions and recursion.
- {doc}`guide/counters`: timing each iteration of a loop.
- {doc}`guide/concurrency`: threads, asyncio tasks and generators.
- {doc}`api`: every function and type.
