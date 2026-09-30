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
The baseline is commit `008494c` (version 0.1.0); the updated column is version 1.0.2.
Both versions ran the same script, one after the other. Values below are microseconds per
operation and include the benchmark function call; plain calls cost approximately
0.02 µs and plain awaits 0.06 µs in both runs.

| Operation | Baseline (µs) | Updated (µs) | Reduction |
| --- | ---: | ---: | ---: |
| New context | 1.558 | 1.101 | 29% |
| Reused context | 1.390 | 1.039 | 25% |
| Decorated call | 1.623 | 1.129 | 30% |
| Decorated await | 1.711 | 1.133 | 34% |
| Five nested contexts | 7.961 | 5.380 | 32% |
| Total time, 1,000 sections | 519.131 | 43.188 | 92% |
| JSON, 1,000 sections | 1,235.188 | 1,064.559 | 14% |
| Disabled logging, 1,000 sections | 572.003 | 0.098 | >99.9% |

Recording keeps each invocation's start time and cached path in a context-local frame.
Decorators reuse their context instead of constructing one per call. Total-time queries
avoid copying and flattening entries, JSON exports share one snapshot, and disabled
logging returns before building a report.
