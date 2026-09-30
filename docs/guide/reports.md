# Reports and export

All timings live in one registry for the whole process. You can read them as a text report,
a log record, a dictionary or JSON. Every reader takes a snapshot, so you can call them
while other threads are still recording.

The examples on this page use these timings:

```python
import time

from execution_timer import TimerContext

with TimerContext("load_data", category="io"):
    time.sleep(0.02)

with TimerContext("solve"):
    for i in range(2):
        with TimerContext("step", category="gpu", counter=i):
            time.sleep(0.01)
```

## Text report

{func}`~execution_timer.get_execution_times_report` returns the report as a string, or `""`
if nothing has been recorded:

```python
from execution_timer import get_execution_times_report

print(get_execution_times_report())
```

```text
Total time: 0.0499 s.

load_data: 0.0249 s (49.92%)
solve: 0.0250 s (50.08%)
..  step: 0.0249 s (49.97%)
```

Sections appear depth-first, each followed by its children, in the order they were first
entered. Percentages are shares of the total time at every level.

## Logging

{func}`~execution_timer.log_execution_times` logs the same report at `INFO` level, starting
on its own line after the log record's prefix:

```python
import logging

from execution_timer import log_execution_times

logging.basicConfig(level=logging.INFO)
log_execution_times()
```

```text
INFO:execution_timer._timer:
Total time: 0.0499 s.

load_data: 0.0249 s (49.92%)
solve: 0.0250 s (50.08%)
..  step: 0.0249 s (49.97%)
```

It logs to the `execution_timer._timer` logger unless you pass your own with
`logger=`. If the logger has `INFO` disabled, it returns without building the report, so it
costs almost nothing in production. If nothing has been recorded, it logs a warning
instead.

## As a dictionary

{func}`~execution_timer.get_execution_timings` returns a new dictionary keyed by section
path. Each value is a {class}`~execution_timer.TimingReport` with the seconds and the
category:

```python
from execution_timer import get_execution_timings

timings = get_execution_timings()

for path, report in timings.items():
    print(" › ".join(path), f"{report['time']:.3f} s", report["category"])
```

```text
load_data 0.025 s io
solve 0.025 s default
solve › step 0.025 s gpu
```

Two more functions give totals directly:

```python
from execution_timer import get_total_category_time, get_total_time

total = get_total_time()  # seconds across all top-level sections
gpu = get_total_category_time("gpu")  # seconds in the top-most "gpu" sections
```

## JSON

{func}`~execution_timer.get_execution_times_json` returns a JSON document and
{func}`~execution_timer.save_execution_timings_json` writes it to a file. Both take
`indent=`, which is `2` by default; pass `None` for the most compact output.

```python
from execution_timer import get_execution_times_json, save_execution_timings_json

document = get_execution_times_json()
path = save_execution_timings_json("timings.json")
```

```json
{
  "total_time": 0.049851,
  "total_category_time": {
    "default": 0.024964,
    "gpu": 0.02491,
    "io": 0.024887
  },
  "sections": [
    {
      "name": "load_data",
      "path": [
        "load_data"
      ],
      "time": 0.024887,
      "category": "io"
    },
    {
      "name": "solve",
      "path": [
        "solve"
      ],
      "time": 0.024964,
      "category": "default"
    },
    {
      "name": "step",
      "path": [
        "solve",
        "step"
      ],
      "time": 0.02491,
      "category": "gpu"
    }
  ]
}
```

The document has three fields. Their types are exported as
{class}`~execution_timer.TimingsPayload` and {class}`~execution_timer.SectionRecord`.

`total_time`
: Seconds across all top-level sections, as from `get_total_time()`.

`total_category_time`
: Seconds per category, counted like `get_total_category_time()`, sorted by name.

`sections`
: Every section in report order, with its own `name`, its full `path`, its `time` and its
  `category`.

Times are rounded to microseconds. The sections and the totals come from the same
snapshot, so they always agree, and the category totals use the original, unmerged
sections even when `flatten=True` merges counter variants with different categories.

The format suits dashboards and CI artifacts, and it's easy for a language model to read if
you want help interpreting a profile.

## Flattening

Every function on this page except the two totals takes `flatten=`. The default, `True`,
merges `counter` variants of a section; `False` keeps them apart. See {doc}`counters`.
