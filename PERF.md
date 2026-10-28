# TUI responsiveness experiments

## Method

`uv run python scripts/benchmark_tui.py --rows 500 --samples 7`

The headless Textual benchmark uses synthetic skills (ten children per collection),
never the real HOME or asset stores. It measures a child checkbox toggle and a
filter/clear pair, including queued screen work. Run the same command repeatedly;
compare medians and ranges, not profiler-instrumented timings. Measurements here
use Python 3.13.5 / Textual 8.2.8 on the development Mac. This is a reproducible
interaction benchmark, not a claim about end-to-end performance on every machine.
Use `--profile /tmp/tui.prof` for cProfile attribution, not comparative timings.

## Attempts

| Attempt | Before | After | Decision |
| --- | --- | --- | --- |
| Update table cells in place when row keys and column schema match | 500-skill toggle medians 44.88 / 47.33 ms (range 35.15-65.88) | 19.54 / 20.36 ms (range 10.18-21.45) | Keep: 55-58% lower median; 746 TUI tests pass. |

All six grids still recompute every displayed value. No asset-state cache or
freshness delay is introduced. Changed row ordering, filters, labels or widths
retain the full-rebuild path. Synthetic regression tests guard row reuse and
state/source updates without imposing a machine-dependent timing threshold.
