"""Publishing requires source fit plus explicit, revision-bound inspection evidence."""
import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_asset_catalog import entry, manifest
from tests.test_cli.test_reground import sandbox, repo, git, invoke


def review_record(item, revision):
    from agent_toolkit_cli.skill_catalog import parse_catalog_entries
    selector = parse_catalog_entries(manifest(item))[0].as_dict()
    selector.pop("description")
    return dict(version=1, selector=selector, revision=revision, reviewer="Test curator",
                reviewedAt="2026-10-26", targets=[dict(harness="pi", scope="project")],
                checks={name: dict(passed=True, evidence=f"Inspected {name} for the stated task")
                        for name in ("fit", "quality", "functional", "security", "license")}, limitations=[])


def test_schema_only_never_claims_source_or_quality_verification(tmp_path, sandbox):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest(entry())))
    result = invoke("catalog", "validate", str(path))
    assert "not inspected" in result.output.lower()


def test_admission_blocks_unreviewed_asset_without_fetching(tmp_path, sandbox, monkeypatch):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest(entry())))
    from agent_toolkit_cli import skill_catalog
    monkeypatch.setattr(skill_catalog, "run_git", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no review; no source fetch")))
    result = CliRunner().invoke(main, ["catalog", "validate", str(path), "--admission"])
    assert result.exit_code != 0 and "review" in result.output.lower()


def test_admission_checks_real_source_and_exact_review_revision(tmp_path, sandbox):
    source = repo(tmp_path, {"COMMAND.md": "Summarize the supplied text", "LICENSE": "Test fixture"})
    revision = git(source, "rev-parse", "HEAD")
    item = entry("command", source=source.as_uri(), ref=revision)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest(item)))
    reviews = tmp_path / "reviews/command"
    reviews.mkdir(parents=True)
    record = review_record(item, revision)
    (reviews / "reviewer.json").write_text(json.dumps(record))
    result = invoke("catalog", "validate", str(path), "--admission")
    assert "1" in result.output and "admission" in result.output.lower()
    record["revision"] = "0" * 40
    (reviews / "reviewer.json").write_text(json.dumps(record))
    assert CliRunner().invoke(main, ["catalog", "validate", str(path), "--admission"]).exit_code != 0


def test_inspection_evidence_cannot_hide_incompatible_packaging(tmp_path, sandbox):
    source = repo(tmp_path, {"README.md": "not a command"})
    revision = git(source, "rev-parse", "HEAD")
    item = entry("command", source=source.as_uri(), ref=revision)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest(item)))
    reviews = tmp_path / "reviews/command"
    reviews.mkdir(parents=True)
    (reviews / "reviewer.json").write_text(json.dumps(review_record(item, revision)))
    result = CliRunner().invoke(main, ["catalog", "validate", str(path), "--admission"])
    assert result.exit_code != 0 and "COMMAND.md" in result.output


def test_native_admission_reads_tarball_with_scripts_disabled(tmp_path, sandbox, monkeypatch):
    import base64
    import hashlib
    import io
    import subprocess
    import tarfile
    from agent_toolkit_cli import catalog_admission
    item = dict(kind="pi-extension", key="native", description="Tools", sourceType="npm", source="npm:@example/tools@1.2.3")
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for path, contents in {
            "package/package.json": json.dumps(dict(name="@example/tools", version="1.2.3", pi={"extensions": ["./extensions/index.ts"]})),
            "package/extensions/index.ts": "throw new Error('must never execute')",
        }.items():
            body = contents.encode()
            info = tarfile.TarInfo(path)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    payload = archive.getvalue()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
    def pack(command, **kwargs):
        assert command[:4] == ["npm", "pack", "--ignore-scripts", "--json"]
        directory = command[command.index("--pack-destination") + 1]
        from pathlib import Path
        (Path(directory) / "tools.tgz").write_bytes(payload)
        return subprocess.CompletedProcess(command, 0, json.dumps([dict(filename="tools.tgz", integrity=integrity)]), "")
    monkeypatch.setattr(catalog_admission.subprocess, "run", pack)
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest(item)))
    reviews = tmp_path / "reviews/pi-extension"
    reviews.mkdir(parents=True)
    record = review_record(item, "1.2.3")
    record["integrity"] = integrity
    (reviews / "native.json").write_text(json.dumps(record))
    result = invoke("catalog", "validate", str(path), "--admission")
    assert "1 new/changed" in result.output
    assert not (sandbox / ".pi").exists()


def test_base_limits_admission_to_new_or_changed_selectors(tmp_path, sandbox):
    base = tmp_path / "base.json"
    current = tmp_path / "catalog.json"
    original = entry("skill")
    base.write_text(json.dumps(manifest(original)))
    current.write_text(json.dumps(manifest({**original, "description": "A spelling correction"})))
    result = invoke("catalog", "validate", str(current), "--admission", "--base", str(base))
    assert "0" in result.output
