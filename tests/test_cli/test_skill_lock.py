import json
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_lock import (
    LockEntry,
    LockFile,
    add_entry,
    clone_url_from_entry,
    is_sha_pinned,
    looks_like_sha,
    read_lock,
    remove_entry,
    write_lock,
)


def test_read_missing_file_returns_empty(tmp_path: Path):
    lock = read_lock(tmp_path / "nope.json")
    assert lock == LockFile(version=1, skills={})


def test_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(
        version=1,
        skills={
            "journal": LockEntry(
                source="ajanderson1/journal",
                source_type="github",
                ref="main",
                skill_path="SKILL.md",
                upstream_sha="abc",
                local_sha="def",
            ),
        },
    )
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 1
    assert raw["skills"]["journal"]["source"] == "ajanderson1/journal"
    assert raw["skills"]["journal"]["sourceType"] == "github"
    assert raw["skills"]["journal"]["upstreamSha"] == "abc"
    assert raw["skills"]["journal"]["localSha"] == "def"
    assert p.read_text().endswith("\n")
    assert read_lock(p) == lf


def test_keys_sorted_alphabetically(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    lf = LockFile(version=1, skills={})
    lf = add_entry(lf, "zeta", LockEntry(source="o/zeta", source_type="github"))
    lf = add_entry(lf, "alpha", LockEntry(source="o/alpha", source_type="github"))
    write_lock(p, lf)
    raw = p.read_text()
    assert raw.index('"alpha"') < raw.index('"zeta"')


def test_unknown_fields_in_input_are_preserved_on_round_trip(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": {
                    "x": {
                        "source": "o/x",
                        "sourceType": "github",
                        "futureField": "yes",
                    },
                },
            }
        )
    )
    lf = read_lock(p)
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["skills"]["x"]["futureField"] == "yes"


def test_remove_entry():
    lf = LockFile(version=1, skills={"a": LockEntry(source="o/a", source_type="github")})
    lf = remove_entry(lf, "a")
    assert lf.skills == {}


def test_remove_unknown_entry_is_noop():
    lf = LockFile(version=1, skills={})
    assert remove_entry(lf, "nope") == lf


def test_unknown_high_version_treated_as_empty(tmp_path: Path):
    """Forward compat: a version we have no reader for becomes empty rather
    than crashing — but unknown fields in known versions are preserved
    (covered by test_unknown_fields_in_input_are_preserved_on_round_trip).
    """
    p = tmp_path / "skills-lock.json"
    p.write_text('{"version": 999, "skills": {}}')
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})


def test_unparseable_file_treated_as_empty(tmp_path: Path):
    p = tmp_path / "skills-lock.json"
    p.write_text("not json")
    lf = read_lock(p)
    assert lf == LockFile(version=1, skills={})


# ── Cross-version interop: `npx skills` writes v3 globally ─────────────────


def test_read_v3_global_lock_from_npx_skills(tmp_path: Path):
    """`npx skills` writes version 3 to ~/.agents/.skill-lock.json. Our reader
    accepts it and surfaces entries via the same LockEntry shape.
    """
    p = tmp_path / ".skill-lock.json"
    p.write_text(
        json.dumps({
            "version": 3,
            "skills": {
                "cmux": {
                    "source": "manaflow-ai/cmux",
                    "sourceType": "github",
                    "sourceUrl": "https://github.com/manaflow-ai/cmux.git",
                    "skillPath": "skills/cmux/SKILL.md",
                    "skillFolderHash": "d7b4a428df22553048a6830f4b5f3733fe1f9393",
                    "installedAt": "2026-05-21T07:24:10.916Z",
                    "updatedAt": "2026-05-21T07:24:10.916Z",
                },
            },
            "dismissed": {"findSkillsPrompt": True},
            "lastSelectedAgents": ["claude-code", "codex"],
        })
    )
    lf = read_lock(p)
    assert lf.version == 3
    assert "cmux" in lf.skills
    e = lf.skills["cmux"]
    assert e.source == "manaflow-ai/cmux"
    assert e.source_type == "github"
    assert e.skill_path == "skills/cmux/SKILL.md"
    # v3 stores upstream pin as skillFolderHash; we surface it via upstream_sha
    # so callers don't have to care which version they're reading.
    assert e.upstream_sha == "d7b4a428df22553048a6830f4b5f3733fe1f9393"


