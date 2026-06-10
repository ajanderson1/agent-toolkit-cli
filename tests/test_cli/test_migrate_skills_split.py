import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "migrate_skills_split",
    Path(__file__).parents[2] / "scripts" / "migrate_skills_split.py",
)
mss = importlib.util.module_from_spec(_SPEC)
# register BEFORE exec: dataclass field-type resolution under
# `from __future__ import annotations` looks the module up in sys.modules
sys.modules[_SPEC.name] = mss
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
    a = tmp_path / "proj" / "skills-lock.json"
    a.write_text('{"skills":{}}')
    deep = tmp_path / "proj" / "sub" / "deep"
    deep.mkdir(parents=True)
    b = deep / "skills-lock.json"
    b.write_text('{"skills":{}}')
    wt = tmp_path / "proj" / ".worktrees" / "run-1"
    wt.mkdir(parents=True)
    c = wt / "skills-lock.json"
    c.write_text('{"skills":{}}')
    cache = tmp_path / ".cache" / "uv" / "git-v0" / "checkouts" / "abc"
    cache.mkdir(parents=True)
    d = cache / "skills-lock.json"
    d.write_text('{"skills":{}}')
    cwt = tmp_path / "proj" / ".claude" / "worktrees" / "feat-x"
    cwt.mkdir(parents=True)
    e = cwt / "skills-lock.json"
    e.write_text('{"skills":{}}')

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
    bad = tmp_path / "skills-lock.json"
    bad.write_text("{ not json")
    import pytest
    with pytest.raises(json.JSONDecodeError):
        mss.find_lock_scopes_for_slug("journal", lock_paths=[bad])


def _fake_agents(slug, scope, lock):
    # injectable projection scanner: lock entries do NOT record agents (parked
    # #230) — live capture scans on-disk projection symlinks, tests stub it
    return ("claude",)


def test_action_plan_orders_global_before_project(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    proj = tmp_path / "p" / "skills-lock.json"
    proj.parent.mkdir()
    proj.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')

    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[proj], projected_agents=_fake_agents)
    phases = [a.phase for a in plan]
    assert phases == sorted(phases), "all phase-A actions precede phase-B"
    a_verbs = [(a.verb, a.scope) for a in plan if a.phase == "A"]
    # remove -> add -> install: the trailing install restores the GLOBAL agent
    # projections that `skill remove --force` deletes and `skill add` does NOT
    # recreate (add only recreates the library dir + lock entry)
    assert a_verbs == [("remove", glob), ("add", glob), ("install", glob)]
    b_verbs = [(a.verb, a.scope, a.agents) for a in plan if a.phase == "B"]
    assert b_verbs == [("uninstall", proj, ("claude",)), ("install", proj, ("claude",))]
    assert all(a.new_source == "ajanderson1/skills-journal" for a in plan if a.verb in ("add", "install"))


def test_action_plan_noop_when_already_migrated(tmp_path):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    assert plan == []


def test_action_plan_project_only_slug_gets_prerequisite_global_add(tmp_path):
    # apk-workbench shape: registered in project locks, ABSENT from the global
    # lock (live count: 30 global first-party slugs, not 31). Phase B install -p
    # re-derives from the global entry, so a prerequisite Phase A add is
    # mandatory (spec mandate) — without it, uninstall -p drops the project
    # entry and install -p raises "not in global library", stranding the slug.
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{}}')
    proj = tmp_path / "p" / "skills-lock.json"
    proj.parent.mkdir()
    proj.write_text('{"skills":{"apk-workbench":{"source":"ajanderson1/skills","skillPath":"apk-workbench"}}}')
    plan = mss.build_action_plan(slugs=["apk-workbench"], global_lock=glob,
                                 project_locks=[proj], projected_agents=_fake_agents)
    a_verbs = [a.verb for a in plan if a.phase == "A"]
    assert a_verbs == ["add"], "no remove (nothing registered), but the prerequisite add MUST be planned"


def test_action_plan_recovers_stranded_slug_after_failed_add(tmp_path):
    # mid-apply abort state: remove succeeded, add failed -> slug on NO source.
    # Re-run must re-emit the add, not silently skip the slug (an old-source-only
    # predicate would make a stranded slug vanish from the plan forever).
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    assert [(a.phase, a.verb) for a in plan] == [("A", "add")]


def test_projected_agents_collapses_bundle_to_universal_token(tmp_path):
    # the captured list is fed straight into `--agents`, and _resolve_agents
    # (commands/skill/__init__.py) hard-rejects synthetic catalog names
    # ("general-skill"/"general-agent", which share skills_dir .agents/skills)
    # — a universal-bundle link must surface as the literal "universal" token
    # (accepted first-class) and the synthetics must NEVER appear
    proj = tmp_path / "p"
    lock = proj / "skills-lock.json"
    bundle = proj / ".agents" / "skills"
    bundle.mkdir(parents=True)
    canon = proj / ".canonical-journal"
    canon.mkdir()
    (bundle / "journal").symlink_to(canon)
    lock.write_text('{"skills":{}}')
    agents = mss.projected_agents("journal", "project", lock)
    assert "universal" in agents
    assert not {"general-skill", "general-agent"} & set(agents)


