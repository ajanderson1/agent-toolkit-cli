"""The push gate validates outgoing commits, never an unrelated working tree."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_ci", ROOT / "scripts/local_ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def test_push_targets_include_other_branches_tags_and_deduplicate():
    a, b = "a" * 40, "b" * 40
    lines = [
        f"refs/heads/other {a} refs/heads/other {b}",
        f"refs/tags/v1 {b} refs/tags/v1 {'0' * 40}",
        f"refs/heads/same {a} refs/heads/same {b}",
        f"(delete) {'0' * 40} refs/heads/old {b}",
    ]
    assert ci.push_targets("\n".join(lines)) == [a, b]


def test_empty_push_does_not_check_head():
    assert ci.push_targets("") == []


@pytest.mark.parametrize("line", ["invalid", "ref not-a-sha remote " + "0" * 40])
def test_malformed_push_input_fails_closed(line):
    with pytest.raises(ValueError):
        ci.push_targets(line)


def test_snapshot_tests_committed_bytes_not_dirty_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    git("init", "-b", "main")
    (repo / "payload").write_text("committed")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "-m", "seed")
    sha = git("rev-parse", "HEAD")
    (repo / "payload").write_text("dirty")
    (repo / "untracked").write_text("not committed")
    snapshot = tmp_path / "snapshot"
    ci.snapshot(repo, sha, snapshot)
    assert (snapshot / "payload").read_text() == "committed"
    assert not (snapshot / "untracked").exists()
    assert subprocess.check_output(
        ["git", "-C", str(snapshot), "rev-parse", "HEAD"], text=True,
    ).strip() == sha


def test_docker_build_failure_prevents_run(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ci, "snapshot", lambda *args: None)
    def run(args, **kwargs):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(ci, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        ci.verify(ROOT, "a" * 40)
    assert calls[0][:2] == ["docker", "build"]
    assert calls[1][:3] == ["docker", "image", "rm"]
    assert not any(call[:2] == ["docker", "run"] for call in calls)


def test_gate_failure_prevents_next_target(monkeypatch):
    calls = []
    def verify(repo, target):
        calls.append(target)
        raise subprocess.CalledProcessError(1, ["docker", "run"])
    monkeypatch.setattr(ci, "verify", verify)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(
        f"ref {'a' * 40} remote {'0' * 40}\nref {'b' * 40} remote {'0' * 40}\n"
    ))
    with pytest.raises(subprocess.CalledProcessError):
        ci.main(["--pre-push"])
    assert calls == ["a" * 40]


def test_real_push_is_rejected_when_gate_cannot_run(tmp_path):
    repo, remote = tmp_path / "repo", tmp_path / "remote.git"
    env = dict(__import__("os").environ,
               GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
               GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")
    def git(*args, check=True):
        return subprocess.run(["git", *args], env=env, check=check,
                              capture_output=True, text=True)
    git("init", "--bare", str(remote))
    git("init", "-b", "main", str(repo))
    (repo / "payload").write_text("test")
    git("-C", str(repo), "add", ".")
    git("-C", str(repo), "commit", "-m", "seed")
    hooks = repo / ".githooks"
    hooks.mkdir()
    hook = hooks / "pre-push"
    hook.write_bytes((ROOT / ".githooks/pre-push").read_bytes())
    hook.chmod(0o755)
    git("-C", str(repo), "config", "core.hooksPath", str(hooks))
    # No scripts/local_ci.py: missing gate must be an error, not a silent pass.
    result = git("-C", str(repo), "push", str(remote), "main", check=False)
    assert result.returncode != 0
    assert "local_ci.py" in result.stderr
    assert git("--git-dir", str(remote), "show-ref", check=False).returncode == 1


def test_hook_and_hosted_checks_share_the_linux_gate():
    hook = yaml.safe_load((ROOT / "lefthook.yml").read_text())
    command = hook["pre-push"]["commands"]["ci"]
    assert command["use_stdin"] is True
    assert "scripts/local_ci.py --pre-push" in command["run"]
    workflow = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())
    steps = workflow["jobs"]["pytest"]["steps"]
    assert any("scripts/local_ci.py" in step.get("run", "") for step in steps)
    checks = (ROOT / "scripts/ci/checks.sh").read_text()
    for required in ("pytest -q", "mkdocs build --strict", "uv build"):
        assert required in checks
    assert "--locked" in checks
    dockerfile = (ROOT / "scripts/ci/Dockerfile").read_text()
    assert "USER node" in dockerfile, "root bypasses filesystem permission tests"
