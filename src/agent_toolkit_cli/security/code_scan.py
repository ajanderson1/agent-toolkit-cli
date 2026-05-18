"""Security review — category 3: code-level red flags."""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit_cli.security.types import CategoryResult, Verdict

_RED_PATTERNS = [
    (re.compile(r"curl\s+[^|]*\|\s*sh\b"), "curl | sh installer"),
    (re.compile(r"wget\s+[^|]*\|\s*sh\b"), "wget | sh installer"),
    (re.compile(r'"postinstall"\s*:'), "package.json postinstall script"),
]
_AMBER_PATTERNS = [
    (re.compile(r"\beval\s*\("), "eval() call"),
    (re.compile(r"\bexec\s*\("), "exec() call"),
]
_NETWORK_PATTERNS = [
    re.compile(r"\brequests\.(get|post|put|delete|patch)\b"),
    re.compile(r"\burllib\.request\b"),
    re.compile(r"\bfetch\s*\("),
    re.compile(r"\bhttp\.client\b"),
    re.compile(r"\baxios\b"),
]
_TEXT_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".bash", ".md", ".json", ".yaml", ".yml", ".toml"}


def scan_code(path: Path, *, asset_kind: str) -> CategoryResult:
    findings: list[str] = []
    red = False
    amber = False

    target = path if path.is_dir() else path.parent
    files = [path] if path.is_file() else _walk(target)

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for pattern, label in _RED_PATTERNS:
            if pattern.search(text):
                findings.append(f"{f.name}: {label}")
                red = True
        for pattern, label in _AMBER_PATTERNS:
            if pattern.search(text):
                findings.append(f"{f.name}: {label}")
                amber = True
        if asset_kind == "skill":
            for pattern in _NETWORK_PATTERNS:
                if pattern.search(text):
                    findings.append(f"{f.name}: network call in skill body (skills must be inert)")
                    red = True
                    break

    if red:
        verdict = Verdict.RED
    elif amber:
        verdict = Verdict.AMBER
    else:
        verdict = Verdict.GREEN

    if findings:
        evidence = f"{len(findings)} flag(s): " + "; ".join(findings[:5])
        if len(findings) > 5:
            evidence += f"; +{len(findings) - 5} more"
    else:
        evidence = "No red flags detected by automated scan."

    return CategoryResult(
        category="3. Code-level red flags",
        verdict=verdict,
        evidence=evidence,
        raw_signals={"findings": findings},
    )


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in _TEXT_EXTENSIONS:
            out.append(p)
    return out
