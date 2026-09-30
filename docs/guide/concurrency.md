# Threads, asyncio and generators

`executiontimer` is safe to use from any number of threads and asyncio tasks, including on
free-threaded Python builds. This page explains how sections from concurrent code nest and
add up.

## How it works

Two pieces of state are involved:

- **The registry** of recorded timings is shared by the whole process and guarded by a
  lock. Every thread and task records into it, so everything lands in one report.
- **The active stack**, the list of currently open sections that decides where a new
  section nests, lives in a {class}`~contextvars.ContextVar`. Each thread and each asyncio
  task has its own, so concurrent code doesn't nest into each other's sections.

## asyncio tasks

Each task nests its sections independently. A task inherits the stack of the code that
created it, so its sections appear under the section that was open at that point:

```python
import asyncio

from execution_timer import TimerContext, get_execution_timings


@TimerContext("fetch", category="io")
async def fetch(delay: float) -> None:
    await asyncio.sleep(delay)


async def worker(n: int) -> None:
    with TimerContext(f"worker{n}"):
        await fetch(0.01)


async def main() -> None:
    with TimerContext("main"):
        await asyncio.gather(worker(0), worker(1))


asyncio.run(main())

assert set(get_execution_timings()) == {
    ("main",),
    ("main", "worker0"),
    ("main", "worker0", "fetch"),
    ("main", "worker1"),
    ("main", "worker1", "fetch"),
}
```

Await child tasks inside the parent section if you want the parent's time to include
them. A task that is still running when its parent section exits is recorded under it all
the same.

## Threads

New threads do **not** inherit the active stack. Sections recorded in a thread appear at the
top level of the report, and their time is added to the total alongside the section that
started the thread:

```python
from concurrent.futures import ThreadPoolExecutor

from execution_timer import clear_execution_timings

clear_execution_timings()


@TimerContext("download")
def download(n: int) -> int:
    return n


with TimerContext("batch"), ThreadPoolExecutor() as pool:
    list(pool.map(download, range(4)))  # recorded as ("download",), not ("batch", "download")
```

To nest thread work under the current section, run it in a copy of the current context
with {func}`contextvars.copy_context`, or use {func}`asyncio.to_thread`, which does that for
you:

```python
import contextvars

clear_execution_timings()

with TimerContext("batch"), ThreadPoolExecutor() as pool:
    context = contextvars.copy_context()
    pool.submit(context.run, download, 1).result()

assert ("batch", "download") in get_execution_timings()
```

On free-threaded builds of Python 3.14, new threads inherit the context by default, so
thread sections nest without extra work.

## Overlapping calls add up

When calls to the same section overlap, from several threads or tasks, each call keeps its
own start time and their durations are added together. Such a total measures accumulated
time and can exceed the wall-clock time. In the asyncio example above, two overlapping
10 ms `fetch` calls would add up to about 20 ms if they shared a path. Give concurrent work
distinct names, or use `counter=`, to report each call separately.

## Generators

A generator runs in the context of whoever is iterating it. A section left open across a
`yield` therefore also contains whatever the caller times while the generator is paused,
and its time includes the pause. Close sections before yielding:

```python
def rows():
    for i in range(3):
        with TimerContext("parse_row"):
            row = i * 2  # timed
        yield row  # not timed: the section is closed


with TimerContext("import"):
    for row in rows():
        pass
```

If a section is still open in a paused generator when the caller's section exits, the timer
emits a {class}`RuntimeWarning`, records the caller's section, and discards the generator's
unfinished section so later sections still nest correctly. Closing the generator afterwards
does nothing. The timer never raises from exiting a section, so it can't replace an
exception that is already propagating. Under warnings-as-errors, the warning is raised only
after this cleanup.
