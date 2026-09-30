# executiontimer

**Hierarchical execution timing for Python.** Time named sections of your code with a
`with` block or a decorator. Sections nested inside each other form a tree, so you see
where the time actually went, not just one number at the end.

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
Total time: 312.838 ms.

load_data: 124.682 ms (39.85%)
solve: 188.157 ms (60.15%)
..  step: 154.718 ms (49.46%)
..  postprocess: 33.295 ms (10.64%)
```

## Why executiontimer

A profiler tells you which *functions* are slow. `executiontimer` tells you which
*parts of your program* are slow, in the terms you choose: "load data", "solve", "write
results". It's for the numbers you'd otherwise collect with `time.perf_counter()` calls
scattered through your code, kept in one place and reported as a tree.

- **One primitive.** {class}`~execution_timer.TimerContext` is both a context manager and
  a decorator.
- **Automatic hierarchy.** Nesting `with` blocks or decorated calls nests the report. There
  is nothing to wire up.
- **Categories.** Tag sections with any string, such as `"io"`, `"gpu"` or `"db"`, and get
  a total per category.
- **Async and threads.** Decorating an `async def` times the whole `await`. Each thread and
  asyncio task keeps its own nesting, and everything lands in one report.
- **Loop counters.** Time each iteration separately, then merge the iterations back
  together in the report.
- **Exports.** A text report, a log record, a dictionary, or a JSON document for
  dashboards, CI artifacts or a language model.
- **Small and dependable.** No dependencies, fully typed, about one microsecond of overhead
  per section, tested on Linux, macOS and Windows with Python 3.11 to 3.14, including
  free-threaded builds.

## Install

```bash
pip install executiontimer
```

The install name is `executiontimer` and the import name is `execution_timer`.
{doc}`getting-started` covers the rest.

```{toctree}
:hidden:

getting-started
```

```{toctree}
:caption: User guide
:hidden:

guide/timing-code
guide/counters
guide/categories
guide/reports
guide/concurrency
guide/long-running
guide/overhead
```

```{toctree}
:caption: Reference
:hidden:

api
changelog
contributing
GitHub <https://github.com/seba2390/ExecutionTimer>
PyPI <https://pypi.org/project/executiontimer/>
```
