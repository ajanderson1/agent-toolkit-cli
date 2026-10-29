#!/usr/bin/env bash
# No publishing or operator-state access. Keep all reproducible gates here.
set -euo pipefail
uv sync --locked --all-extras --python 3.14
uv run --locked pytest -q
DISABLE_MKDOCS_2_WARNING=true uv run --locked mkdocs build --strict
uv build
