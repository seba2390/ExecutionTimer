# Overhead benchmarks

From a repository checkout, run:

```bash
uv run python benchmarks/overhead.py --number 100000 --repeat 9
```

The script prints JSON with the Python version, platform, and median nanoseconds per
operation. Recording cases run `--number` operations per repeat. Reporting cases run
`max(1, number // 1000)` operations against 1,000 recorded counter variants with ten
categories. Async calls run in one event loop, so loop startup is excluded.

Compare the same interpreter and machine under similar load, without coverage or a
profiler enabled. These are microbenchmarks, not CI timing thresholds. The no-op bodies
make instrumentation costs visible; application speedups depend on the work being timed.

## Local comparison

Measured on macOS 26.6.2, ARM64, CPython 3.14.5, using 100,000 operations and nine repeats.
The baseline is commit `008494c` (version 0.1.0); the updated column uses version 0.1.1.
Both versions ran the same script. Values below are microseconds per operation and
include the benchmark function call; plain calls cost approximately 0.017 µs and plain
awaits 0.056 µs in both runs.

| Operation | Baseline (µs) | Updated (µs) | Reduction |
| --- | ---: | ---: | ---: |
| New context | 1.550 | 1.028 | 34% |
| Reused context | 1.425 | 0.947 | 34% |
| Decorated call | 1.604 | 1.011 | 37% |
| Decorated await | 1.696 | 1.093 | 36% |
| Five nested contexts | 7.792 | 5.116 | 34% |
| Total time, 1,000 sections | 524.809 | 43.068 | 92% |
| JSON, 1,000 sections | 1,177.635 | 1,005.600 | 15% |
| Disabled logging, 1,000 sections | 520.167 | 0.099 | >99.9% |

Recording keeps each invocation's start time and cached path in a context-local frame.
Decorators reuse their context instead of constructing one per call. Total-time queries
avoid copying and flattening entries, JSON exports share one snapshot, and disabled
logging returns before building a report.
