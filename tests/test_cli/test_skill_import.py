"""Tests for `skill import` — additive cross-machine library sync."""
import json
import subprocess
from pathlib import Path

import click
import pytest

from tests.conftest import scrub_git_env

from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_reconstruct_helper_clones_single_repo_and_pins(
    git_sandbox, tmp_path, monkeypatch
):
    """reconstruct_skill_into_library clones a single repo and honours pin_sha."""
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli.commands.skill import reconstruct_skill_into_library
    from agent_toolkit_cli.skill_paths import library_skill_path
    from agent_toolkit_cli.skill_source import parse_source

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    parsed = parse_source(str(git_sandbox.upstream))
    target_sha = skill_git.head_sha(git_sandbox.clone, env=None)

    upstream_sha, local_sha = reconstruct_skill_into_library(
        parsed, "demo", pin_sha=target_sha,
    )

    assert (library_skill_path("demo") / "SKILL.md").exists()
    assert local_sha == target_sha


NOTE_UPSTREAM = "pinned to upstream commits"
NOTE_PROJECT = "Project-scoped skills"
NOTE_AGENTS = "not installed for any agent"


def test_import_missing_file_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(tmp_path / "nope.json")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_empty_file_imports_nothing_but_prints_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "lib" / "skills"))
    incoming = tmp_path / "incoming.json"
    incoming.write_text('{"version": 1, "skills": {}}')
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert NOTE_UPSTREAM in result.output
    assert NOTE_PROJECT in result.output
    assert NOTE_AGENTS in result.output


