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

All four must pass. The suite has 100% statement and branch coverage, and CI enforces it.
Any warning raised during the tests fails them.

The test suite is also run against Python 3.11, 3.12, 3.13, 3.14 and free-threaded 3.14t
on Linux, macOS and Windows.
To check another interpreter locally:

```bash
uv run --python 3.11 pytest
```

For changes to recording or reporting performance, compare the benchmark on the same
machine and Python version, without coverage instrumentation:

```bash
uv run python benchmarks/overhead.py --number 100000 --repeat 9
```

See [benchmarks/README.md](https://github.com/seba2390/ExecutionTimer/blob/main/benchmarks/README.md) for methodology and reference results.
Timing results are advisory rather than CI pass/fail thresholds.

## Documentation

The documentation site is built with [Sphinx](https://www.sphinx-doc.org/) from the
Markdown pages in `docs/` and the docstrings in `src/`. To build and preview it:

```bash
uv run --group docs sphinx-build -M html docs docs/_build -W --keep-going -n
```

Then open `docs/_build/html/index.html`. CI builds the site on every pull request and fails
on any warning, such as a broken cross-reference. Changes merged into `main` are published
to [GitHub Pages](https://seba2390.github.io/ExecutionTimer/) automatically.

The Python examples in `docs/` and `README.md` run as part of the test suite, so keep them
self-contained and runnable.

## Guidelines

- Tests exercise the **public API** only — import from `execution_timer`, not
  `execution_timer._timer`. This keeps internals free to change.
- Every behaviour change needs a test that fails before the fix and passes after it.
- Public functions carry type annotations and a one-line docstring.
- Add an entry under `## [Unreleased]` in [CHANGELOG.md](https://github.com/seba2390/ExecutionTimer/blob/main/CHANGELOG.md).

## Releasing

Maintainers only:

1. Move the `## [Unreleased]` entries into a new version section in `CHANGELOG.md`, and
   update the link definitions at the bottom.
2. Bump `__version__` in `src/execution_timer/__init__.py`, then run `uv lock --check`
   to verify the lockfile. Package metadata reads the version from `__version__`.
3. Run the checks above, build with `uv build`, and validate metadata with
   `uvx twine check --strict dist/*`. Use a clean output directory so old versions are
   not included in release artifacts.
4. Commit on a branch and open a pull request. `main` is protected: it only accepts
   pull requests whose `CI passed` check succeeds. Squash-merge once CI is green.
5. Publish a GitHub release tagged `vX.Y.Z`, targeting the merged commit on `main`.
   Use that version's changelog entries as release notes.

The [Publish to PyPI workflow](https://github.com/seba2390/ExecutionTimer/blob/main/.github/workflows/publish.yml) runs when a GitHub release
is **published**. Pushing to `main`, pushing a tag alone, or saving a draft release does
not trigger it. The workflow builds and validates the distributions, checks that the tag
matches `__version__`, and uploads them to PyPI via Trusted Publishing. No manual
`twine upload` or PyPI API token is needed. If the `pypi` GitHub environment requires
approval, approve the publishing job there.

After publishing the release, check that the workflow succeeds and the new version
appears on [PyPI](https://pypi.org/project/executiontimer/).
