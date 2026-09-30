# Long-running processes

Timings accumulate until you clear them. That suits scripts and batch jobs, which report
once at the end. Services, workers and training loops that run for hours usually want a
report per interval instead.

## Report and clear periodically

Log the report, then call {func}`~execution_timer.clear_execution_timings` to start the
next interval from zero:

```python
import time

from execution_timer import TimerContext, clear_execution_timings, log_execution_times

for batch in range(6):
    with TimerContext("handle_batch"):
        time.sleep(0.001)

    if batch % 3 == 2:  # every three batches
        log_execution_times()
        clear_execution_timings()
```

This also keeps memory bounded when you time loops with `counter=`, since each counter
value is a separate section until the next clear.

## Clearing while sections are open

You can clear from inside an open section, for example from inside the loop's own
section. The active sections keep nesting correctly, but their samples are discarded: a
section that was already open during the clear isn't recorded when it exits. Sections
started after the clear are recorded normally. If their parent section was open during the
clear, they appear as top-level sections and count toward the total.

```python
from execution_timer import get_execution_timings

clear_execution_timings()

with TimerContext("service"):
    with TimerContext("tick"):  # discarded by the clear below
        time.sleep(0.001)
    clear_execution_timings()  # "service" is still open
    with TimerContext("tick"):  # recorded
        time.sleep(0.001)

# "service" was open during the clear, so only the second "tick" is recorded.
assert list(get_execution_timings()) == [("service", "tick")]
```

The second `tick` keeps its full path, `("service", "tick")`, but reports treat it as a
top-level section because `service` has no recorded time.

## What is and isn't included

Reports include completed sections only. A section's time is added when it exits, so a
section that is still running contributes nothing yet. Nesting rules from
{func}`~execution_timer.register_forbidden_nesting` survive a clear; remove them with
{func}`~execution_timer.clear_forbidden_nesting`.
