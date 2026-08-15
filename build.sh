#!/usr/bin/env bash
# Build the wheel + sdist into dist/ for local installation in other repos.
set -euo pipefail

cd "$(dirname "$0")"
rm -rf dist
uv build
echo ""
echo "Built artifacts:"
ls -1 dist
echo ""
echo "Install into another project with:"
echo "  uv pip install $(pwd)/dist/execution_timer-$(uv version --short 2>/dev/null || echo '0.1.0')-py3-none-any.whl"
echo "or add to another project's pyproject dependencies:"
echo "  execution-timer @ file://$(pwd)/dist/execution_timer-0.1.0-py3-none-any.whl"