def test_secret_scan_flags_credential_files_and_uuids(tmp_path):
    skill = tmp_path / "bank-statement-download" / "references"
    skill.mkdir(parents=True)
    (skill / "credentials.md").write_text(
        "N26 vault item: 3f2a9c14-1b2d-4e6a-9f01-aabbccddeeff\nacct 51412937\n"
    )
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "SKILL.md").write_text("name: journal\n")

    hits = mss.scan_for_secrets(tmp_path)
    files = {str(h.relative_to(tmp_path)) for h in hits}
    assert "bank-statement-download/references/credentials.md" in files
    assert not any("journal" in f for f in files)


def test_action_plan_flags_projectionless_scope_for_manual_decision(tmp_path):
    # live state: several project locks (whatsapp_sync et al.) hold old-source
    # entries with ZERO projection symlinks. A planned uninstall/install pair
    # would let `uninstall -p` destroy the lock entry BEFORE any empty-agents
    # guard fires, and the journal would replay the doomed install forever.
    # Plan a needs-decision marker instead; main() blocks --apply on these.
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills-journal","skillPath":"journal"}}}')
    proj = tmp_path / "p" / "skills-lock.json"
    proj.parent.mkdir()
    proj.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[proj],
                                 projected_agents=lambda *a: ())
    assert [(a.phase, a.verb) for a in plan] == [("B", "needs-decision")]


def test_render_plan_groups_by_phase(tmp_path, capsys):
    glob = tmp_path / "global-lock.json"
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    plan = mss.build_action_plan(slugs=["journal"], global_lock=glob,
                                 project_locks=[], projected_agents=_fake_agents)
    mss.render_plan(plan)
    out = capsys.readouterr().out
    assert "Phase A" in out and "remove journal" in out and "ajanderson1/skills-journal" in out


def test_main_dryrun_fails_loud_on_unmapped(tmp_path, monkeypatch, capsys):
    # an unmapped first-party slug must abort the dry-run, not be skipped
    glob = tmp_path / "skills-lock.json"
    glob.write_text('{"skills":{"newthing":{"source":"ajanderson1/skills","skillPath":"newthing"}}}')
    import pytest
    with pytest.raises(SystemExit):
        mss.main(["--global-lock", str(glob), "--roots", str(tmp_path)])
    assert "unmapped" in capsys.readouterr().out.lower()


def test_main_excludes_global_lock_from_project_scopes(tmp_path, monkeypatch, capsys):
    # ~/.agent-toolkit/skills-lock.json matches the $HOME rglob; treating it as
    # a project scope would have Phase B `uninstall -p` (cwd=~/.agent-toolkit)
    # strip the just-migrated GLOBAL entries, then `install -p` fail and strand
    # hermetic: stub the scanner + journal so this never reads real $HOME state
    # (a real mid-migration journal would inject phantom Phase B rows and
    # spuriously fail the "Phase B" assertion below)
    monkeypatch.setattr(mss, "projected_agents", _fake_agents)
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    glob = tmp_path / ".agent-toolkit" / "skills-lock.json"
    glob.parent.mkdir()
    glob.write_text('{"skills":{"journal":{"source":"ajanderson1/skills","skillPath":"journal"}}}')
    mss.main(["--global-lock", str(glob), "--roots", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Phase B" not in out, "global lock must never appear as a Phase B scope"


def test_journal_pending_installs_reemits_unpaired_uninstall(tmp_path, monkeypatch):
    # crash/abort between Phase B uninstall and install drops the project lock
    # entry — without the journal, re-run planning (which keys on lock entries)
    # would silently strand that project scope
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    mss._journal_append({"event": "uninstalled", "slug": "journal",
                         "scope": str(tmp_path / "p" / "skills-lock.json"),
                         "agents": ["claude"]})
    pending = mss.journal_pending_installs()
    assert [(x.verb, x.slug, x.agents) for x in pending] == [("install", "journal", ("claude",))]


def test_journal_pending_installs_skips_empty_agents(tmp_path, monkeypatch, capsys):
    # a journaled uninstall with agents=[] must NOT be replayed as a live
    # install — it would hit the empty-agents refusal on every re-run (an
    # infinite abort loop fixable only by hand-editing the journal). Skip it
    # loudly and leave the scope for manual re-install.
    monkeypatch.setattr(mss, "JOURNAL", tmp_path / "journal.jsonl")
    mss._journal_append({"event": "uninstalled", "slug": "journal",
                         "scope": str(tmp_path / "p" / "skills-lock.json"),
                         "agents": []})
    assert mss.journal_pending_installs() == []
    assert "manual re-install required" in capsys.readouterr().out
