#!/usr/bin/env python3
"""Build and verify repository-owned release artifacts.

Enforces:
1. Manifest & tag guard: pyproject.toml matches .release-please-manifest.json and tag.
2. Build outputs: creates exact wheel and sdist in --dist-dir, rejecting any stale or unexpected files.
3. Artifact verification: verifies required modules, data files, and entrypoints.
4. Disposable install & smoke tests: installs wheel into a clean venv and verifies:
   - CLI --version, --help, and packaged instructions list
   - TUI --version and headless Textual pilot
   All smoke checks execute in a fully sandboxed disposable environment.
5. Receipt & Checksums: generates deployment-receipt.json and SHA256SUMS and validates them.
6. Exact artifact allowlist: outputs exact verified paths without wildcards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Use standard library tomllib if available (Python 3.11+), else fallback to tomlkit
try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:
    import tomlkit as tomllib  # type: ignore[no-redef]


def get_versions(repo_root: Path) -> tuple[str, str]:
    """Read version from pyproject.toml and .release-please-manifest.json."""
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    with pyproject_path.open("rb") as f:
        pyproject_data = tomllib.load(f)

    pyproject_version = str(pyproject_data["project"]["version"])

    manifest_path = repo_root / ".release-please-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f".release-please-manifest.json not found at {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    manifest_version = str(manifest_data.get(".", manifest_data.get("agent-toolkit", "")))
    if not manifest_version:
        raise ValueError(f"No version found for root in {manifest_path}")

    return pyproject_version, manifest_version


def get_git_commit(repo_root: Path) -> str:
    """Return the checked-out commit, never the workflow-triggering commit implicitly."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def verify_tag_and_manifest(
    repo_root: Path, tag: str | None, expected_sha: str | None = None
) -> str:
    """Verify version alignment across pyproject.toml, manifest, and optional git tag.

    Returns the verified version string.
    """
    pyproject_ver, manifest_ver = get_versions(repo_root)

    if pyproject_ver != manifest_ver:
        raise ValueError(
            f"pyproject.toml version '{pyproject_ver}' does not match "
            f".release-please-manifest.json version '{manifest_ver}'"
        )

    if tag is not None:
        expected_tag = f"v{pyproject_ver}"
        if tag != expected_tag:
            raise ValueError(
                f"Tag '{tag}' does not match pyproject.toml version '{pyproject_ver}' (expected '{expected_tag}')"
            )

    if expected_sha is not None:
        actual_sha = get_git_commit(repo_root)
        if actual_sha != expected_sha:
            raise ValueError(
                f"Checked-out commit '{actual_sha}' does not match expected SHA '{expected_sha}'"
            )
        tag_proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", f"refs/tags/{tag}^{{commit}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if tag_proc.stdout.strip() != expected_sha:
            raise ValueError(f"Tag '{tag}' does not resolve to expected SHA '{expected_sha}'")

    return pyproject_ver


def select_and_verify_artifacts(dist_dir: Path, version: str) -> tuple[Path, Path]:
    """Select exact candidate wheel and sdist by expected version and reject any stale/extra files."""
    expected_wheel_name = f"agent_toolkit-{version}-py3-none-any.whl"
    expected_sdist_name = f"agent_toolkit-{version}.tar.gz"

    expected_wheel = dist_dir / expected_wheel_name
    expected_sdist = dist_dir / expected_sdist_name

    # Check for any unexpected distribution archives in dist_dir
    archive_patterns = ["*.whl", "*.tar.gz", "*.zip"]
    found_archives: set[Path] = set()
    for pat in archive_patterns:
        found_archives.update(dist_dir.glob(pat))

    unexpected = [
        f.name for f in found_archives
        if f.name not in (expected_wheel_name, expected_sdist_name)
    ]
    if unexpected:
        raise ValueError(
            f"Unexpected or stale artifacts found in {dist_dir}: {sorted(unexpected)}. "
            f"Only exact candidate artifacts ({expected_wheel_name}, {expected_sdist_name}) are permitted."
        )

    if not expected_wheel.exists():
        raise FileNotFoundError(f"Expected wheel not found: {expected_wheel}")
    if not expected_sdist.exists():
        raise FileNotFoundError(f"Expected sdist not found: {expected_sdist}")

    return expected_wheel, expected_sdist


def build_artifacts(repo_root: Path, out_dir: Path, version: str) -> tuple[Path, Path]:
    """Build wheel and sdist into out_dir via uv build, verifying exact expected output."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable not found on PATH; required for building artifacts")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Reject if dist_dir already contains pre-existing distribution archives
    existing_archives = list(out_dir.glob("*.whl")) + list(out_dir.glob("*.tar.gz"))
    if existing_archives:
        archive_names = [f.name for f in existing_archives]
        raise ValueError(
            f"dist directory contains pre-existing distribution artifacts: {archive_names}. "
            f"To protect against stale builds, dist directory must not contain prior archives before build."
        )

    cmd = [uv, "build", "--out-dir", str(out_dir)]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"uv build failed (exit code {proc.returncode}):\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    return select_and_verify_artifacts(out_dir, version)


def verify_artifacts(wheel_path: Path, sdist_path: Path, version: str) -> None:
    """Validate package structure and required files inside wheel and sdist."""
    expected_wheel_name = f"agent_toolkit-{version}-py3-none-any.whl"
    if wheel_path.name != expected_wheel_name:
        raise ValueError(f"Wheel filename '{wheel_path.name}' does not match expected '{expected_wheel_name}'")

    expected_sdist_name = f"agent_toolkit-{version}.tar.gz"
    if sdist_path.name != expected_sdist_name:
        raise ValueError(f"Sdist filename '{sdist_path.name}' does not match expected '{expected_sdist_name}'")

    # Inspect wheel contents
    with zipfile.ZipFile(wheel_path) as zf:
        members = zf.namelist()
        if "agent_toolkit_cli/__init__.py" not in members:
            raise ValueError("Wheel missing CLI package (agent_toolkit_cli/__init__.py)")
        if "agent_toolkit_tui/__init__.py" not in members:
            raise ValueError("Wheel missing TUI package (agent_toolkit_tui/__init__.py)")
        if "agent_toolkit_cli/data/harness-matrix.md" not in members:
            raise ValueError("Wheel missing force-included harness-matrix.md data file (#305 regression)")

        entry_point_files = [m for m in members if m.endswith("entry_points.txt")]
        if not entry_point_files:
            raise ValueError("Wheel missing entry_points.txt in dist-info")
        ep_content = zf.read(entry_point_files[0]).decode("utf-8")
        if "agent-toolkit-cli = agent_toolkit_cli.cli:main" not in ep_content:
            raise ValueError("Wheel entry_points.txt missing agent-toolkit-cli console script")
        if "agent-toolkit-tui = agent_toolkit_tui.app:main" not in ep_content:
            raise ValueError("Wheel entry_points.txt missing agent-toolkit-tui console script")

    # Inspect sdist contents
    with tarfile.open(sdist_path) as tf:
        sdist_members = tf.getnames()
        if not any(m.endswith("pyproject.toml") for m in sdist_members):
            raise ValueError("Sdist missing pyproject.toml")
        if not any(m.endswith("docs/agent-toolkit/harness-matrix.md") for m in sdist_members):
            raise ValueError("Sdist missing docs/agent-toolkit/harness-matrix.md")
        if not any(m.endswith("src/agent_toolkit_cli/__init__.py") for m in sdist_members):
            raise ValueError("Sdist missing src/agent_toolkit_cli")
        if not any(m.endswith("src/agent_toolkit_tui/__init__.py") for m in sdist_members):
            raise ValueError("Sdist missing src/agent_toolkit_tui")


def smoke_test_installed_wheel(
    wheel_path: Path,
    version: str,
    tmp_path: Path,
) -> dict[str, str]:
    """Install built wheel in a clean venv and smoke test BOTH CLI and TUI entrypoints.

    Runs all smoke tests with strictly sandboxed environment variables.
    """
    venv_dir = tmp_path / "smoke_venv"
    sandbox_dir = tmp_path / "smoke_sandbox"
    workdir = tmp_path / "smoke_workdir"

    for d in (venv_dir, sandbox_dir, workdir):
        d.mkdir(parents=True, exist_ok=True)

    # Create sandbox directories
    sandbox_home = sandbox_dir / "home"
    sandbox_xdg = sandbox_dir / "xdg"
    sandbox_codex = sandbox_dir / "codex"
    sandbox_claude = sandbox_dir / "claude"
    sandbox_vibe = sandbox_dir / "vibe"
    sandbox_pi = sandbox_dir / "pi"

    for d in (sandbox_home, sandbox_xdg, sandbox_codex, sandbox_claude, sandbox_vibe, sandbox_pi):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Create clean disposable venv
    uv = shutil.which("uv")
    if uv is not None:
        res = subprocess.run([uv, "venv", str(venv_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, timeout=120)
    else:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, timeout=120)

    bindir = "Scripts" if sys.platform == "win32" else "bin"
    py = venv_dir / bindir / ("python.exe" if sys.platform == "win32" else "python")
    cli = venv_dir / bindir / "agent-toolkit-cli"
    tui = venv_dir / bindir / "agent-toolkit-tui"

    # 2. Install wheel
    if uv is not None:
        install_cmd = [uv, "pip", "install", "--python", str(py), str(wheel_path)]
    else:
        install_cmd = [str(py), "-m", "pip", "install", "--quiet", str(wheel_path)]

    install_res = subprocess.run(install_cmd, capture_output=True, text=True, timeout=300)
    if install_res.returncode != 0:
        raise RuntimeError(
            f"Failed to install wheel into disposable venv:\n"
            f"STDOUT:\n{install_res.stdout}\nSTDERR:\n{install_res.stderr}"
        )

    # 3. Prepare isolated environment
    env = os.environ.copy()
    env["HOME"] = str(sandbox_home)
    env["USERPROFILE"] = str(sandbox_home)
    env["XDG_CONFIG_HOME"] = str(sandbox_xdg)
    env["CODEX_HOME"] = str(sandbox_codex)
    env["CLAUDE_CONFIG_DIR"] = str(sandbox_claude)
    env["VIBE_HOME"] = str(sandbox_vibe)
    env["PI_CODING_AGENT_DIR"] = str(sandbox_pi)
    env.pop("AGENT_TOOLKIT_SKILLS_ROOT", None)
    env.pop("AGENT_TOOLKIT_TUI_SETTINGS", None)

    results: dict[str, str] = {}

    # Smoke 1: CLI --version
    proc = subprocess.run(
        [str(cli), "--version"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or version not in proc.stdout:
        raise RuntimeError(
            f"agent-toolkit-cli --version failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results["cli_version"] = "pass"

    # Smoke 2: CLI --help
    proc = subprocess.run(
        [str(cli), "--help"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or "Usage:" not in proc.stdout:
        raise RuntimeError(
            f"agent-toolkit-cli --help failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results["cli_help"] = "pass"

    # Smoke 3: CLI packaged data (instructions list)
    proc = subprocess.run(
        [str(cli), "instructions", "list"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "claude-code" not in proc.stdout:
        raise RuntimeError(
            f"agent-toolkit-cli instructions list failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results["cli_instructions_list"] = "pass"

    # Smoke 4: TUI --version
    proc = subprocess.run(
        [str(tui), "--version"],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or version not in proc.stdout:
        raise RuntimeError(
            f"agent-toolkit-tui --version failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results["tui_version"] = "pass"

    # Smoke 5: TUI headless Textual pilot
    pilot_code = (
        "import asyncio\n"
        "from agent_toolkit_tui.app import TUIApp\n"
        "\n"
        "async def _pilot_smoke():\n"
        "    app = TUIApp()\n"
        "    async with app.run_test() as pilot:\n"
        "        await pilot.pause()\n"
        "        assert app.is_running\n"
        "\n"
        "asyncio.run(_pilot_smoke())\n"
        "print('TUI_PILOT_SUCCESS')\n"
    )
    proc = subprocess.run(
        [str(py), "-c", pilot_code],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "TUI_PILOT_SUCCESS" not in proc.stdout:
        raise RuntimeError(
            f"agent-toolkit-tui headless pilot failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    results["tui_headless_pilot"] = "pass"

    return results


def compute_sha256(path: Path) -> str:
    """Compute sha256 checksum for a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _get_git_commit_for_receipt(repo_root: Path) -> str:
    """Return checked-out HEAD; workflow-trigger SHA is not artifact provenance."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def generate_receipt(
    repo_root: Path,
    tag: str,
    version: str,
    wheel_path: Path,
    sdist_path: Path,
    smoke_results: dict[str, str],
    receipt_file: Path,
    sums_file: Path,
    expected_commit: str,
) -> dict:
    """Generate receipt and checksums bound to the checked-out release commit."""
    wheel_sha = compute_sha256(wheel_path)
    sdist_sha = compute_sha256(sdist_path)
    commit = get_git_commit(repo_root)
    if commit != expected_commit:
        raise ValueError(f"Checked-out commit '{commit}' does not match expected SHA '{expected_commit}'")
    now_iso = datetime.now(timezone.utc).isoformat()

    receipt = {
        "release": tag,
        "version": version,
        "commit": commit,
        "timestamp": now_iso,
        "artifacts": {
            "wheel": {
                "name": wheel_path.name,
                "bytes": wheel_path.stat().st_size,
                "sha256": wheel_sha,
            },
            "sdist": {
                "name": sdist_path.name,
                "bytes": sdist_path.stat().st_size,
                "sha256": sdist_sha,
            },
        },
        "smoke_tests": smoke_results,
        "scope": "CLI/TUI package candidate verified; no PyPI publish",
    }

    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    with receipt_file.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)

    sums_content = f"{wheel_sha}  {wheel_path.name}\n{sdist_sha}  {sdist_path.name}\n"
    with sums_file.open("w", encoding="utf-8") as f:
        f.write(sums_content)

    return receipt


def parse_sha256sums(content: str) -> dict[str, str]:
    """Parse a strict two-entry SHA256SUMS file."""
    entries: dict[str, str] = {}
    for line in content.splitlines():
        parts = line.split("  ")
        if len(parts) != 2 or len(parts[0]) != 64 or any(c not in "0123456789abcdef" for c in parts[0]):
            raise ValueError(f"Malformed SHA256SUMS line: {line!r}")
        if not parts[1] or parts[1] in entries:
            raise ValueError(f"Duplicate or empty SHA256SUMS filename: {parts[1]!r}")
        entries[parts[1]] = parts[0]
    if len(entries) != 2:
        raise ValueError(f"SHA256SUMS must contain exactly two entries, found {len(entries)}")
    return entries


def verify_checksums_and_receipt(
    wheel_path: Path,
    sdist_path: Path,
    receipt_file: Path,
    sums_file: Path,
    *,
    expected_tag: str,
    expected_version: str,
    expected_commit: str,
) -> None:
    """Verify candidate identity, successful smoke tests, and exact artifact hashes."""
    if not receipt_file.exists():
        raise FileNotFoundError(f"Receipt file missing: {receipt_file}")
    if not sums_file.exists():
        raise FileNotFoundError(f"SHA256SUMS file missing: {sums_file}")

    with receipt_file.open("r", encoding="utf-8") as f:
        receipt = json.load(f)

    if receipt.get("release") != expected_tag:
        raise ValueError(f"Receipt release does not match expected tag '{expected_tag}'")
    if receipt.get("version") != expected_version:
        raise ValueError(f"Receipt version does not match expected version '{expected_version}'")
    if receipt.get("commit") != expected_commit:
        raise ValueError(f"Receipt commit does not match expected SHA '{expected_commit}'")
    smoke_tests = receipt.get("smoke_tests")
    required_smoke = {"cli_version", "cli_help", "cli_instructions_list", "tui_version", "tui_headless_pilot"}
    if not isinstance(smoke_tests, dict) or set(smoke_tests) != required_smoke or any(
        result != "pass" for result in smoke_tests.values()
    ):
        raise ValueError("Receipt smoke tests are missing or not all passing")

    actual_wheel_sha = compute_sha256(wheel_path)
    actual_sdist_sha = compute_sha256(sdist_path)

    receipt_wheel = receipt["artifacts"]["wheel"]
    if receipt_wheel["sha256"] != actual_wheel_sha:
        raise ValueError(
            f"Checksum mismatch for wheel in receipt: expected {receipt_wheel['sha256']}, got {actual_wheel_sha}"
        )
    if receipt_wheel["bytes"] != wheel_path.stat().st_size:
        raise ValueError(
            f"Size mismatch for wheel in receipt: expected {receipt_wheel['bytes']}, got {wheel_path.stat().st_size}"
        )

    if receipt_wheel.get("name") != wheel_path.name:
        raise ValueError(f"Receipt wheel name does not match expected '{wheel_path.name}'")

    receipt_sdist = receipt["artifacts"]["sdist"]
    if receipt_sdist["sha256"] != actual_sdist_sha:
        raise ValueError(
            f"Checksum mismatch for sdist in receipt: expected {receipt_sdist['sha256']}, got {actual_sdist_sha}"
        )
    if receipt_sdist["bytes"] != sdist_path.stat().st_size:
        raise ValueError(
            f"Size mismatch for sdist in receipt: expected {receipt_sdist['bytes']}, got {sdist_path.stat().st_size}"
        )

    if receipt_sdist.get("name") != sdist_path.name:
        raise ValueError(f"Receipt sdist name does not match expected '{sdist_path.name}'")

    sums = parse_sha256sums(sums_file.read_text(encoding="utf-8"))
    expected_sums = {wheel_path.name: actual_wheel_sha, sdist_path.name: actual_sdist_sha}
    if sums != expected_sums:
        raise ValueError(f"SHA256SUMS entries do not exactly match expected artifacts: {expected_sums}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and verify release artifacts.")
    parser.add_argument("--tag", help="Git release tag (e.g. v5.9.1)")
    parser.add_argument("--expected-sha", help="Expected immutable release commit SHA")
    parser.add_argument("--dist-dir", default="dist", help="Directory for distribution artifacts (default: dist)")
    parser.add_argument("--repo-root", default=".", help="Root of repository (default: .)")
    parser.add_argument("--skip-build", action="store_true", help="Skip build and verify existing artifacts in dist-dir")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    dist_dir = (repo_root / args.dist_dir).resolve() if not Path(args.dist_dir).is_absolute() else Path(args.dist_dir)

    print(f"==> Verifying release candidate at {repo_root}")
    version = verify_tag_and_manifest(repo_root, args.tag, expected_sha=args.expected_sha)
    expected_sha = args.expected_sha or get_git_commit(repo_root)
    tag = args.tag or f"v{version}"
    print(f"✓ Version verified: {version} (tag: {tag})")

    if args.skip_build:
        print(f"==> Selecting existing artifacts from {dist_dir}")
        wheel_path, sdist_path = select_and_verify_artifacts(dist_dir, version)
        print(f"✓ Using existing artifacts: {wheel_path.name}, {sdist_path.name}")
    else:
        print(f"==> Building wheel and sdist into {dist_dir} via uv build")
        wheel_path, sdist_path = build_artifacts(repo_root, dist_dir, version)
        print(f"✓ Built: {wheel_path.name}")
        print(f"✓ Built: {sdist_path.name}")

    print("==> Validating artifact structure and contents")
    verify_artifacts(wheel_path, sdist_path, version)
    print("✓ Artifact structure verified")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        print("==> Executing isolated disposable install and smoke tests")
        smoke_results = smoke_test_installed_wheel(wheel_path, version, tmp_path)
        for check, res in smoke_results.items():
            print(f"  ✓ {check}: {res}")

    receipt_file = dist_dir / "deployment-receipt.json"
    sums_file = dist_dir / "SHA256SUMS"
    print("==> Generating receipt and SHA256 checksums")
    generate_receipt(
        repo_root=repo_root,
        tag=tag,
        version=version,
        wheel_path=wheel_path,
        sdist_path=sdist_path,
        smoke_results=smoke_results,
        receipt_file=receipt_file,
        sums_file=sums_file,
        expected_commit=expected_sha,
    )
    print(f"✓ Receipt written: {receipt_file}")
    print(f"✓ Checksums written: {sums_file}")

    print("==> Validating generated receipt and checksums against artifacts on disk")
    verify_checksums_and_receipt(
        wheel_path, sdist_path, receipt_file, sums_file,
        expected_tag=tag, expected_version=version, expected_commit=expected_sha,
    )
    print("✓ Checksums and receipt verified against disk artifacts")

    # Write exact release artifacts allowlist
    allowlist_file = dist_dir / "release-artifacts.txt"
    verified_files = [wheel_path, sdist_path, receipt_file, sums_file]
    with allowlist_file.open("w", encoding="utf-8") as f:
        for p in verified_files:
            f.write(f"{p}\n")
    print(f"✓ Exact release artifact allowlist written: {allowlist_file}")

    # Emit step outputs for GitHub Actions if GITHUB_OUTPUT is present
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"wheel={wheel_path}\n")
            f.write(f"sdist={sdist_path}\n")
            f.write(f"receipt={receipt_file}\n")
            f.write(f"sums={sums_file}\n")
            f.write(f"allowlist={allowlist_file}\n")
        print("✓ Emitted exact artifact paths to GITHUB_OUTPUT")

    print(f"==> Release candidate verification COMPLETE for {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