def test_write_preserves_existing_file_version(tmp_path: Path):
    """If we read a v3 file, we write v3 back — never downgrade.
    Preserves interop with `npx skills` reading the same file later.
    """
    p = tmp_path / ".skill-lock.json"
    p.write_text(
        json.dumps({
            "version": 3,
            "skills": {
                "cmux": {
                    "source": "manaflow-ai/cmux",
                    "sourceType": "github",
                    "sourceUrl": "https://github.com/manaflow-ai/cmux.git",
                    "skillPath": "skills/cmux/SKILL.md",
                    "skillFolderHash": "d7b4a428df22553048a6830f4b5f3733fe1f9393",
                    "installedAt": "2026-05-21T07:24:10.916Z",
                    "updatedAt": "2026-05-21T07:24:10.916Z",
                },
            },
            "dismissed": {"findSkillsPrompt": True},
        })
    )
    lf = read_lock(p)
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 3
    assert raw["skills"]["cmux"]["skillFolderHash"] == (
        "d7b4a428df22553048a6830f4b5f3733fe1f9393"
    )
    # Wrapper fields survive round-trip
    assert raw["dismissed"] == {"findSkillsPrompt": True}


def test_write_adds_entry_to_v3_file_using_v3_shape(tmp_path: Path):
    """Adding an entry to a v3 file writes it back in v3 shape."""
    p = tmp_path / ".skill-lock.json"
    p.write_text(
        json.dumps({
            "version": 3, "skills": {}, "dismissed": {},
        })
    )
    lf = read_lock(p)
    lf = add_entry(
        lf, "journal",
        LockEntry(
            source="ajanderson1/journal", source_type="github",
            ref="main", skill_path="SKILL.md",
            upstream_sha="abc123",
        ),
    )
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 3
    entry = raw["skills"]["journal"]
    assert entry["source"] == "ajanderson1/journal"
    # v3 stores the upstream pin under skillFolderHash, not upstreamSha
    assert entry["skillFolderHash"] == "abc123"
    # v3 has timestamps; we synthesise on write
    assert "installedAt" in entry
    assert "updatedAt" in entry


def test_new_file_defaults_to_v1(tmp_path: Path):
    """Writing to a path that doesn't exist creates a v1 file (the project
    lock format). v3 is only used when reading a v3 file back."""
    p = tmp_path / "skills-lock.json"
    lf = LockFile(version=1, skills={})
    lf = add_entry(
        lf, "demo",
        LockEntry(source="o/demo", source_type="github", ref="main"),
    )
    write_lock(p, lf)
    raw = json.loads(p.read_text())
    assert raw["version"] == 1
    assert "demo" in raw["skills"]


# ── clone_url_from_entry — used by both the v3 writer and the read-side
# resolve in `ensure_project_canonical` (#159).


def test_clone_url_from_entry_github_short_form():
    e = LockEntry(source="foo/bar", source_type="github")
    assert clone_url_from_entry(e) == "https://github.com/foo/bar.git"


def test_clone_url_from_entry_gitlab_short_form():
    e = LockEntry(source="foo/bar", source_type="gitlab")
    assert clone_url_from_entry(e) == "https://gitlab.com/foo/bar.git"


def test_clone_url_from_entry_extras_override_wins():
    e = LockEntry(
        source="foo/bar",
        source_type="github",
        extras={"sourceUrl": "git@github.com:override/x.git"},
    )
    assert clone_url_from_entry(e) == "git@github.com:override/x.git"


