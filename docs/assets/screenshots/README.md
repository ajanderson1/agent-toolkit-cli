# Documentation screenshot

The README uses `assets/agent-toolkit-cli-tui.png`; the site uses the identical
`tui-overview.png` in this directory. Source SVG is
`assets/agent-toolkit-cli-tui.svg` at repository root.

Reproduce from the checkout:

```bash
uv sync --all-extras
uv run python scripts/capture_docs_tui.py
```

Requires `rsvg-convert` on PATH for PNG rasterization (no new Python dependency).
The script starts a subprocess with disposable HOME/config/library paths **before
importing the application**, asserts CLI/TUI imports resolve into this checkout,
seeds local Git + seven real skill entries, invokes actual source-batch install,
and renders the real Textual app at 150×32 cells. No network, operator assets,
credentials or live configuration are read. The temporary fixture is removed.

Assertions verify one collection, seven real skills, actual Standard links and
two queued changes that have not written to disk. The SVG must include current
sidebar/collection/repository labels and exclude source-checkout/user-home paths.
`tests/test_docs_capture.py` repeats the isolation/media checks when the rasterizer
is installed.

**Visual verdict:** PASS — expanded collection and seven children are legible;
cyan mixed parents differ from yellow pending removal, six plural sidebar labels
are clean, global scope and two pending edits are visible, and REPO/final
`demo-project` component are bold. At this viewport the Source cell clips long
text; Info retains full identity. This is actual UI behavior, not edited media.

The current image was recaptured from the 7.1.0 source UI, not relabeled from a
historical screenshot. Its header shows the installed source package version.
The capture runs headlessly, so automatic package-update checks are suppressed;
no update toast is fabricated or painted into the image. Interactive startup
notification behavior is documented in [the TUI guide](../../agent-toolkit/tui.md#startup-update-notification).
The package version in the header is the source package's current version;
ReleasePlease owns subsequent version changes. Only synthetic `example/workflows`
assets and disposable `/tmp` paths appear. Do not substitute live operator state.
