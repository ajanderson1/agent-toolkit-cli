"""Pure persistence tests for TUI settings schema v1 (#480)."""

from __future__ import annotations

from dataclasses import replace
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


def test_invalid_utf8_returns_defaults_with_loud_diagnostic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    path.write_bytes(b"\xff\xfe invalid UTF-8")

    settings = load(available_themes={DEFAULT_THEME})

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == MAIN_HARNESSES
    assert settings.diagnostics
    assert str(path) in settings.diagnostics[0]
    assert "UTF-8" in settings.diagnostics[0]


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


def test_future_schema_cannot_be_overwritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    original = {
        "schema": "agent-toolkit-tui-settings/v99",
        "theme": "future-theme",
        "harnesses": ["future-harness"],
        "future_option": {"nested": ["must", "survive"]},
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    settings = load(available_themes={DEFAULT_THEME})

    with pytest.raises(ValueError, match="unsupported schema"):
        save(settings)

    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_unknown_top_level_v1_fields_survive_save(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    original = {
        "schema": SCHEMA,
        "theme": "nord",
        "harnesses": ["pi"],
        "future_option": {"nested": ["must", "survive"]},
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    save(load(available_themes={DEFAULT_THEME, "nord"}))

    assert json.loads(path.read_text(encoding="utf-8")) == original


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


def test_unavailable_theme_survives_unrelated_harness_save(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _settings_path(monkeypatch, tmp_path)
    _write(path, theme="retired-theme", harnesses=["pi"])

    settings = load(available_themes={DEFAULT_THEME, "nord"})
    assert settings.theme == DEFAULT_THEME

    save(replace(settings, harnesses=("codex",)))

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["theme"] == "retired-theme"
    assert persisted["harnesses"] == ["codex"]


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


@pytest.mark.parametrize("override", ("relative-settings.json", " "))
def test_relative_or_whitespace_env_override_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, override: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / override,
        theme="nord",
        harnesses=["pi"],
    )

    settings = load(
        available_themes={DEFAULT_THEME, "nord"},
        env={"AGENT_TOOLKIT_TUI_SETTINGS": override},
    )

    assert settings.theme == DEFAULT_THEME
    assert settings.harnesses == MAIN_HARNESSES
    assert settings.diagnostics
    assert "AGENT_TOOLKIT_TUI_SETTINGS" in settings.diagnostics[0]
    assert "absolute" in settings.diagnostics[0]


def test_default_path_is_under_agent_toolkit_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_TOOLKIT_TUI_SETTINGS", raising=False)

    assert str(default_path()).endswith(".agent-toolkit/tui-settings.json")
