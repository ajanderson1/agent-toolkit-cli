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
_KNOWN_FIELDS = frozenset(("schema", "theme", "harnesses"))


class SettingsPathError(ValueError):
    """Raised when the explicit settings-path override is unsafe."""


class SettingsWriteError(ValueError):
    """Raised when loaded settings cannot be safely rewritten."""


@dataclass(frozen=True)
class TuiSettings:
    """Validated settings plus retained forward-compatibility state."""

    theme: str = DEFAULT_THEME
    harnesses: tuple[str, ...] = MAIN_HARNESSES
    unknown_harnesses: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    retained_theme: str | None = None
    unknown_top_level: tuple[tuple[str, object], ...] = ()
    write_error: str | None = None


def default_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the settings path, rejecting unsafe explicit overrides."""

    environ = os.environ if env is None else env
    if _ENV_VAR not in environ:
        return Path.home() / ".agent-toolkit" / "tui-settings.json"

    override = environ[_ENV_VAR]
    if not override.strip():
        raise SettingsPathError(
            f"{_ENV_VAR} must be a non-whitespace absolute path; unset it to use the default"
        )
    path = Path(override).expanduser()
    if not path.is_absolute():
        raise SettingsPathError(
            f"{_ENV_VAR} must be an absolute path; got {override!r}"
        )
    return path


def _defaults(*diagnostics: str, write_error: str | None = None) -> TuiSettings:
    return TuiSettings(diagnostics=tuple(diagnostics), write_error=write_error)


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

    try:
        path = default_path(env)
    except SettingsPathError as exc:
        return _defaults(str(exc))

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _defaults()
    except UnicodeDecodeError as exc:
        return _defaults(f"{path}: invalid UTF-8 ({exc})")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _defaults(f"{path}: malformed JSON ({exc})")

    if not isinstance(payload, dict):
        return _defaults(f"{path}: settings root must be a JSON object")

    schema = payload.get("schema")
    if schema != SCHEMA:
        message = (
            f"{path}: unsupported schema {schema!r}; expected {SCHEMA!r}; "
            "refusing writes until an explicit migration or reset exists"
        )
        return _defaults(message, write_error=message)

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
    retained_theme: str | None = None
    if available_themes is not None and theme not in available_themes:
        chosen_theme = DEFAULT_THEME
        retained_theme = theme
        diagnostics.append(
            f"{path}: theme {theme!r} is unavailable; using {DEFAULT_THEME!r}"
        )

    unknown_top_level = tuple(
        (key, value) for key, value in payload.items() if key not in _KNOWN_FIELDS
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
        retained_theme=retained_theme,
        unknown_top_level=unknown_top_level,
    )


def save(
    settings: TuiSettings,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Atomically persist writable v1 settings without losing retained data."""

    if settings.write_error is not None:
        raise SettingsWriteError(settings.write_error)

    path = default_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = dict(settings.unknown_top_level)
    payload.update(
        {
            "schema": SCHEMA,
            "theme": (
                settings.retained_theme
                if settings.retained_theme is not None
                else settings.theme
            ),
            "harnesses": [*settings.harnesses, *settings.unknown_harnesses],
        }
    )

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
