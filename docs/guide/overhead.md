# Overhead

Timing a section costs about one microsecond on a modern machine: entering and exiting a
`with TimerContext(...)` block, or calling a decorated function. That's negligible for
sections that take milliseconds or more. For code that runs millions of times in a tight
loop, time the loop rather than each iteration, or
[reuse one context](timing-code.md#reusing-a-context).

A few habits keep the cost down:

- **Reuse contexts in hot loops.** Creating a `TimerContext` each time is slightly slower
  than entering an existing one. Decorators already reuse theirs.
- **Keep reporting out of hot paths.** Reports copy the registry under its lock, and the
  JSON export also orders and serializes every section. Read the timings when you need
  them, not on every iteration.
- **Leave `log_execution_times()` in place.** It returns immediately, without building a
  report, when its logger has `INFO` disabled.

## Measuring it yourself

The repository includes a benchmark for recording and reporting costs. From a checkout:

```bash
uv run python benchmarks/overhead.py --number 100000 --repeat 9
```

It prints the median nanoseconds per operation as JSON. Compare results on the same
interpreter and machine, without coverage or a profiler running. See
[`benchmarks/README.md`](https://github.com/seba2390/ExecutionTimer/blob/main/benchmarks/README.md)
for the methodology.

## Reference results

```{include} ../../benchmarks/README.md
:start-after: "## Local comparison"
```
