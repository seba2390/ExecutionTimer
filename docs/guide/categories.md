# Categories

A category is any string you attach to a section to group it with others, such as `"io"`,
`"gpu"`, `"db"` or `"cpu"`. Sections without one get
{data}`~execution_timer.DEFAULT_CATEGORY`, `"default"`.

```python
import time

from execution_timer import TimerContext, get_execution_timings, get_total_category_time

with TimerContext("train"):
    with TimerContext("load_batch", category="io"):
        time.sleep(0.02)
    with TimerContext("forward", category="gpu"):
        time.sleep(0.03)
    with TimerContext("save_checkpoint", category="io"):
        time.sleep(0.01)

timings = get_execution_timings()
io_sections = timings["train", "load_batch"]["time"] + timings["train", "save_checkpoint"]["time"]
assert get_total_category_time("io") == io_sections
```

## How category totals are counted

{func}`~execution_timer.get_total_category_time` adds up the **top-most** section of the
category along each branch. A section nested inside another section of the same category
is already part of that section's time, so it isn't counted again:

```python
from execution_timer import clear_execution_timings

clear_execution_timings()

with TimerContext("query", category="db"):
    time.sleep(0.01)
    with TimerContext("fetch_rows", category="db"):  # already inside "query"
        time.sleep(0.02)

# Only "query" counts; "fetch_rows" is already part of its time.
assert get_total_category_time("db") == get_execution_timings()[("query",)]["time"]
```

Sections of other categories in between don't change this. A `db` section inside an `io`
section inside another `db` section still counts only once.

A category with no sections totals `0.0`. The JSON export includes every category's total
in one go; see {doc}`reports`.

## One category per section

Repeated entries of the same section add to one total. If you enter the same path with a
different category, the latest category applies to the section's *whole* accumulated time.
Keep one category per section path if you need the totals to stay apart.

## Forbidding a nesting

Some combinations are mistakes, for example CPU-side work inside a section meant to
measure pure GPU time. {func}`~execution_timer.register_forbidden_nesting` turns them into
an error at the moment they happen:

```python
from execution_timer import clear_forbidden_nesting, register_forbidden_nesting

register_forbidden_nesting(outer="gpu", inner="cpu")

try:
    with TimerContext("kernel", category="gpu"):
        with TimerContext("reduce", category="cpu"):
            pass
except ValueError as error:
    print(error)
```

```text
Category 'cpu' is not allowed inside category 'gpu'.
```

Entering the inner section raises {class}`ValueError`, and the inner section isn't
recorded. Only the direct parent is checked: a `cpu` section inside an `io` section inside
a `gpu` section is allowed.

Rules apply to the whole process and persist until you call
{func}`~execution_timer.clear_forbidden_nesting`. Clearing the timings leaves the rules in
place.

```python
clear_forbidden_nesting()
```
