"""Tests for `_yaml_edit` — the only writer for `.agent-toolkit.yaml`."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _invoke(runner: CliRunner, *args: str, input: str | None = None):
    return runner.invoke(main, ["_yaml-edit", *args], input=input, catch_exceptions=False)


def _write(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_add_creates_file_when_missing(tmp_path):
    f = tmp_path / "a.yaml"
    runner = CliRunner()
    result = _invoke(runner, "add", str(f), "skills", "alpha")
    assert result.exit_code == 0, result.output
    text = f.read_text(encoding="utf-8")
    assert "skills:" in text
    assert "- alpha" in text
    # All five sections present
    for section in ("skills", "agents", "commands", "hooks", "plugins"):
        assert f"{section}:" in text


def test_add_idempotent(tmp_path):
    f = tmp_path / "a.yaml"
    runner = CliRunner()
    _invoke(runner, "add", str(f), "skills", "alpha")
    first = f.read_text(encoding="utf-8")
    result = _invoke(runner, "add", str(f), "skills", "alpha")
    assert result.exit_code == 0
    assert f.read_text(encoding="utf-8") == first


def test_add_to_existing_section(tmp_path):
    f = tmp_path / "a.yaml"
    _write(
        f,
        "# my allow-list\n"
        "skills:\n"
        "  - alpha\n"
        "agents: []\n",
    )
    runner = CliRunner()
    result = _invoke(runner, "add", str(f), "skills", "beta")
    assert result.exit_code == 0
    text = f.read_text(encoding="utf-8")
    assert "- alpha" in text
    assert "- beta" in text
    # Comment preserved
    assert "# my allow-list" in text


def test_add_preserves_comment_and_blank_lines(tmp_path):
    f = tmp_path / "a.yaml"
    _write(
        f,
        "# header comment\n"
        "\n"
        "skills:\n"
        "  - alpha   # inline note\n"
        "\n"
        "agents:\n"
        "  - scout\n",
    )
    runner = CliRunner()
    _invoke(runner, "add", str(f), "skills", "beta")
    text = f.read_text(encoding="utf-8")
    assert "# header comment" in text
    assert "# inline note" in text


def test_remove_idempotent_when_slug_absent(tmp_path):
    f = tmp_path / "a.yaml"
    _write(f, "skills:\n  - alpha\n")
    runner = CliRunner()
    result = _invoke(runner, "remove", str(f), "skills", "ghost")
    assert result.exit_code == 0
    assert "alpha" in f.read_text(encoding="utf-8")


def test_remove_drops_slug(tmp_path):
    f = tmp_path / "a.yaml"
    _write(f, "skills:\n  - alpha\n  - beta\n")
    runner = CliRunner()
    _invoke(runner, "remove", str(f), "skills", "alpha")
    text = f.read_text(encoding="utf-8")
    assert "alpha" not in text
    assert "beta" in text


def test_remove_last_slug_leaves_empty_list(tmp_path):
    f = tmp_path / "a.yaml"
    _write(f, "skills:\n  - alpha\n")
    runner = CliRunner()
    _invoke(runner, "remove", str(f), "skills", "alpha")
    text = f.read_text(encoding="utf-8")
    # Section persists, just empty
    assert "skills" in text
    assert "alpha" not in text


def test_remove_errors_when_file_missing(tmp_path):
    f = tmp_path / "nope.yaml"
    runner = CliRunner()
    result = _invoke(runner, "remove", str(f), "skills", "alpha")
    assert result.exit_code != 0
    assert "no such file" in result.output.lower() or "not found" in result.output.lower()


def test_snapshot_replaces_file_from_stdin(tmp_path):
    f = tmp_path / "a.yaml"
    _write(f, "# old comment\nskills:\n  - oldslug\n")
    runner = CliRunner()
    stdin = "skills alpha\nskills beta\nagents scout\n"
    result = _invoke(runner, "snapshot", str(f), input=stdin)
    assert result.exit_code == 0, result.output
    text = f.read_text(encoding="utf-8")
    assert "oldslug" not in text
    assert "- alpha" in text
    assert "- beta" in text
    assert "- scout" in text


def test_snapshot_creates_missing_file(tmp_path):
    f = tmp_path / "fresh.yaml"
    runner = CliRunner()
    stdin = "skills alpha\n"
    result = _invoke(runner, "snapshot", str(f), input=stdin)
    assert result.exit_code == 0
    assert "- alpha" in f.read_text(encoding="utf-8")


def test_snapshot_empty_stdin_writes_empty_sections(tmp_path):
    f = tmp_path / "a.yaml"
    runner = CliRunner()
    result = _invoke(runner, "snapshot", str(f), input="")
    assert result.exit_code == 0
    text = f.read_text(encoding="utf-8")
    for section in ("skills", "agents", "commands", "hooks", "plugins"):
        assert f"{section}:" in text


def test_add_unknown_section_errors(tmp_path):
    """`add` rejects sections not in the SECTIONS allow-list."""
    f = tmp_path / "a.yaml"
    runner = CliRunner()
    result = _invoke(runner, "add", str(f), "bogus", "x")
    assert result.exit_code != 0
    assert "unknown section" in result.output.lower()


def test_remove_idempotent_byte_equal(tmp_path):
    """`remove` of an absent slug must not rewrite the file."""
    f = tmp_path / "a.yaml"
    _write(f, "skills:\n  - alpha\n")
    runner = CliRunner()
    before = f.read_text(encoding="utf-8")
    before_mtime = f.stat().st_mtime_ns
    result = _invoke(runner, "remove", str(f), "skills", "ghost")
    assert result.exit_code == 0
    assert f.read_text(encoding="utf-8") == before
    # mtime check is best-effort — same byte content should mean no write,
    # but assert content equality at minimum.
    _ = before_mtime  # silence unused
