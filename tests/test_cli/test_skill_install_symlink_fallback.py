"""_symlink_or_copy creates a symlink when possible; falls back to copy."""
from pathlib import Path

from agent_toolkit_cli.skill_install import _symlink_or_copy


def test_symlink_or_copy_creates_symlink(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("hi")
    dest = tmp_path / "dest"

    mode = _symlink_or_copy(src, dest)
    assert mode == "symlink"
    assert dest.is_symlink()
    assert dest.resolve() == src.resolve()
    assert (dest / "f.txt").read_text() == "hi"


def test_symlink_or_copy_falls_back_to_copy(monkeypatch, tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("hi")
    dest = tmp_path / "dest"

    def raise_oserror(self, target, target_is_directory=False):
        raise OSError("simulated platform refusal")
    monkeypatch.setattr(Path, "symlink_to", raise_oserror)

    mode = _symlink_or_copy(src, dest)
    assert mode == "copy"
    assert not dest.is_symlink()
    assert dest.is_dir()
    assert (dest / "f.txt").read_text() == "hi"


def test_symlink_or_copy_refuses_to_overwrite(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    import pytest
    from agent_toolkit_cli.skill_install import InstallError
    with pytest.raises(InstallError):
        _symlink_or_copy(src, dest)
