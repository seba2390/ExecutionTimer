# Counters and flattening

Pass `counter=` to time the iterations of a loop as separate sections. The section is
recorded as `name[counter]`:

```python
import time

from execution_timer import TimerContext, get_execution_timings

with TimerContext("solve"):
    for i in range(3):
        with TimerContext("step", counter=i):
            time.sleep(0.01 * (i + 1))
```

## Merged or separate

Every function that reads timings takes a `flatten` argument. With the default,
`flatten=True`, counter variants are merged back into one section and their times added
up. With `flatten=False`, each iteration stays separate:

```python
merged = get_execution_timings()  # flatten=True
separate = get_execution_timings(flatten=False)

assert list(merged) == [("solve",), ("solve", "step")]
assert list(separate) == [("solve",), ("solve", "step[0]"), ("solve", "step[1]"), ("solve", "step[2]")]
```

The same applies to the text report:

```python
from execution_timer import get_execution_times_report

print(get_execution_times_report(flatten=False))
```

```text
Total time: 0.0724 s.

solve: 0.0724 s (100.00%)
..  step[0]: 0.0125 s (17.31%)
..  step[1]: 0.0250 s (34.60%)
..  step[2]: 0.0347 s (47.97%)
```

Use the separate view to find a slow iteration, and the merged view to see the loop's
share of the whole run.

## What flattening merges

Flattening removes a final integer suffix in brackets from every name in the path,
including negative counters such as `step[-1]`. Other bracketed names are kept:
`array[index]` and `cache[]` are left alone.

Flattening can't tell a counter from a name you wrote yourself, so sections you named
`"row[1]"` and `"row[2]"` are merged into `row` too. Use `flatten=False` to keep them
apart, or pick names without a trailing `[number]`.

If merged variants have different categories, the merged section takes the category of the
most recently entered one. Category totals are computed before merging, so they stay
correct either way.

## Counters and memory

Each counter value is a separate section until you call
{func}`~execution_timer.clear_execution_timings`. A long-running process that times an
unbounded loop with `counter=` keeps adding entries. Either clear the timings periodically
(see {doc}`long-running`) or drop `counter=` so the iterations accumulate into one section.
