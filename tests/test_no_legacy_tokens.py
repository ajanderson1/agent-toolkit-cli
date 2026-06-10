"""Arch guard (#350): old token spellings must not reappear in src/.

The only sanctioned host is the DEPRECATED_TOKEN_ALIASES block in
skill_agents.py (deleted in v4 along with this allowance).
"""
import re
from pathlib import Path

OLD_TOKEN = re.compile(
    r"['\"](universal|general-skill|general-agent|general-instructions|general-pi-extension)['\"]"
)
SRC = Path(__file__).resolve().parents[1] / "src"


def _alias_block(text: str) -> tuple[int, int]:
    """Line range (1-based, inclusive) of the DEPRECATED_TOKEN_ALIASES literal."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines, 1) if "DEPRECATED_TOKEN_ALIASES" in l)
    end = next(i for i, l in enumerate(lines[start:], start + 1) if l.strip() == "}")
    return start, end


def test_no_old_tokens_in_src_outside_alias_table():
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        text = py.read_text()
        allowed = _alias_block(text) if py.name == "skill_agents.py" else (0, -1)
        for i, line in enumerate(text.splitlines(), 1):
            if OLD_TOKEN.search(line) and not (allowed[0] <= i <= allowed[1]):
                offenders.append(f"{py.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, "old token spellings outside the alias table:\n" + "\n".join(offenders)
