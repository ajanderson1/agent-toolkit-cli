"""Pure persistence tests for TUI settings schema v1 (#480)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_toolkit_tui.composition import MAIN_HARNESSES
from agent_toolkit_tui.settings import (
    DEFAULT_THEME,
    SCHEMA,
    TuiSettings,
    default_path,
    load,
    save,
)


def _settings_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "s.json"
    monkeypatch.setenv("AGENT_TOOLKIT_TUI_SETTINGS", str(path))
    return path


def _write(path: Path, *, theme: str, harnesses: list[str], schema: str = SCHEMA) -> None:
    path.write_text(
        json.dumps({"schema": schema, "theme": theme, "harnesses": harnesses})
    )


def test_missing_file_returns_defaults_without_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _settings_path(monkeypatch, tmp_path)

    settings = load(available_themes={DEFAULT_THEME})

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == MAIN_HARNESSES
    assert settings.unknown_harnesses == ()
    assert settings.diagnostics == ()


def test_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _settings_path(monkeypatch, tmp_path)
    expected = TuiSettings(theme="nord", harnesses=("pi",))

    save(expected)

    assert load(available_themes={DEFAULT_THEME, "nord"}) == expected


def test_malformed_json_returns_defaults_with_loud_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    path.write_text("{not json")

    settings = load(available_themes={DEFAULT_THEME})

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == MAIN_HARNESSES
    assert settings.diagnostics
    assert str(path) in settings.diagnostics[0]
    assert "malformed JSON" in settings.diagnostics[0]


def test_unknown_schema_returns_defaults_with_loud_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _write(
        path,
        schema="agent-toolkit-tui-settings/v99",
        theme="nord",
        harnesses=["pi"],
    )

    settings = load(available_themes={DEFAULT_THEME, "nord"})

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == MAIN_HARNESSES
    assert settings.diagnostics
    assert str(path) in settings.diagnostics[0]
    assert "schema" in settings.diagnostics[0]


def test_unknown_harness_key_is_retained_but_not_rendered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _write(path, theme=DEFAULT_THEME, harnesses=["pi", "ghost-harness"])

    settings = load(available_themes={DEFAULT_THEME})

    assert settings.harnesses == ("pi",)
    assert settings.unknown_harnesses == ("ghost-harness",)
    assert any("ghost-harness" in diagnostic for diagnostic in settings.diagnostics)

    save(settings)

    persisted = json.loads(path.read_text())
    assert persisted["harnesses"] == ["pi", "ghost-harness"]


def test_unavailable_theme_falls_back_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _write(path, theme="retired-theme", harnesses=["pi"])

    settings = load(available_themes={DEFAULT_THEME, "nord"})

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == ("pi",)
    assert any("retired-theme" in diagnostic for diagnostic in settings.diagnostics)


def test_empty_selection_is_legal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _write(path, theme=DEFAULT_THEME, harnesses=[])

    settings = load(available_themes={DEFAULT_THEME})

    assert settings.harnesses == ()
    assert settings.unknown_harnesses == ()
    assert settings.diagnostics == ()


def test_env_override_is_honoured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)

    save(TuiSettings(theme=DEFAULT_THEME, harnesses=("pi",)))

    assert path.exists()
    assert default_path() == path


def test_default_path_is_under_agent_toolkit_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_TOOLKIT_TUI_SETTINGS", raising=False)

    assert str(default_path()).endswith(".agent-toolkit/tui-settings.json")
