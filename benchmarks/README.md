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
The baseline is commit `008494c` (version 0.1.0). All three versions ran the same script,
one after the other. Values below are microseconds per operation and include the benchmark
function call; plain calls cost approximately 0.02 µs and plain awaits 0.06 µs in every
run. The last column compares 1.0.3 with the baseline.

| Operation | 0.1.0 (µs) | 1.0.2 (µs) | 1.0.3 (µs) | Reduction |
| --- | ---: | ---: | ---: | ---: |
| New context | 1.604 | 1.116 | 0.877 | 45% |
| Reused context | 1.433 | 1.013 | 0.786 | 45% |
| Decorated call | 1.656 | 1.220 | 0.897 | 46% |
| Decorated await | 1.800 | 1.197 | 0.948 | 47% |
| Five nested contexts | 8.238 | 5.782 | 4.371 | 47% |
| Total time, 1,000 sections | 522.668 | 43.786 | 43.630 | 92% |
| JSON, 1,000 sections | 1,255.098 | 1,139.416 | 1,065.708 | 15% |
| Disabled logging, 1,000 sections | 530.408 | 0.100 | 0.100 | >99.9% |

Recording keeps each invocation's start time and cached path in a context-local frame,
stored as a plain tuple because a named tuple's constructor costs more than the rest of
entering a section. Decorators reuse their context instead of constructing one per call.
Total-time queries avoid copying and flattening entries, JSON exports share one snapshot,
and disabled logging returns before building a report.