def _write_incoming_for(
    upstream: Path | str, slug: str, sha: str, dest: Path
) -> Path:
    """Write a v1 lock naming one single-repo skill pinned to `sha`.

    `upstream` may be a path or a `file://` URL string — passed through to the
    lock's `source` verbatim (don't wrap a `file://` URL in Path, which
    collapses the `//` and makes git misread `file:` as an ssh host)."""
    dest.write_text(json.dumps({
        "version": 1,
        "skills": {
            slug: {
                "source": str(upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": sha,
                "localSha": sha,
            }
        },
    }))
    return dest


def test_import_adds_new_single_skill_pinned(git_sandbox, tmp_path, monkeypatch):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = _write_incoming_for(
        git_sandbox.upstream, "demo", sha, tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output
    assert "added" in result.output and "demo" in result.output

    assert (library_root / "demo" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "demo" in lock["skills"]
    assert lock["skills"]["demo"]["localSha"] == sha


def test_import_skips_existing_and_preserves_lock(
    installed_skill, git_sandbox, tmp_path
):
    """A slug already in the library is skipped; its lock entry is untouched."""
    before = installed_skill.lock_path.read_text()

    # Incoming names the SAME slug 'demo' but points at a different source.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": "someone/other-repo",
                "sourceType": "github",
                "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 skipped" in result.output
    assert "already present" in result.output

    # Additive-merge invariant: existing entry byte-identical.
    assert installed_skill.lock_path.read_text() == before


def test_import_latest_clones_current_head(make_behind, tmp_path, monkeypatch):
    """--latest lands on upstream HEAD, not the recorded (older) sha."""
    from agent_toolkit_cli import skill_git
    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Recorded sha = the OLD clone HEAD (before upstream advanced).
    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "demo": {
                "source": str(sandbox.upstream),
                "sourceType": "git",
                "skillPath": "SKILL.md",
                "upstreamSha": old_sha,
                "localSha": old_sha,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming), "--latest"])
    assert result.exit_code == 0, result.output
    assert "latest:" in result.output

    landed = skill_git.head_sha(library_root / "demo", env=None)
    assert landed != old_sha, "with --latest, HEAD should be upstream's newer commit"


def test_import_partial_failure_exit_1_but_writes_good(
    git_sandbox, tmp_path, monkeypatch
):
    from agent_toolkit_cli import skill_git
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    good_sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "good": {
                "source": str(git_sandbox.upstream),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": good_sha, "localSha": good_sha,
            },
            "bad": {
                "source": str(tmp_path / "does-not-exist.git"),
                "sourceType": "git", "skillPath": "SKILL.md",
                "upstreamSha": "deadbeef",
            },
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 1, result.output
    assert "1 added" in result.output and "1 failed" in result.output
    assert "failed" in result.output and "bad" in result.output

    # Good skill still landed and is in the lock.
    assert (library_root / "good" / "SKILL.md").exists()
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "good" in lock["skills"]
    assert "bad" not in lock["skills"]


def test_import_reconstructs_monorepo_entry(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    # Incoming lock describes a monorepo skill: directory skillPath, parentUrl,
    # read_only. owner_repo synthesised as local/<name> by file:// parsing.
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "mkdocs": {
                "source": f"local/{parent.name}",
                "sourceType": "git",
                "skillPath": "mkdocs",
                "parentUrl": f"file://{parent}",
                "readOnly": True,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output

    canonical = library_root / "mkdocs"
    assert (canonical / "SKILL.md").exists(), "monorepo skill materialised"
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert lock["skills"]["mkdocs"]["skillPath"] == "mkdocs"
    assert lock["skills"]["mkdocs"].get("readOnly") is True


def test_import_self_is_noop(installed_skill):
    """Importing the live global lock onto itself skips all, changes nothing."""
    before = installed_skill.lock_path.read_text()
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(installed_skill.lock_path)])
    assert result.exit_code == 0, result.output
    assert "0 added" in result.output
    assert "skipped" in result.output
    assert installed_skill.lock_path.read_text() == before


def test_import_persists_lock_incrementally_before_abort(
    git_sandbox, tmp_path, monkeypatch
):
    """A skill that landed before an abort is already in the on-disk lock (#251).

    Simulates ^C mid-import: the first skill clones fine, then the second
    reconstruction raises KeyboardInterrupt (not caught by the per-skill
    `except Exception`). With end-of-loop persistence the lock would be empty;
    with per-skill persistence the first skill is recorded and a re-run resumes.
    """
    from agent_toolkit_cli import skill_git
    from agent_toolkit_cli.commands import skill as skill_pkg

    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    sha = skill_git.head_sha(git_sandbox.clone, env=None)
    incoming = tmp_path / "incoming.json"
    # "aaa" sorts first (clones fine); "zzz" sorts second (we abort on it).
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "aaa": {
                "source": str(git_sandbox.upstream), "sourceType": "git",
                "skillPath": "SKILL.md", "upstreamSha": sha, "localSha": sha,
            },
            "zzz": {
                "source": str(git_sandbox.upstream), "sourceType": "git",
                "skillPath": "SKILL.md", "upstreamSha": sha, "localSha": sha,
            },
        },
    }))

    real_reconstruct = skill_pkg.reconstruct_skill_into_library

    def reconstruct_then_abort(parsed, slug, *, pin_sha):
        if slug == "zzz":
            raise KeyboardInterrupt
        return real_reconstruct(parsed, slug, pin_sha=pin_sha)

    monkeypatch.setattr(
        skill_pkg, "reconstruct_skill_into_library", reconstruct_then_abort,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    # The abort aborts the run (CliRunner surfaces KeyboardInterrupt as a
    # non-zero SystemExit); the import did NOT complete normally.
    assert result.exit_code != 0

    # The first skill was persisted to the lock BEFORE the abort.
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    assert "aaa" in lock["skills"], "incremental write should record the landed skill"
    assert "zzz" not in lock["skills"]


def _is_shallow(repo: Path) -> bool:
    import subprocess
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return out == "true"


def test_import_single_pinned_old_sha_lands_exact_tree(
    make_behind, tmp_path, monkeypatch
):
    """The bug's core: import a single-repo skill pinned to a NON-HEAD older
    commit. A naive `clone --depth=1 + checkout <old_sha>` fails ('unable to
    read tree'); the fetch-pin-then-checkout path must land that exact commit
    with the right tree (#259)."""
    from agent_toolkit_cli import skill_git

    sandbox = make_behind  # upstream advanced one commit past the clone's HEAD
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    old_sha = skill_git.head_sha(sandbox.clone, env=None)  # the seed commit
    # file:// so --depth genuinely shallows (plain local paths ignore --depth),
    # mirroring the https://github.com/... URLs import resolves in production.
    incoming = _write_incoming_for(
        f"file://{sandbox.upstream}", "demo", old_sha,
        tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output

    landed = library_root / "demo"
    assert skill_git.head_sha(landed, env=None) == old_sha
    # The pinned (old) commit's tree: seed had SKILL.md but NOT the advance file.
    assert (landed / "SKILL.md").exists()
    assert not (landed / "UPSTREAM.md").exists(), (
        "landed tree must be the pinned old commit, not upstream HEAD"
    )


def test_import_single_records_unchanged_shas(make_behind, tmp_path, monkeypatch):
    """Shallow path preserves SHA semantics: localSha = pinned commit,
    upstreamSha = branch tip (#259)."""
    from agent_toolkit_cli import skill_git

    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = _write_incoming_for(
        f"file://{sandbox.upstream}", "demo", old_sha,
        tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output

    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    entry = lock["skills"]["demo"]
    assert entry["localSha"] == old_sha, "localSha = pinned commit"
    # upstreamSha = branch tip, which is strictly newer than the pinned sha.
    assert entry["upstreamSha"] != old_sha, "upstreamSha = branch tip"
    landed_branch_tip = skill_git.remote_head_sha(
        library_root / "demo", ref="main", env=None
    )
    assert entry["upstreamSha"] == landed_branch_tip


def test_import_single_clone_is_shallow(make_behind, tmp_path, monkeypatch):
    """End-to-end proof the perf fix engaged: the imported library clone is
    shallow (#259)."""
    from agent_toolkit_cli import skill_git

    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = _write_incoming_for(
        f"file://{sandbox.upstream}", "demo", old_sha,
        tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert _is_shallow(library_root / "demo") is True


def test_import_latest_single_is_shallow_branch_head(
    make_behind, tmp_path, monkeypatch
):
    """`--latest` lands branch HEAD as a shallow clone (#259)."""
    from agent_toolkit_cli import skill_git

    sandbox = make_behind
    library_root = tmp_path / "lib" / "skills"
    for k, v in sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    old_sha = skill_git.head_sha(sandbox.clone, env=None)
    incoming = _write_incoming_for(
        f"file://{sandbox.upstream}", "demo", old_sha,
        tmp_path / "incoming.json",
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["skill", "import", str(incoming), "--latest"]
    )
    assert result.exit_code == 0, result.output

    landed = library_root / "demo"
    assert skill_git.head_sha(landed, env=None) != old_sha, "should be HEAD"
    assert (landed / "UPSTREAM.md").exists(), "branch HEAD has the advance file"
    assert _is_shallow(landed) is True


def test_import_monorepo_clone_is_shallow(tmp_path, monkeypatch):
    """Monorepo parent clone is shallow and the subpath tree materialises (#259)."""
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "mkdocs": {
                "source": f"local/{parent.name}",
                "sourceType": "git",
                "skillPath": "mkdocs",
                "parentUrl": f"file://{parent}",
                "readOnly": True,
            }
        },
    }))

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "import", str(incoming)])
    assert result.exit_code == 0, result.output
    assert (library_root / "mkdocs" / "SKILL.md").exists()

    # The parent clone (symlink target's repo) must be shallow.
    from agent_toolkit_cli.skill_paths import parent_clone_path
    owner, repo = f"local/{parent.name}".split("/", 1)
    parent_dir = parent_clone_path(owner, repo, ref=None, env=None)
    assert _is_shallow(parent_dir) is True


