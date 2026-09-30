# API reference

Everything below is importable from `execution_timer`. The public API follows
[semantic versioning](https://semver.org/): it only changes incompatibly in a new major
version.

```python
from execution_timer import TimerContext, get_execution_times_report
```

## Timing

```{eval-rst}
.. autoclass:: execution_timer.TimerContext
   :special-members: __call__

.. py:data:: execution_timer.DEFAULT_CATEGORY
   :type: str
   :value: "default"

   The category of sections created without one.
```

## Reports

```{eval-rst}
.. autofunction:: execution_timer.get_execution_times_report
.. autofunction:: execution_timer.log_execution_times
.. autofunction:: execution_timer.get_execution_timings
.. autofunction:: execution_timer.get_total_time
.. autofunction:: execution_timer.get_total_category_time
```

## JSON export

```{eval-rst}
.. autofunction:: execution_timer.get_execution_times_json
.. autofunction:: execution_timer.save_execution_timings_json
```

## Managing timings and rules

```{eval-rst}
.. autofunction:: execution_timer.clear_execution_timings
.. autofunction:: execution_timer.register_forbidden_nesting
.. autofunction:: execution_timer.clear_forbidden_nesting
```

## Types

These are {class}`~typing.TypedDict` classes: at runtime the values are plain
dictionaries, and the classes exist for type checkers.

```{eval-rst}
.. autoclass:: execution_timer.TimingReport
   :members:

.. autoclass:: execution_timer.TimingsPayload
   :members:

.. autoclass:: execution_timer.SectionRecord
   :members:
```

## Version

```{eval-rst}
.. py:data:: execution_timer.__version__
   :type: str

   The installed version, for example ``"1.0.2"``.
```
