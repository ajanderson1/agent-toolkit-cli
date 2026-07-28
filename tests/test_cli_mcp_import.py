from pathlib import Path
import json
import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.mcp_manifest import McpManifestEntry

def _manifest_file(home: Path) -> Path:
    return home / ".agent-toolkit" / "mcps-library.json"

def _manifest_entry(slug: str, install_method: str = "npx", **kwargs) -> dict:
    base = {
        "slug": slug,
        "install_method": install_method,
        "transport": "stdio",
        "source": "ctx7",
        "command": "npx" if install_method == "npx" else "test",
        "args": ["-y", "ctx7@9.9.9"] if install_method == "npx" else [],
        "env": [],
        "description": None,
        "resolved_version": "9.9.9" if install_method == "npx" else None,
    }
    base.update(kwargs)
    return base

def _write_manifest(home: Path, entries: dict[str, dict]) -> None:
    path = _manifest_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "mcps": entries}, indent=2) + "\n")

def _read_manifest(home: Path) -> dict:
    return json.loads(_manifest_file(home).read_text())["mcps"]

def test_mcp_import_rejects_lock_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lock_file = tmp_path / "mcps-lock.json"
    lock_file.write_text("{}")
    result = CliRunner().invoke(main, ["mcp", "import", str(lock_file)])
    assert result.exit_code != 0
    assert "records where servers are installed" in result.output
    assert "mcps-library.json" in result.output

def test_mcp_import_adds_servers_and_persists_iteratively(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    
    source_home = tmp_path / "source"
    entries = {
        "alpha": _manifest_entry("alpha"),
        "beta": _manifest_entry("beta")
    }
    _write_manifest(source_home, entries)
    source_manifest = _manifest_file(source_home)
    
    result = CliRunner().invoke(main, ["mcp", "import", str(source_manifest)])
    assert result.exit_code == 0, result.output
    assert "2 added, 0 skipped, 0 failed" in result.output
    assert "alpha  <- ctx7 @ 9.9.9" in result.output
    
    local_manifest = _read_manifest(tmp_path)
    assert "alpha" in local_manifest
    assert "beta" in local_manifest
    assert (tmp_path / ".agent-toolkit" / "mcps" / "alpha" / "config.json").is_file()
    assert (tmp_path / ".agent-toolkit" / "mcps" / "alpha.toolkit.yaml").is_file()

def test_mcp_import_skips_existing_local_and_unsafe(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    
    # Pre-populate existing
    _write_manifest(tmp_path, {"existing": _manifest_entry("existing")})
    
    source_home = tmp_path / "source"
    entries = {
        "existing": _manifest_entry("existing"),
        "local_mcp": _manifest_entry("local_mcp", install_method="local", source="/Users/test/local"),
        "unsafe_mcp": _manifest_entry("unsafe_mcp", install_method="npx", args=["-y", "--token=secret123", "ctx7@9.9.9"])
    }
    _write_manifest(source_home, entries)
    source_manifest = _manifest_file(source_home)
    
    result = CliRunner().invoke(main, ["mcp", "import", str(source_manifest)])
    assert result.exit_code == 0, result.output
    assert "0 added, 3 skipped, 0 failed" in result.output
    assert "existing  (already present)" in result.output
    assert "local_mcp  (local paths cannot be imported)" in result.output
    assert "unsafe_mcp  (unsafe literal at args[1]" in result.output
    assert "secret123" not in result.output

def test_mcp_import_latest_re_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    
    from agent_toolkit_cli.commands.mcp import _resolve
    monkeypatch.setattr(_resolve, "resolve_npm_version", lambda _: "10.0.0")
    
    source_home = tmp_path / "source"
    entries = {
        "alpha": _manifest_entry("alpha") # resolved_version is 9.9.9
    }
    _write_manifest(source_home, entries)
    source_manifest = _manifest_file(source_home)
    
    result = CliRunner().invoke(main, ["mcp", "import", str(source_manifest), "--latest"])
    assert result.exit_code == 0, result.output
    assert "1 added" in result.output
    assert "latest: 10.0.0" in result.output
    
    local_manifest = _read_manifest(tmp_path)
    assert local_manifest["alpha"]["resolved_version"] == "10.0.0"
    assert local_manifest["alpha"]["args"][-1] == "ctx7@10.0.0"

def test_mcp_import_partial_failure_continues_and_returns_1(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    
    import agent_toolkit_cli.mcp_library as mcp_library
    real_write = mcp_library.atomic_write_text
    
    def fail_sidecar(path: Path, content: str) -> None:
        if "alpha.toolkit.yaml" in str(path):
            raise OSError("simulated sidecar failure")
        real_write(path, content)
        
    monkeypatch.setattr(mcp_library, "atomic_write_text", fail_sidecar)
    
    source_home = tmp_path / "source"
    entries = {
        "alpha": _manifest_entry("alpha"),
        "beta": _manifest_entry("beta")
    }
    _write_manifest(source_home, entries)
    source_manifest = _manifest_file(source_home)
    
    result = CliRunner().invoke(main, ["mcp", "import", str(source_manifest)])
    assert result.exit_code == 1
    assert "failed   alpha" in result.output
    assert "added    beta" in result.output
    
    local_manifest = _read_manifest(tmp_path)
    assert "alpha" in local_manifest
    assert "beta" in local_manifest
