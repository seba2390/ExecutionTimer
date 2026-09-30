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
  <a href="https://seba2390.github.io/ExecutionTimer/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-4F46E5" alt="Documentation"></a>
</p>

Time named sections of your code with a `with` block or a decorator. Sections nested inside
each other form a tree, so you see where the time actually went, not just one number at the
end.

Zero dependencies. Fully typed. Works with threads and `asyncio`.

## Documentation 
[seba2390.github.io/ExecutionTimer](https://seba2390.github.io/ExecutionTimer/)

## Installation

```bash
pip install executiontimer
```

Requires Python 3.11+. The install name is `executiontimer`; the import name is
`execution_timer`.

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
Total time: 0.3156 s.

load_data: 0.1219 s (38.62%)
solve: 0.1937 s (61.38%)
..  step: 0.1585 s (50.24%)
..  postprocess: 0.0350 s (11.10%)
```

`TimerContext` also works as a decorator, including on `async def` functions:

```python
@TimerContext("preprocess")
def preprocess(rows: list[str]) -> list[str]:
    return [row.strip() for row in rows]
```

## Learn more

- [Getting started](https://seba2390.github.io/ExecutionTimer/getting-started.html)
- User guide: [timing code](https://seba2390.github.io/ExecutionTimer/guide/timing-code.html),
  [counters](https://seba2390.github.io/ExecutionTimer/guide/counters.html),
  [categories](https://seba2390.github.io/ExecutionTimer/guide/categories.html),
  [reports and JSON export](https://seba2390.github.io/ExecutionTimer/guide/reports.html),
  [threads, asyncio and generators](https://seba2390.github.io/ExecutionTimer/guide/concurrency.html)
- [API reference](https://seba2390.github.io/ExecutionTimer/api.html)
- [Changelog](https://github.com/seba2390/ExecutionTimer/blob/main/CHANGELOG.md) and
  [contributing guide](https://github.com/seba2390/ExecutionTimer/blob/main/CONTRIBUTING.md)

## License

MIT — see [LICENSE](https://github.com/seba2390/ExecutionTimer/blob/main/LICENSE).
