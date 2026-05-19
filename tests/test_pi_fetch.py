"""Tests for `_pi_fetch.py` — the `pi install`/`pi remove` shell-out wrapper."""
from __future__ import annotations

import subprocess

import pytest

from agent_toolkit_cli._pi_fetch import (
    PiNotFoundError,
    fetch_package,
    remove_package_fetched,
)


def test_fetch_package_invokes_pi_install(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    cwds: list[str | None] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        cwds.append(kwargs.get("cwd"))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    home = tmp_path / "home"
    proj = tmp_path / "proj"
    home.mkdir()
    proj.mkdir()

    fetch_package("npm:pi-subagents", scope="user", home=home, project_root=proj)

    assert calls, "pi install was not invoked"
    assert calls[0][:2] == ["pi", "install"]
    assert "npm:pi-subagents" in calls[0]
    # No `--local` flag at user scope.
    assert "--local" not in calls[0]
    # User scope → cwd is the home dir.
    assert cwds[0] == str(home)


def test_fetch_package_project_scope_uses_local_flag(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    cwds: list[str | None] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        cwds.append(kwargs.get("cwd"))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    home = tmp_path / "home"
    proj = tmp_path / "proj"
    home.mkdir()
    proj.mkdir()

    fetch_package("npm:pi-subagents", scope="project", home=home, project_root=proj)

    assert calls[0][:2] == ["pi", "install"]
    assert "--local" in calls[0]
    # Project scope → cwd is the project root.
    assert cwds[0] == str(proj)


def test_fetch_package_raises_on_pi_missing(tmp_path, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError("pi")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(PiNotFoundError):
        fetch_package(
            "npm:pi-subagents",
            scope="user",
            home=tmp_path / "home",
            project_root=tmp_path / "proj",
        )


def test_fetch_package_raises_on_nonzero(tmp_path, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc:
        fetch_package(
            "npm:pi-subagents",
            scope="user",
            home=tmp_path / "home",
            project_root=tmp_path / "proj",
        )
    assert "boom" in str(exc.value)


def test_remove_package_fetched_invokes_pi_remove(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    cwds: list[str | None] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        cwds.append(kwargs.get("cwd"))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    home = tmp_path / "home"
    proj = tmp_path / "proj"
    home.mkdir()
    proj.mkdir()

    remove_package_fetched(
        "npm:pi-subagents", scope="project", home=home, project_root=proj
    )

    assert calls[0][:2] == ["pi", "remove"]
    assert "npm:pi-subagents" in calls[0]
    assert "--local" in calls[0]
    # Project scope → cwd is the project root.
    assert cwds[0] == str(proj)
