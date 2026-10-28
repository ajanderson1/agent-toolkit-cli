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

| Background inventory loading with latest-read-wins publication | Injected 250 ms read blocks the tab handler for 254 ms | Tab handler returns under 100 ms and filter remains usable, but 57 TUI tests fail | Reverted: pending-queue, cross-kind Save and startup races violate correctness. No background inventory changes retained. |

The collection index holds references to the current rows and is replaced on every
`set_rows` and visible-row calculation (one linear pass, preserving mutable row
metadata); it never caches filesystem, Git or exposure state. Profiling the
2,000-skill case identified repeated full-inventory collection scans (7,320 calls
across nine rebuilds) before this change.

## Final verification timings

A later run had substantially higher host load, so the committed baseline and
final implementation were measured in alternating fresh processes with the same
benchmark, seven samples each. The baseline grid module was loaded from
`f96cd0e` into the same interpreter environment; no user checkout files were
changed. The current shared helper has no effect on the baseline grid, which
still calls `clear` / `add_row` directly. These final numbers include refreshing
the collection index per visible-row calculation to preserve mutable metadata.

| Skills | Baseline toggle medians | Final toggle medians | Baseline filter/clear medians | Final filter/clear medians |
| --- | --- | --- | --- | --- |
| 500 | 76.96 / 79.42 ms | 27.46 / 26.34 ms | 87.02 / 84.32 ms | 59.75 / 54.84 ms |
| 2,000 | 442.83 / 433.11 ms | 64.61 / 68.66 ms | 452.59 / 475.53 ms | 304.01 / 363.93 ms |

Toggle medians improve by about 65-67% at 500 skills and 84-85% at 2,000.
Filter/clear improves by 31-35% and 23-33%, respectively. The larger filter case
still exceeds a 200 ms interaction target; it is not claimed solved. Individual
outliers are noisy under host load, so these are local median results, not p95
latency guarantees. Inventory reads and Apply remain synchronous; their stalls
are a separate unresolved bottleneck, not hidden by dropping validation.

All six grids still recompute every displayed value. No asset-state cache or
freshness delay is introduced. Changed row ordering, filters, labels or widths
retain the full-rebuild path. Synthetic regression tests guard row reuse and
state/source updates without imposing a machine-dependent timing threshold.

Final correctness gate: `uv run pytest -q` reports **3,341 passed, 11 skipped**
(existing skips; no tests were disabled). `uv build` and strict
`make docs-build` pass. A temporary mutation disabling the in-place update path
fails eight regression tests, including all six grids; the original file was
restored byte-for-byte afterward. Runtime checks use Textual's headless Pilot;
no claim of an attended terminal or real-user performance study is made.

## Integration review against main

The benchmark now explicitly expands the synthetic inventory and selects a child
before timing. This keeps its workload consistent after collections became
collapsed by default in #561. A regression checks that twenty children plus two
parents are rendered and each toggle changes exactly one child's pending state.

After integrating main `1f55fbc`, a fresh-process baseline using that commit's
grid and the same benchmark was compared with the integrated implementation
(seven samples each; no checkout files modified):

| Skills | Main toggle median | Integrated toggle median | Main filter/clear median | Integrated filter/clear median |
| --- | --- | --- | --- | --- |
| 500 | 43.98 ms | 15.30 ms | 48.38 ms | 33.55 ms |
| 2,000 | 228.85 ms | 20.01 ms | 237.47 ms | 131.98 ms |

These remain local headless medians, not real-user p95 guarantees. The full gate
is rerun for the integrated PR; the 3,341-test result above describes the original
pre-integration branch. Review also verified current collection defaults,
Right-arrow navigation, literal Info facts, catalogue status and source widths.