def _commit_parent_change(parent: Path, path: str, content: str) -> str:
    """Commit a parent change and return its new HEAD SHA."""
    from agent_toolkit_cli import skill_git

    (parent / path).write_text(content)
    env = scrub_git_env()
    for command in (
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "advance parent"],
    ):
        subprocess.run(command, cwd=parent, check=True, env=env)
    return skill_git.head_sha(parent, env=None)


def _write_monorepo_incoming(
    parent: Path, entries: dict[str, str], dest: Path, *, ref: str | None = None,
) -> Path:
    """Write lock entries for fixture subpaths pinned to their given SHAs."""
    dest.write_text(json.dumps({
        "version": 1,
        "skills": {
            slug: {
                "source": f"local/{parent.name}",
                "sourceType": "git",
                "skillPath": slug,
                "parentUrl": f"file://{parent}",
                "readOnly": True,
                "upstreamSha": sha,
                "localSha": sha,
                **({"ref": ref} if ref is not None else {}),
            }
            for slug, sha in entries.items()
        },
    }))
    return dest


def _monorepo_parent_clone(library_root: Path) -> Path:
    parents = list((library_root / "_parents").glob("*/*"))
    assert len(parents) == 1, parents
    return parents[0]


def test_import_monorepo_pinned_old_sha_lands_and_records_exact_commit(
    tmp_path, monkeypatch,
):
    """Default monorepo import must land the incoming pin, not ref HEAD."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    old_sha = skill_git.head_sha(parent, env=None)
    new_sha = _commit_parent_change(parent, "mkdocs/UPSTREAM.md", "new\n")
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    incoming = _write_monorepo_incoming(
        parent, {"mkdocs": old_sha}, tmp_path / "incoming.json",
    )

    result = CliRunner().invoke(main, ["skill", "import", str(incoming)])

    assert result.exit_code == 0, result.output
    parent_clone = _monorepo_parent_clone(library_root)
    assert skill_git.head_sha(parent_clone, env=None) == old_sha
    assert not (library_root / "mkdocs" / "UPSTREAM.md").exists()
    entry = json.loads((library_root.parent / "skills-lock.json").read_text())["skills"]["mkdocs"]
    assert entry["upstreamSha"] == old_sha
    assert entry["upstreamSha"] != new_sha


def test_import_monorepo_full_sha_ref_clones_then_checks_out_pin(
    tmp_path, monkeypatch,
):
    """A SHA ref cannot be passed to clone --branch during import."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    sha = skill_git.head_sha(parent, env=None)
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    incoming = _write_monorepo_incoming(
        parent, {"mkdocs": sha}, tmp_path / "incoming.json", ref=sha,
    )

    result = CliRunner().invoke(main, ["skill", "import", str(incoming)])

    assert result.exit_code == 0, result.output
    assert skill_git.head_sha(_monorepo_parent_clone(library_root), env=None) == sha
    lock = json.loads((library_root.parent / "skills-lock.json").read_text())
    entry = lock["skills"]["mkdocs"]
    assert entry["ref"] == sha
    assert entry["upstreamSha"] == sha


