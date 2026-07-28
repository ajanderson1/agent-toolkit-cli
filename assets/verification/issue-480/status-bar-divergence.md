# Visual-verification divergence — #480 R6

**Requirement:** malformed settings must show a visible, named status-bar notice.

**Observed:** the initial visual capture showed no notice despite the `Static` render value containing the diagnostic. Focused red regression (`status-bar-red.txt`) measured `#status-bar` at one row.

**Root cause:** `#status-bar` had `height: 1` and a top border; the border consumed its only row.

**Resolution:** change only `#status-bar` to `height: 2` (one border row plus one text row). `status-bar-green.txt` passes; `tui-suite-after-status-fix.txt` passes; refreshed `malformed-settings-notice.png` visibly shows the named malformed-JSON notice.

**Scope:** CSS layout correction only; no settings schema, persistence, CLI, or dependency behavior changed.
