"""Tests for release candidate build and verification (scripts/build_and_verify_release.py).

Validates:
1. Version/tag guard: pyproject.toml version must match .release-please-manifest.json and tag.
2. Build produces exact wheel and sdist with required contents.
3. Disposable install in a clean venv smoke-tests BOTH CLI and TUI entrypoints.
4. Deployment receipt and SHA256 checksums are generated.
5. Strict artifact selection: rejects stale, extra, or foreign artifacts in dist.
6. Checksum tamper verification: detects mismatch between receipt/sums and artifacts on disk.
7. Exact artifact allowlist: writes exact files to release-artifacts.txt and GITHUB_OUTPUT.
8. Workflow safety: release.yml enforces fail_on_unmatched_files and contains no upload wildcards.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

# Add scripts directory to sys.path so we can import build_and_verify_release
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_and_verify_release import (
    build_artifacts,
    parse_sha256sums,
    compute_sha256,
    generate_receipt,
    get_versions,
    main,
    select_and_verify_artifacts,
    smoke_test_installed_wheel,
    verify_artifacts,
    verify_checksums_and_receipt,
    verify_tag_and_manifest,
)

_CURRENT_REPO_VERSION, _ = get_versions(_REPO_ROOT)


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH")
    return uv


def test_get_versions_reads_pyproject_and_manifest():
    pyproject_ver, manifest_ver = get_versions(_REPO_ROOT)
    assert pyproject_ver == _CURRENT_REPO_VERSION
    assert manifest_ver == _CURRENT_REPO_VERSION
    assert pyproject_ver == manifest_ver


def test_verify_tag_and_manifest_valid():
    ver = verify_tag_and_manifest(_REPO_ROOT, f"v{_CURRENT_REPO_VERSION}")
    assert ver == _CURRENT_REPO_VERSION

    ver_no_tag = verify_tag_and_manifest(_REPO_ROOT, None)
    assert ver_no_tag == _CURRENT_REPO_VERSION


def test_verify_tag_and_manifest_rejects_tag_mismatch():
    with pytest.raises(ValueError, match=f"Tag 'v9.9.9' does not match pyproject.toml version '{_CURRENT_REPO_VERSION}'"):
        verify_tag_and_manifest(_REPO_ROOT, "v9.9.9")


def test_verify_tag_and_manifest_rejects_manifest_mismatch(tmp_path):
    # Create dummy repo root with mismatched manifest
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / "pyproject.toml").write_text(f'[project]\nname = "agent-toolkit"\nversion = "{_CURRENT_REPO_VERSION}"\n')
    (fake_repo / ".release-please-manifest.json").write_text('{\n  ".": "0.0.1"\n}\n')

    with pytest.raises(
        ValueError,
        match=f"pyproject.toml version '{_CURRENT_REPO_VERSION}' does not match .release-please-manifest.json version '0.0.1'",
    ):
        verify_tag_and_manifest(fake_repo, f"v{_CURRENT_REPO_VERSION}")


def test_build_artifacts_and_verify_contents(tmp_path):
    _uv()
    dist_dir = tmp_path / "dist"
    wheel_path, sdist_path = build_artifacts(_REPO_ROOT, dist_dir, version=_CURRENT_REPO_VERSION)

    assert wheel_path.exists()
    assert sdist_path.exists()
    assert wheel_path.name == f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl"
    assert sdist_path.name == f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz"

    # Verify wheel members
    with zipfile.ZipFile(wheel_path) as zf:
        members = zf.namelist()
        assert "agent_toolkit_cli/__init__.py" in members
        assert "agent_toolkit_tui/__init__.py" in members
        assert "agent_toolkit_cli/data/harness-matrix.md" in members
        entry_points = [m for m in members if m.endswith("entry_points.txt")]
        assert entry_points, "entry_points.txt missing in wheel"
        ep_content = zf.read(entry_points[0]).decode("utf-8")
        assert "agent-toolkit-cli = agent_toolkit_cli.cli:main" in ep_content
        assert "agent-toolkit-tui = agent_toolkit_tui.app:main" in ep_content

    # Verify sdist members
    with tarfile.open(sdist_path) as tf:
        sdist_members = tf.getnames()
        assert any(m.endswith("pyproject.toml") for m in sdist_members)
        assert any(m.endswith("docs/agent-toolkit/harness-matrix.md") for m in sdist_members)
        assert any(m.endswith("src/agent_toolkit_cli/__init__.py") for m in sdist_members)
        assert any(m.endswith("src/agent_toolkit_tui/__init__.py") for m in sdist_members)

    verify_artifacts(wheel_path, sdist_path, _CURRENT_REPO_VERSION)


def test_smoke_test_installed_wheel_both_entrypoints(tmp_path):
    _uv()
    dist_dir = tmp_path / "dist"
    wheel_path, sdist_path = build_artifacts(_REPO_ROOT, dist_dir, version=_CURRENT_REPO_VERSION)

    smoke_env_root = tmp_path / "smoke_env"
    results = smoke_test_installed_wheel(wheel_path, _CURRENT_REPO_VERSION, smoke_env_root)

    assert results["cli_version"] == "pass"
    assert results["cli_help"] == "pass"
    assert results["cli_instructions_list"] == "pass"
    assert results["tui_version"] == "pass"
    assert results["tui_headless_pilot"] == "pass"


def test_generate_receipt_creates_valid_json_and_sums(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl"
    wheel_path.write_text("wheel contents")
    sdist_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz"
    sdist_path.write_text("sdist contents")

    smoke_results = {
        "cli_version": "pass",
        "cli_help": "pass",
        "cli_instructions_list": "pass",
        "tui_version": "pass",
        "tui_headless_pilot": "pass",
    }

    receipt_file = dist_dir / "deployment-receipt.json"
    sums_file = dist_dir / "SHA256SUMS"

    receipt = generate_receipt(
        repo_root=_REPO_ROOT,
        tag=f"v{_CURRENT_REPO_VERSION}",
        version=_CURRENT_REPO_VERSION,
        wheel_path=wheel_path,
        sdist_path=sdist_path,
        smoke_results=smoke_results,
        receipt_file=receipt_file,
        sums_file=sums_file,
        expected_commit=generate_receipt.__globals__["get_git_commit"](_REPO_ROOT),
    )

    assert receipt["release"] == f"v{_CURRENT_REPO_VERSION}"
    assert receipt["version"] == _CURRENT_REPO_VERSION
    assert receipt["artifacts"]["wheel"]["name"] == wheel_path.name
    assert receipt["artifacts"]["wheel"]["sha256"] == compute_sha256(wheel_path)
    assert receipt["artifacts"]["sdist"]["name"] == sdist_path.name
    assert receipt["artifacts"]["sdist"]["sha256"] == compute_sha256(sdist_path)
    assert receipt["smoke_tests"] == smoke_results

    assert receipt_file.exists()
    assert sums_file.exists()
    sums_text = sums_file.read_text()
    assert wheel_path.name in sums_text
    assert sdist_path.name in sums_text


def test_select_and_verify_artifacts_rejects_stale_wheel(tmp_path):
    """Regression test for reviewer finding: stale artifacts in dist must be rejected."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "agent_toolkit-5.0.0-py3-none-any.whl").write_text("stale wheel")
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl").write_text("expected wheel")
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz").write_text("expected sdist")

    with pytest.raises(ValueError, match="Unexpected or stale artifacts found in"):
        select_and_verify_artifacts(dist_dir, version=_CURRENT_REPO_VERSION)


