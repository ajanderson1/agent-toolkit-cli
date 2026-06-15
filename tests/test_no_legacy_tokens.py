"""Arch guard (#350, hardened by #356): old token spellings must not appear in src/.

#356 removed the DEPRECATED_TOKEN_ALIASES block, so there is no longer any
sanctioned host — zero old spellings allowed anywhere in src/.
"""
import re
from pathlib import Path

OLD_TOKEN = re.compile(
    r"['\"](universal|general-skill|general-agent|general-instructions|general-pi-extension)['\"]"
)
SRC = Path(__file__).resolve().parents[1] / "src"


def test_no_old_tokens_in_src():
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        text = py.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if OLD_TOKEN.search(line):
                offenders.append(f"{py.relative_to(SRC)}:{i}: {line.strip()}")
    assert not offenders, "old token spellings in src/:\n" + "\n".join(offenders)
