"""Versioned, TUI-only user settings persistence (#480).

The CLI intentionally does not read this module or its JSON file. Settings are
loaded by the Textual app and filter presentation only.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile

from agent_toolkit_tui.composition import MAIN_HARNESSES

SCHEMA = "agent-toolkit-tui-settings/v1"
DEFAULT_THEME = "gruvbox"
_ENV_VAR = "AGENT_TOOLKIT_TUI_SETTINGS"


@dataclass(frozen=True)
class TuiSettings:
    """Validated settings plus retained forward-compatibility state."""

    theme: str = DEFAULT_THEME
    harnesses: tuple[str, ...] = MAIN_HARNESSES
    unknown_harnesses: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


def default_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the settings path, honouring the explicit environment override."""

    environ = os.environ if env is None else env
    override = environ.get(_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".agent-toolkit" / "tui-settings.json"


def _defaults(*diagnostics: str) -> TuiSettings:
    return TuiSettings(diagnostics=tuple(diagnostics))


def load(
    *,
    available_themes: Collection[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> TuiSettings:
    """Load and validate settings.

    Missing files are normal. Invalid user data returns defaults plus a loud
    diagnostic. Genuine filesystem failures other than absence propagate so
    the app can surface them as operational errors rather than misclassifying
    them as malformed data.
    """

    path = default_path(env)
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return _defaults()

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as exc:
        return _defaults(f"{path}: malformed JSON ({exc})")

    if not isinstance(payload, dict):
        return _defaults(f"{path}: settings root must be a JSON object")

    schema = payload.get("schema")
    if schema != SCHEMA:
        return _defaults(
            f"{path}: unsupported schema {schema!r}; expected {SCHEMA!r}"
        )

    theme = payload.get("theme")
    harnesses = payload.get("harnesses")
    if not isinstance(theme, str):
        return _defaults(f"{path}: field 'theme' must be a string")
    if not isinstance(harnesses, list) or not all(
        isinstance(harness, str) for harness in harnesses
    ):
        return _defaults(f"{path}: field 'harnesses' must be a list of strings")

    diagnostics: list[str] = []
    chosen_theme = theme
    if available_themes is not None and theme not in available_themes:
        chosen_theme = DEFAULT_THEME
        diagnostics.append(
            f"{path}: theme {theme!r} is unavailable; using {DEFAULT_THEME!r}"
        )

    effective = tuple(harness for harness in harnesses if harness in MAIN_HARNESSES)
    unknown = tuple(harness for harness in harnesses if harness not in MAIN_HARNESSES)
    if unknown:
        names = ", ".join(repr(harness) for harness in unknown)
        diagnostics.append(
            f"{path}: unknown harness setting(s) {names}; retained but ignored"
        )

    return TuiSettings(
        theme=chosen_theme,
        harnesses=effective,
        unknown_harnesses=unknown,
        diagnostics=tuple(diagnostics),
    )


def save(
    settings: TuiSettings,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Atomically persist schema v1, retaining unknown harness names."""

    path = default_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SCHEMA,
        "theme": settings.theme,
        "harnesses": [*settings.harnesses, *settings.unknown_harnesses],
    }

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return path