def test_import_monorepo_latest_lands_current_ref_head(tmp_path, monkeypatch):
    """--latest preserves the current parent-ref refresh behavior."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    old_sha = skill_git.head_sha(parent, env=None)
    new_sha = _commit_parent_change(parent, "mkdocs/UPSTREAM.md", "new\n")
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    incoming = _write_monorepo_incoming(
        parent, {"mkdocs": old_sha}, tmp_path / "incoming.json",
    )

    result = CliRunner().invoke(
        main, ["skill", "import", str(incoming), "--latest"],
    )

    assert result.exit_code == 0, result.output
    assert skill_git.head_sha(_monorepo_parent_clone(library_root), env=None) == new_sha
    assert (library_root / "mkdocs" / "UPSTREAM.md").exists()


def test_import_monorepo_sibling_reuses_matching_pinned_parent(
    tmp_path, monkeypatch,
):
    """Sibling imports at one pin share the parent without moving it."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    old_sha = skill_git.head_sha(parent, env=None)
    _commit_parent_change(parent, "mkdocs/UPSTREAM.md", "new\n")
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    first = _write_monorepo_incoming(
        parent, {"mkdocs": old_sha}, tmp_path / "first.json",
    )
    second = _write_monorepo_incoming(
        parent, {"docker": old_sha}, tmp_path / "second.json",
    )
    runner = CliRunner()
    assert runner.invoke(main, ["skill", "import", str(first)]).exit_code == 0
    result = runner.invoke(main, ["skill", "import", str(second)])

    assert result.exit_code == 0, result.output
    assert skill_git.head_sha(_monorepo_parent_clone(library_root), env=None) == old_sha
    assert (library_root / "mkdocs" / "SKILL.md").exists()
    assert (library_root / "docker" / "SKILL.md").exists()


def test_import_monorepo_conflicting_pin_refuses_without_moving_parent(
    tmp_path, monkeypatch,
):
    """A shared parent cannot silently switch a first sibling to another pin."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    old_sha = skill_git.head_sha(parent, env=None)
    new_sha = _commit_parent_change(parent, "mkdocs/UPSTREAM.md", "new\n")
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    first = _write_monorepo_incoming(
        parent, {"mkdocs": old_sha}, tmp_path / "first.json",
    )
    assert runner.invoke(main, ["skill", "import", str(first)]).exit_code == 0
    before_lock = (library_root.parent / "skills-lock.json").read_text()

    second = _write_monorepo_incoming(
        parent, {"docker": new_sha}, tmp_path / "second.json",
    )
    result = runner.invoke(main, ["skill", "import", str(second)])

    assert result.exit_code == 1, result.output
    assert "failed" in result.output
    assert skill_git.head_sha(_monorepo_parent_clone(library_root), env=None) == old_sha
    assert (library_root / "mkdocs" / "SKILL.md").exists()
    assert not (library_root / "docker").exists()
    assert (library_root.parent / "skills-lock.json").read_text() == before_lock


def test_import_monorepo_dirty_parent_refuses_before_movement(tmp_path, monkeypatch):
    """Import never hard-resets a dirty shared parent, even at its same pin."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    parent = _init_parent(tmp_path)
    old_sha = skill_git.head_sha(parent, env=None)
    _commit_parent_change(parent, "mkdocs/UPSTREAM.md", "new\n")
    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    runner = CliRunner()
    first = _write_monorepo_incoming(
        parent, {"mkdocs": old_sha}, tmp_path / "first.json",
    )
    assert runner.invoke(main, ["skill", "import", str(first)]).exit_code == 0
    parent_clone = _monorepo_parent_clone(library_root)
    (parent_clone / "mkdocs" / "DIRTY.md").write_text("keep me\n")
    before_lock = (library_root.parent / "skills-lock.json").read_text()

    second = _write_monorepo_incoming(
        parent, {"docker": old_sha}, tmp_path / "second.json",
    )
    result = runner.invoke(main, ["skill", "import", str(second)])

    assert result.exit_code == 1, result.output
    assert "dirty" in result.output.lower()
    assert skill_git.head_sha(parent_clone, env=None) == old_sha
    assert (parent_clone / "mkdocs" / "DIRTY.md").exists()
    assert not (library_root / "docker").exists()
    assert (library_root.parent / "skills-lock.json").read_text() == before_lock