def test_select_and_verify_artifacts_rejects_stale_sdist(tmp_path):
    """Regression test: stale sdist in dist must be rejected."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl").write_text("expected wheel")
    (dist_dir / "agent_toolkit-5.0.0.tar.gz").write_text("stale sdist")
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz").write_text("expected sdist")

    with pytest.raises(ValueError, match="Unexpected or stale artifacts found in"):
        select_and_verify_artifacts(dist_dir, version=_CURRENT_REPO_VERSION)


def test_select_and_verify_artifacts_rejects_foreign_archive(tmp_path):
    """Regression test: foreign .whl or .tar.gz in dist must be rejected."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl").write_text("expected wheel")
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz").write_text("expected sdist")
    (dist_dir / "unrelated_pkg-1.0.0-py3-none-any.whl").write_text("foreign wheel")

    with pytest.raises(ValueError, match="Unexpected or stale artifacts found in"):
        select_and_verify_artifacts(dist_dir, version=_CURRENT_REPO_VERSION)


def test_select_and_verify_artifacts_rejects_missing_wheel(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz").write_text("expected sdist")

    with pytest.raises(FileNotFoundError, match="Expected wheel not found"):
        select_and_verify_artifacts(dist_dir, version=_CURRENT_REPO_VERSION)


def test_select_and_verify_artifacts_rejects_missing_sdist(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl").write_text("expected wheel")

    with pytest.raises(FileNotFoundError, match="Expected sdist not found"):
        select_and_verify_artifacts(dist_dir, version=_CURRENT_REPO_VERSION)


def test_verify_checksums_and_receipt_detects_tampering(tmp_path):
    """Ensure tamper check verifies artifact sha256 matches deployment-receipt and SHA256SUMS."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl"
    wheel_path.write_text("clean wheel")
    sdist_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz"
    sdist_path.write_text("clean sdist")

    receipt_file = dist_dir / "deployment-receipt.json"
    sums_file = dist_dir / "SHA256SUMS"

    generate_receipt(
        repo_root=_REPO_ROOT,
        tag=f"v{_CURRENT_REPO_VERSION}",
        version=_CURRENT_REPO_VERSION,
        wheel_path=wheel_path,
        sdist_path=sdist_path,
        smoke_results={
            "cli_version": "pass", "cli_help": "pass", "cli_instructions_list": "pass",
            "tui_version": "pass", "tui_headless_pilot": "pass",
        },
        receipt_file=receipt_file,
        sums_file=sums_file,
        expected_commit=generate_receipt.__globals__["get_git_commit"](_REPO_ROOT),
    )

    # Valid check passes
    commit = generate_receipt.__globals__["get_git_commit"](_REPO_ROOT)
    verify_checksums_and_receipt(
        wheel_path, sdist_path, receipt_file, sums_file,
        expected_tag=f"v{_CURRENT_REPO_VERSION}",
        expected_version=_CURRENT_REPO_VERSION,
        expected_commit=commit,
    )

    # Tamper with wheel
    wheel_path.write_text("tampered wheel contents")
    with pytest.raises(ValueError, match="Checksum mismatch for wheel"):
        verify_checksums_and_receipt(
            wheel_path, sdist_path, receipt_file, sums_file,
            expected_tag=f"v{_CURRENT_REPO_VERSION}",
            expected_version=_CURRENT_REPO_VERSION,
            expected_commit=commit,
        )


def test_verify_checksums_and_receipt_rejects_wrong_tag_and_commit(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    wheel_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl"
    wheel_path.write_text("wheel")
    sdist_path = dist_dir / f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz"
    sdist_path.write_text("sdist")
    receipt_file = dist_dir / "deployment-receipt.json"
    sums_file = dist_dir / "SHA256SUMS"
    receipt = generate_receipt(
        repo_root=_REPO_ROOT,
        tag=f"v{_CURRENT_REPO_VERSION}",
        version=_CURRENT_REPO_VERSION,
        wheel_path=wheel_path,
        sdist_path=sdist_path,
        smoke_results={"all": "pass"},
        receipt_file=receipt_file,
        sums_file=sums_file,
        expected_commit=generate_receipt.__globals__["get_git_commit"](_REPO_ROOT),
    )
    receipt["release"] = "v0.0.0"
    receipt["commit"] = "0" * 40
    receipt_file.write_text(json.dumps(receipt))

    with pytest.raises(ValueError, match="Receipt release does not match expected tag"):
        verify_checksums_and_receipt(
            wheel_path, sdist_path, receipt_file, sums_file,
            expected_tag=f"v{_CURRENT_REPO_VERSION}",
            expected_version=_CURRENT_REPO_VERSION,
            expected_commit=receipt["commit"],
        )


def test_parse_sha256sums_rejects_extra_entries():
    with pytest.raises(ValueError, match="SHA256SUMS must contain exactly"):
        parse_sha256sums("a" * 64 + "  wheel.whl\n" + "b" * 64 + "  sdist.tar.gz\n" + "c" * 64 + "  extra.whl\n")


def test_main_rejects_pre_existing_stale_artifacts(tmp_path):
    """Main should fail if dist directory contains stale artifacts before build."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "agent_toolkit-5.0.0-py3-none-any.whl").write_text("pre-existing old wheel")

    with pytest.raises(ValueError, match="dist directory contains pre-existing distribution artifacts"):
        main([
            "--tag", f"v{_CURRENT_REPO_VERSION}",
            "--dist-dir", str(dist_dir),
            "--repo-root", str(_REPO_ROOT),
        ])


def test_main_skip_build_writes_exact_allowlist_and_github_output(tmp_path, monkeypatch):
    """Main in skip-build mode must output exact release-artifacts.txt and GITHUB_OUTPUT."""
    _uv()
    dist_dir = tmp_path / "dist"
    build_artifacts(_REPO_ROOT, dist_dir, version=_CURRENT_REPO_VERSION)

    github_output_file = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output_file))

    exit_code = main([
        "--tag", f"v{_CURRENT_REPO_VERSION}",
        "--dist-dir", str(dist_dir),
        "--repo-root", str(_REPO_ROOT),
        "--skip-build",
    ])
    assert exit_code == 0

    allowlist_file = dist_dir / "release-artifacts.txt"
    assert allowlist_file.exists()
    lines = [line.strip() for line in allowlist_file.read_text().splitlines() if line.strip()]
    assert len(lines) == 4
    assert any(line.endswith(f"agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl") for line in lines)
    assert any(line.endswith(f"agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz") for line in lines)
    assert any(line.endswith("deployment-receipt.json") for line in lines)
    assert any(line.endswith("SHA256SUMS") for line in lines)

    assert github_output_file.exists()
    gh_output_content = github_output_file.read_text()
    assert f"wheel={dist_dir}/agent_toolkit-{_CURRENT_REPO_VERSION}-py3-none-any.whl" in gh_output_content
    assert f"sdist={dist_dir}/agent_toolkit-{_CURRENT_REPO_VERSION}.tar.gz" in gh_output_content
    assert f"receipt={dist_dir}/deployment-receipt.json" in gh_output_content
    assert f"sums={dist_dir}/SHA256SUMS" in gh_output_content