def test_clone_url_from_entry_passthrough_for_local():
    e = LockEntry(source="/tmp/some-upstream", source_type="local")
    assert clone_url_from_entry(e) == "/tmp/some-upstream"


# ── insteadOf rewriting — SSH-only host support (#251). _apply_insteadof reads
# the user's git config; we isolate it via a fake HOME (.gitconfig) so the real
# host config never leaks in and the autouse GIT_* scrub can't strip our setup.


def _isolated_gitconfig(tmp_path: Path, monkeypatch, body: str) -> None:
    home = tmp_path / "fake-home"
    home.mkdir()
    (home / ".gitconfig").write_text(body)
    monkeypatch.setenv("HOME", str(home))
    # git on some platforms reads XDG/explicit config too; pin those away.
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def test_clone_url_insteadof_rewrites_github(tmp_path: Path, monkeypatch):
    _isolated_gitconfig(
        tmp_path, monkeypatch,
        '[url "git@github.com:"]\n'
        '\tinsteadOf = https://github.com/\n',
    )
    e = LockEntry(source="foo/bar", source_type="github")
    assert clone_url_from_entry(e) == "git@github.com:foo/bar.git"


def test_clone_url_no_insteadof_passthrough(tmp_path: Path, monkeypatch):
    _isolated_gitconfig(tmp_path, monkeypatch, "[user]\n\tname = nobody\n")
    e = LockEntry(source="foo/bar", source_type="github")
    assert clone_url_from_entry(e) == "https://github.com/foo/bar.git"


def test_clone_url_insteadof_longest_match_wins(tmp_path: Path, monkeypatch):
    # Two bases match; git (and us) pick the longest rewrite value.
    _isolated_gitconfig(
        tmp_path, monkeypatch,
        '[url "ssh://git@host/"]\n'
        '\tinsteadOf = https://\n'
        '[url "git@github.com:"]\n'
        '\tinsteadOf = https://github.com/\n',
    )
    e = LockEntry(source="foo/bar", source_type="github")
    assert clone_url_from_entry(e) == "git@github.com:foo/bar.git"


def test_clone_url_explicit_sourceurl_not_rewritten(tmp_path: Path, monkeypatch):
    _isolated_gitconfig(
        tmp_path, monkeypatch,
        '[url "git@github.com:"]\n'
        '\tinsteadOf = https://github.com/\n',
    )
    e = LockEntry(
        source="foo/bar",
        source_type="github",
        extras={"sourceUrl": "https://github.com/foo/bar.git"},
    )
    # Explicit sourceUrl wins verbatim — git rewrites natively at clone time.
    assert clone_url_from_entry(e) == "https://github.com/foo/bar.git"


# --- #345: SHA-pin discriminator -------------------------------------------

_SHA = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"  # 40-hex


@pytest.mark.parametrize(
    "source_type,ref,pinned,tracks_branch",
    [
        ("npm", _SHA, False, False),        # npm + hex ref: NOT a pin (#386 guard)
        ("npm", "main", False, False),      # npm + branch: neither (no clone)
        ("git", _SHA, True, False),         # store-owned + SHA: pinned
        ("git", "main", False, True),       # store-owned + branch: tracks branch
        ("git", None, False, True),         # store-owned + None: tracks default
        ("github", "abc1234", True, False), # short SHA on a git entry: pinned
    ],
)
def test_lockentry_pin_truth_table(source_type, ref, pinned, tracks_branch):
    entry = LockEntry(source="o/r", source_type=source_type, ref=ref)
    assert is_sha_pinned(entry) is pinned
    assert entry.ref_looks_pinned is pinned
    assert entry.ref_tracks_branch is tracks_branch


def test_looks_like_sha_unchanged():
    assert looks_like_sha(_SHA) is True
    assert looks_like_sha("abc1234") is True
    assert looks_like_sha("main") is False
    assert looks_like_sha(None) is False
    assert looks_like_sha("g" * 7) is False  # non-hex
