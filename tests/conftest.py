"""Shared fixtures across the test suite."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest


@dataclass
class GitSandbox:
    upstream: Path     # bare repo acting as the "remote"
    clone: Path        # working clone of upstream, pre-populated
    env: dict[str, str]


def _scrub_git_env(base: dict[str, str]) -> dict[str, str]:
    """Strip inherited GIT_* env vars. See memory feedback_git_env_leak.md."""
    return {k: v for k, v in base.items() if not k.startswith("GIT_")}


@pytest.fixture
def git_sandbox(tmp_path: Path) -> GitSandbox:
    env = _scrub_git_env(os.environ.copy())
    env.update({
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "HOME": str(tmp_path / "fake-home"),
    })
    (tmp_path / "fake-home").mkdir()

    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream)],
        check=True, env=env, capture_output=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed)],
        check=True, env=env, capture_output=True,
    )
    (seed / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A test skill.\n---\n# demo\n"
    )
    subprocess.run(
        ["git", "-C", str(seed), "add", "SKILL.md"],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "seed"],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "remote", "add", "origin", str(upstream)],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "push", "origin", "main"],
        check=True, env=env, capture_output=True,
    )

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(upstream), str(clone)],
        check=True, env=env, capture_output=True,
    )

    return GitSandbox(upstream=upstream, clone=clone, env=env)


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit_impl(tmp: Path) -> Path:
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha2.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(schema_src.read_text())
    return root


def _seed_skill_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


AGENT_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: {slug} agent.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
# {slug} agent body
"""


def _seed_agent_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    asset_path = agents_dir / f"{slug}.md"
    asset_path.write_text(
        AGENT_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return asset_path


def _seed_pi_extension_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    ext_dir = toolkit_root / "extensions" / slug
    ext_dir.mkdir(parents=True, exist_ok=True)
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (ext_dir / "extension.meta.yaml").write_text(
        f"apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} pi extension.\n"
        f"  lifecycle: stable\n"
        f"spec:\n"
        f"  origin: first-party\n"
        f"  vendored_via: none\n"
        f"  harnesses:\n"
        f"{harness_lines}\n"
    )
    (ext_dir / "package.json").write_text('{"name": "' + slug + '", "version": "1.0.0", "type": "module"}\n')
    (ext_dir / "index.ts").write_text("export default function (pi: any) {}\n")
    return ext_dir


@pytest.fixture
def skill_frontmatter() -> str:
    """Template for SKILL.md frontmatter; format with `slug=` and `harness_lines=`."""
    return SKILL_FRONTMATTER


@pytest.fixture
def seed_toolkit() -> Callable[[Path], Path]:
    return _seed_toolkit_impl


@pytest.fixture
def seed_skill() -> Callable[[Path, str, list[str]], Path]:
    return _seed_skill_impl


@pytest.fixture
def seed_agent() -> Callable[[Path, str, list[str]], Path]:
    return _seed_agent_impl


@pytest.fixture
def seed_pi_extension() -> Callable[[Path, str, list[str]], Path]:
    return _seed_pi_extension_impl


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit_impl(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}
