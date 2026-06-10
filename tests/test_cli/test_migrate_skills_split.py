import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "migrate_skills_split",
    Path(__file__).parents[2] / "scripts" / "migrate_skills_split.py",
)
mss = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mss)


def test_map_covers_31_mapped_skills_exactly_once():
    placed = [slug for slugs in mss.CATEGORY_MAP.values() for slug in slugs]
    assert len(placed) == len(set(placed)), "a slug is placed in two repos"
    assert set(placed) == mss.MIGRATED_SLUGS
    assert len(mss.MIGRATED_SLUGS) == 31          # 31 tracked dirs
    assert not hasattr(mss, "DELETED_SLUGS")       # botfather is a local rm, not a repo op


def test_servers_is_an_alias_of_contexts_not_a_skill():
    # `servers` lock entries re-point to contexts in skills-infra (broken dup)
    assert mss.ALIAS_REMAP == {"servers": ("contexts", "skills-infra")}


def test_repo_for_slug_and_owner():
    assert mss.OWNER == "ajanderson1"
    assert mss.repo_for_slug("journal") == "skills-journal"
    assert all(r.startswith("skills-") for r in mss.CATEGORY_MAP)


def test_unmapped_slug_guard_lists_strays(tmp_path):
    lock = tmp_path / "skills-lock.json"
    lock.write_text(
        '{"version":1,"skills":{'
        '"journal":{"source":"ajanderson1/skills","skillPath":"journal"},'
        '"servers":{"source":"ajanderson1/skills","skillPath":"servers"},'
        '"newthing":{"source":"ajanderson1/skills","skillPath":"newthing"}}}'
    )
    strays = mss.unmapped_first_party_slugs([lock])
    assert strays == {"newthing"}   # journal mapped, servers is a known alias, newthing is a stray


def test_discover_lock_paths_scans_home_excludes_worktrees(tmp_path):
    (tmp_path / "proj").mkdir()
    a = tmp_path / "proj" / "skills-lock.json"; a.write_text('{"skills":{}}')
    deep = tmp_path / "proj" / "sub" / "deep"; deep.mkdir(parents=True)
    b = deep / "skills-lock.json"; b.write_text('{"skills":{}}')
    wt = tmp_path / "proj" / ".worktrees" / "run-1"; wt.mkdir(parents=True)
    c = wt / "skills-lock.json"; c.write_text('{"skills":{}}')
    cache = tmp_path / ".cache" / "uv" / "git-v0" / "checkouts" / "abc"; cache.mkdir(parents=True)
    d = cache / "skills-lock.json"; d.write_text('{"skills":{}}')
    cwt = tmp_path / "proj" / ".claude" / "worktrees" / "feat-x"; cwt.mkdir(parents=True)
    e = cwt / "skills-lock.json"; e.write_text('{"skills":{}}')

    found = mss.discover_lock_paths([tmp_path])
    assert a in found and b in found
    assert c not in found, ".worktrees locks must be excluded"
    assert d not in found, ".cache locks (uv git checkouts) are disposable snapshots, not scopes"
    assert e not in found, ".claude/worktrees locks must be excluded"


def test_find_lock_scopes_filters_to_source_repo(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text(
        '{"skills":{'
        '"journal":{"source":"ajanderson1/skills","skillPath":"journal"},'
        '"grill-me":{"source":"mattpocock/skills","skillPath":"x"}}}'
    )
    assert mss.find_lock_scopes_for_slug("journal", lock_paths=[glob]) == [glob]
    assert mss.find_lock_scopes_for_slug("grill-me", lock_paths=[glob]) == []


def test_parse_error_fails_loud(tmp_path):
    bad = tmp_path / "skills-lock.json"; bad.write_text("{ not json")
    import pytest
    with pytest.raises(json.JSONDecodeError):
        mss.find_lock_scopes_for_slug("journal", lock_paths=[bad])
