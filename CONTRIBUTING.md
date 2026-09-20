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

All four must pass. Coverage is enforced at 95%; the current suite has 100% statement
and branch coverage. Preserve coverage when adding or changing behavior.

The test suite is also run against Python 3.12, 3.13 and 3.14 on Linux, macOS and Windows.
To check another interpreter locally:

```bash
uv run --python 3.12 pytest
```

For changes to recording or reporting performance, compare the benchmark on the same
machine and Python version, without coverage instrumentation:

```bash
uv run python benchmarks/overhead.py --number 100000 --repeat 9
```

See [benchmarks/README.md](benchmarks/README.md) for methodology and reference results.
Timing results are advisory rather than CI pass/fail thresholds.

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
2. Bump `__version__` in `src/execution_timer/__init__.py`, then run `uv lock --check`
   to verify the lockfile. Package metadata reads the version from `__version__`.
3. Run the checks above, build with `uv build`, and validate metadata with
   `uvx twine check --strict dist/*`. Use a clean output directory so old versions are
   not included in release artifacts.
4. Commit, then push to `main` and wait for CI to pass.
5. Publish a GitHub release tagged `vX.Y.Z`, targeting the validated commit on `main`.
   Use that version's changelog entries as release notes.

The [Publish to PyPI workflow](.github/workflows/publish.yml) runs when a GitHub release
is **published**. Pushing to `main`, pushing a tag alone, or saving a draft release does
not trigger it. The workflow builds and validates the distributions, checks that the tag
matches `__version__`, and uploads them to PyPI via Trusted Publishing. No manual
`twine upload` or PyPI API token is needed. If the `pypi` GitHub environment requires
approval, approve the publishing job there.

After publishing the release, check that the workflow succeeds and the new version
appears on [PyPI](https://pypi.org/project/executiontimer/).
