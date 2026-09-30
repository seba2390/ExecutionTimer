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

Whether a new thread starts inside the section that started it depends on the Python build:

- **Regular builds**, including Python 3.14, start each new thread with an empty stack.
  Sections recorded in the thread appear at the top level of the report, and their time
  is added to the total alongside the section that started the thread.
- **Free-threaded builds of Python 3.14** start each new thread with a copy of the context
  of the code that called {meth}`~threading.Thread.start`. Sections recorded in the thread
  nest under the section that was open at that moment.

Python's `-X thread_inherit_context` option switches between the two on any 3.14 build,
and `sys.flags.thread_inherit_context` reports which one is in effect.

### Thread pools

The difference matters most for thread pools, because a pool reuses its threads.
{class}`~concurrent.futures.ThreadPoolExecutor` starts a worker thread when work is
submitted and keeps it for later work. On a free-threaded build, the worker keeps the
stack it started with for as long as it lives, so work submitted later, from a different
section or from none, still nests under the section that was open when the worker started.
On a regular build, the same work is recorded at the top level.

To get the same report on every build, pick the context for each call yourself. To nest
thread work under the current section, run each call in a fresh copy of the current
context from {func}`contextvars.copy_context`:

```python
import contextvars
from concurrent.futures import ThreadPoolExecutor

from execution_timer import clear_execution_timings

clear_execution_timings()


@TimerContext("download")
def download(n: int) -> int:
    return n


with ThreadPoolExecutor(max_workers=2) as pool:
    with TimerContext("batch"):
        futures = [pool.submit(contextvars.copy_context().run, download, n) for n in range(4)]
        results = [future.result() for future in futures]
    with TimerContext("retry"):
        pool.submit(contextvars.copy_context().run, download, 0).result()

timings = get_execution_timings()
assert ("batch", "download") in timings
assert ("retry", "download") in timings
assert ("download",) not in timings
```

Copy the context for every call rather than once per section: a context can't be entered
by two threads at the same time. {func}`asyncio.to_thread` copies the context for you.

To keep thread work at the top level on every build, run each call in a new, empty
{class}`~contextvars.Context` instead:

```python
clear_execution_timings()

with ThreadPoolExecutor(max_workers=2) as pool, TimerContext("batch"):
    pool.submit(contextvars.Context().run, download, 1).result()

timings = get_execution_timings()
assert ("download",) in timings
assert ("batch", "download") not in timings
```

The same works for a plain thread: pass `target=contextvars.copy_context().run` or
`target=contextvars.Context().run`, followed by the function and its arguments in `args`.

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