def test_release_workflow_uses_exact_artifact_outputs_no_wildcards():

    """Verify .github/workflows/release.yml avoids wildcards and sets fail_on_unmatched_files."""
    workflow_path = _REPO_ROOT / ".github" / "workflows" / "release.yml"
    assert workflow_path.exists()
    content = workflow_path.read_text(encoding="utf-8")

    assert "fail_on_unmatched_files: true" in content
    assert "workflow_dispatch:" in content
    assert "required: true" in content
    assert "actions: read" in content
    assert "--expected-sha" in content
    assert "github.ref_name" in content
    assert "gh run list --workflow" in content
    assert "status == \"completed\" and .conclusion == \"success\"" in content
    assert "tag_name: ${{ steps.target.outputs.tag }}" in content
    assert "sort_by(.createdAt) | last" in content
    assert '.headBranch == "main"' in content
    assert '.event == "push"' in content
    runs = [
        {"headSha": "a" * 40, "headBranch": "main", "event": "push", "status": "completed", "conclusion": "success", "createdAt": "2026-01-01T00:00:00Z"},
        {"headSha": "a" * 40, "headBranch": "main", "event": "push", "status": "completed", "conclusion": "failure", "createdAt": "2026-01-02T00:00:00Z"},
    ]
    selected = subprocess.run(
        ["jq", "-c", "--arg", "sha", "a" * 40,
         '[.[] | select(.headSha == $sha and .headBranch == "main" and .event == "push")] | sort_by(.createdAt) | last // empty'],
        input=json.dumps(runs), capture_output=True, text=True, check=True,
    )
    assert json.loads(selected.stdout)["conclusion"] == "failure"
    assert "tag_name: ${{ steps.target.outputs.tag }}" in content
    assert "*.whl" not in content, "Wildcard *.whl found in release.yml"
    assert "*.tar.gz" not in content, "Wildcard *.tar.gz found in release.yml"
    assert "${{ steps.build.outputs.wheel }}" in content
    assert "${{ steps.build.outputs.sdist }}" in content
    assert "${{ steps.build.outputs.receipt }}" in content
    assert "${{ steps.build.outputs.sums }}" in content
