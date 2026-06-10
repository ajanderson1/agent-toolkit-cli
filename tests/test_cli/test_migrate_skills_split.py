import importlib.util
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
