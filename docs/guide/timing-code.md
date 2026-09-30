# Timing code

Everything is timed with one class, {class}`~execution_timer.TimerContext`. This page
covers the ways to use it.

## With a `with` block

```python
import time

from execution_timer import TimerContext

with TimerContext("load_data"):
    time.sleep(0.01)
```

The section's time is added when the block exits, even if the block raises. The exception
propagates as usual; the timer never swallows or replaces it.

```python
from execution_timer import get_execution_timings

try:
    with TimerContext("risky"):
        raise ValueError("bad input")
except ValueError:
    pass

assert ("risky",) in get_execution_timings()
```

## As a decorator

Decorating a function times every call to it and adds them all up in one section:

```python
@TimerContext("preprocess")
def preprocess(rows: list[str]) -> list[str]:
    return [row.strip() for row in rows]


preprocess([" a ", " b "])
```

The decorated function keeps its name, docstring, signature and return value. A decorated
call made inside another section nests under it, exactly like a `with` block.

### Async functions

Decorating an `async def` times the whole `await`, including everything the coroutine
awaits along the way, not just the creation of the coroutine object:

```python
import asyncio


@TimerContext("fetch", category="io")
async def fetch(delay: float) -> str:
    await asyncio.sleep(delay)
    return "payload"


asyncio.run(fetch(0.01))
```

This also works when another decorator sits between `TimerContext` and the `async def`, as
long as that decorator returns the coroutine, like most retry, caching and tracing
decorators do:

```python
import functools


def logged(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper


@TimerContext("fetch_logged", category="io")
@logged
async def fetch_logged() -> None:
    await asyncio.sleep(0.01)


asyncio.run(fetch_logged())
```

The section then covers both the call and the `await`.

### Generator functions can't be decorated

Decorating a generator function, or an async generator function, raises `TypeError`. A
wrapper could only time creating the generator object, which takes microseconds however
long the iteration takes. Time the loop that consumes the generator instead:

```python
def numbers(n: int):
    for i in range(n):
        yield i * i


with TimerContext("consume_numbers"):
    total = sum(numbers(1_000))
```

{doc}`concurrency` explains what happens to sections opened *inside* a generator.

## Reusing a context

A `TimerContext` holds no timing state of its own; the registry does. So one context can be
used any number of times, nested inside itself, or shared between threads and tasks. In a
tight loop, create it once:

```python
step_timer = TimerContext("step")

for item in range(100):
    with step_timer:
        _ = item * item
```

A decorator already works this way: it creates one context and reuses it for every call.

## Repeated and recursive calls

Entering the same section again, at the same place in the tree, adds to its total. The
report shows one line with the accumulated time.

Recursion is different: each level runs *inside* the previous one, so each level is a new,
deeper section. A recursive function decorated with `TimerContext` shows one line per
depth:

```python
from execution_timer import clear_execution_timings, get_execution_times_report

clear_execution_timings()


@TimerContext("walk")
def walk(depth: int) -> None:
    time.sleep(0.01)
    if depth:
        walk(depth - 1)


walk(2)
print(get_execution_times_report())
```

```text
Total time: 0.0354 s.

walk: 0.0354 s (100.00%)
..  walk: 0.0247 s (69.77%)
..  ..  walk: 0.0125 s (35.38%)
```

For deep recursion, time the top-level call only, for example with a `with` block around
it.

## Names and paths

A section is identified by its **path**: the names of the enclosing sections followed by its
own name. In reports and in {func}`~execution_timer.get_execution_timings`, the section
above is `("walk", "walk")`, and `step` inside `solve` is `("solve", "step")`. Two sections
with the same name in different places are separate entries.
