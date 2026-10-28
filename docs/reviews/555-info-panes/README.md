# #555 Info-pane visual verification

These paired SVG captures are real Textual `run_test` exports at wide **110×32**
and narrow **58×20** terminal sizes. They use only a controlled temporary
`atk-555-info-…` fixture HOME/project and synthetic sources; no operator assets,
configuration, network, or credentials are read. Full technical details
intentionally show controlled temporary fixture paths where needed; operator home
paths are excluded.

`before/` was captured before the first source edit from canonical
`origin/main` **f96cd0e**. `after/` was captured from this change using the same
case names and sizes. `scripts/capture_issue_555_info_panes.py` regenerates the
short, long, local, library, and catalogue after-captures through production
`SkillGrid.action_info` with a disposable fixture. The runtime cases cover short and long source-backed
assets, local ownership/removal guidance, library and catalogue information,
and Pi Extension/NPM column help.

| Case | Visual result after #555 |
| --- | --- |
| `short`, `long` | At-a-glance facts lead; long identifiers have a compact source fact and full Technical details. |
| `local`, `local-actions` | Source ownership is structured at the top; the scrolled capture shows the distinct manual command, destructive warning, and full technical path. |
| `library`, `catalogue` | Availability and update/source details are labelled rather than joined into one wall. |
| `pi`, `npm` | Pi help separates origin/availability, mixed-entrypoint meaning, shortcuts, and update guidance. |

All panes show `↑/↓ or PgUp/PgDn scroll` plus their close keys in the footer.
SVG rather than rasterized PNG is retained so reviewers can inspect exact
terminal text and wrapping. This review evidence directory is excluded from the
public MkDocs site.