def test_import_direct_package_skill_path_ignores_parent_url(tmp_path, monkeypatch):
    """A direct package lock entry clones its source instead of a parent cache."""
    from agent_toolkit_cli import skill_git
    from tests.test_cli.test_skill_update_monorepo import _init_parent

    package_root = _init_parent(tmp_path)
    (package_root / "package.json").write_text('{"name": "direct-package"}\n')
    nested_skill = package_root / "skills" / "direct" / "SKILL.md"
    nested_skill.parent.mkdir(parents=True)
    nested_skill.write_text("---\nname: direct\n---\nbody\n")
    subprocess.run(["git", "add", "package.json", "skills"], cwd=package_root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "package skill"],
        cwd=package_root,
        check=True,
    )
    assert not (package_root / "SKILL.md").exists()

    library_root = tmp_path / "lib" / "skills"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    sha = skill_git.head_sha(package_root, env=None)
    package_url = f"file://{package_root}"
    incoming = tmp_path / "incoming.json"
    incoming.write_text(json.dumps({
        "version": 1,
        "skills": {
            "direct": {
                "source": package_url,
                "sourceType": "git",
                "ref": sha,
                "skillPath": "SKILL.md",
                "parentUrl": package_url,
                "upstreamSha": sha,
            }
        },
    }))

    result = CliRunner().invoke(main, ["skill", "import", str(incoming)])

    assert result.exit_code == 0, result.output
    assert (library_root / "direct" / "package.json").exists()
    assert (library_root / "direct" / "skills" / "direct" / "SKILL.md").exists()
    assert not (library_root / "_parents").exists()
    assert json.loads((library_root.parent / "skills-lock.json").read_text()) == {
        "version": 1,
        "skills": {
            "direct": {
                "source": package_url,
                "sourceType": "git",
                "ref": sha,
                "skillPath": "SKILL.md",
                "upstreamSha": sha,
                "localSha": sha,
                "parentUrl": package_url,
            }
        },
    }


def test_entry_to_parsed_keeps_directory_skill_path_as_monorepo():
    """A directory skillPath is still a monorepo subpath when parentUrl exists."""
    from agent_toolkit_cli.commands.skill.import_cmd import _entry_to_parsed
    from agent_toolkit_cli.skill_lock import LockEntry

    parsed = _entry_to_parsed(LockEntry(
        source="owner/repo",
        source_type="github",
        skill_path="skills/example",
        parent_url="https://github.com/owner/repo.git",
    ))

    assert parsed.url == "https://github.com/owner/repo.git"
    assert parsed.subpath == "skills/example"


def test_entry_to_parsed_refuses_parent_url_without_skill_path():
    """Missing skillPath cannot safely be inferred from parentUrl alone."""
    from agent_toolkit_cli.commands.skill.import_cmd import _entry_to_parsed
    from agent_toolkit_cli.skill_lock import LockEntry

    entry = LockEntry(
        source="owner/repo",
        source_type="github",
        parent_url="https://github.com/owner/repo.git",
    )

    with pytest.raises(click.ClickException, match="parentUrl.*skillPath"):
        _entry_to_parsed(entry)


def test_import_appears_in_skill_help():
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "--help"])
    assert result.exit_code == 0
    assert "import" in result.output
