# Contributing

Thanks for taking the time to contribute.

## Getting set up

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/seba2390/ExecutionTimer.git
cd ExecutionTimer
uv sync
```

## Before opening a pull request

Run the same checks CI runs:

```bash
uv run pytest --cov
uv run ruff check --fix
uv run ruff format
uv run basedpyright
```

All four must pass. Coverage is enforced at 95%.

The test suite is also run against Python 3.12, 3.13 and 3.14 on Linux, macOS and Windows.
To check another interpreter locally:

```bash
uv run --python 3.12 pytest
```

## Guidelines

- Tests exercise the **public API** only — import from `execution_timer`, not
  `execution_timer._timer`. This keeps internals free to change.
- Every behaviour change needs a test that fails before the fix and passes after it.
- Public functions carry type annotations and a one-line docstring.
- Add an entry under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

## Releasing

Maintainers only:

1. Move the `## [Unreleased]` entries into a new version section in `CHANGELOG.md`, and
   update the link definitions at the bottom.
2. Bump `__version__` in `src/execution_timer/__init__.py`.
3. Commit, then push to `main` and wait for CI to pass.
4. Create a GitHub release tagged `vX.Y.Z`.

Publishing to PyPI happens automatically from `.github/workflows/publish.yml` via Trusted
Publishing. The workflow refuses to publish if the tag and `__version__` disagree.
