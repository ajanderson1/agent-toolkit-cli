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

| Index collection membership and name collisions once per row snapshot | 2,000-skill toggle median 125.44 ms (range 117.37-128.22); filter/clear 245.42 ms (224.22-275.44) | Toggle medians 20.62 / 20.78 ms; filter/clear 141.47 / 142.79 ms | Keep: about 83% lower toggle and 42% lower filter median. 500-skill toggle now 14.85 ms. |

The collection index holds references to the current rows and is replaced on every
`set_rows`; it never caches filesystem, Git or exposure state. Profiling the
2,000-skill case identified repeated full-inventory collection scans (7,320 calls
across nine rebuilds) before this change.

All six grids still recompute every displayed value. No asset-state cache or
freshness delay is introduced. Changed row ordering, filters, labels or widths
retain the full-rebuild path. Synthetic regression tests guard row reuse and
state/source updates without imposing a machine-dependent timing threshold.
