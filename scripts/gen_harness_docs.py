"""Generate the docs-site compatibility matrix and per-harness pages.

Sources (never edited by this script):
  - docs/agent-toolkit/harness-matrix.md — machine-read SSOT (wheel data +
    parity tests). Parsed for the `agent` and `instructions` verdict tables.
  - src/agent_toolkit_cli/skill_agents.py — the skills catalog (skill dirs,
    display names, live adapter status).

Outputs (fully owned by this script — regenerate, never hand-edit):
  - docs/matrix.md
  - docs/harnesses/<slug>.md (one atomic note per harness)
  - the nav block in mkdocs.yml between the GENERATED HARNESS NAV markers

Run from the repo root:  uv run python scripts/gen_harness_docs.py
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_toolkit_cli.skill_agents import AGENTS  # noqa: E402

MATRIX_SSOT = ROOT / "docs/agent-toolkit/harness-matrix.md"
DOCS = ROOT / "docs"
HARNESS_DIR = DOCS / "harnesses"
MKDOCS_YML = ROOT / "mkdocs.yml"

SYNTHETIC = {"universal", "general-skill", "general-agent"}

# Headline harnesses shown in the top table; everything else folds into the
# collapsible "others" section. Curated: the toolkit's primary targets plus
# the widely-known names.
MAIN = [
    "claude-code", "codex", "gemini-cli", "opencode", "pi",
    "cursor", "github-copilot", "windsurf", "cline", "amp", "goose", "junie",
]

AGENT_SUPPORTED = {"symlink", "translate", "config_file+folder", "dual-symlink"}
UNKNOWN = "unknown — no public evidence found"

HOME = str(Path.home())


@dataclass
class AgentRow:
    verdict: str
    paths: str
    fmt: str
    citation: str


@dataclass
class InstrRow:
    verdict: str
    default_file: str
    paths: str
    native: str
    mechanism: str
    citation: str


def _parse_table(lines: list[str], header_prefix: str, ncols: int) -> dict[str, list[str]]:
    """Extract {slug: cells} from the markdown table whose header starts with
    header_prefix. Fails loudly on column-count mismatches."""
    rows: dict[str, list[str]] = {}
    in_table = False
    for line in lines:
        if line.startswith(header_prefix):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != ncols:
                raise SystemExit(
                    f"bad row (expected {ncols} cols, got {len(cells)}): {line!r}"
                )
            slug = cells[0].strip("`")
            rows[slug] = cells[1:]
    if not rows:
        raise SystemExit(f"table not found: {header_prefix!r}")
    return rows


def parse_ssot() -> tuple[dict[str, AgentRow], dict[str, InstrRow]]:
    lines = MATRIX_SSOT.read_text().splitlines()
    agent_raw = _parse_table(
        lines, "| Harness | Verdict | Mechanism | User path / Project path |", 6
    )
    instr_raw = _parse_table(
        lines, "| Harness | Verdict | Default file | Project / Global path |", 7
    )
    agents = {s: AgentRow(c[0], c[2], c[3], c[4]) for s, c in agent_raw.items()}
    instrs = {s: InstrRow(*c) for s, c in instr_raw.items()}
    return agents, instrs


def tilde(p: object) -> str:
    return str(p).replace(HOME, "~")


def sym_agent(v: str) -> str:
    if v in AGENT_SUPPORTED:
        return "✅"
    if v == "unsupported (gap)":
        return "❌"
    if v == "unsupported (by design)":
        return "—"
    if v == UNKNOWN:
        return "❓"
    raise SystemExit(f"unmapped agent verdict: {v!r}")


def sym_instr(v: str) -> str:
    if v in ("native", "symlink"):
        return "✅"
    if v == "unsupported (gap)":
        return "❌"
    if v == "unsupported (by design)":
        return "—"
    if v == UNKNOWN:
        return "❓"
    raise SystemExit(f"unmapped instructions verdict: {v!r}")


def matrix_row(slug: str, agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> str:
    cfg = AGENTS[slug]
    page = f"harnesses/{slug}.md"
    instr_s = sym_instr(instrs[slug].verdict)
    agent_s = sym_agent(agents[slug].verdict)
    instr_cell = f"[{instr_s}]({page}#instructions)" if instr_s != "—" else "—"
    agent_cell = f"[{agent_s}]({page}#agents)" if agent_s != "—" else "—"
    skills_cell = f"[✅]({page}#skills)"
    pi_cell = f"[✅]({page}#pi-extensions)" if slug == "pi" else "—"
    return (
        f"| [{cfg.display_name}]({page}) | {instr_cell} | {skills_cell} "
        f"| {agent_cell} | — | {pi_cell} |"
    )


MATRIX_HEADER = (
    "| Harness | [Instructions](kinds/instructions.md) | [Skills](kinds/skills.md) "
    "| [Agents](kinds/agents.md) | [MCP](kinds/mcp.md) | [Pi extensions](kinds/pi-extensions.md) |"
)
MATRIX_RULE = "|---|:-:|:-:|:-:|:-:|:-:|"


def write_matrix(slugs: list[str], agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> None:
    others = [s for s in slugs if s not in MAIN]
    main_rows = "\n".join(matrix_row(s, agents, instrs) for s in MAIN)
    other_rows = "\n".join(
        "    " + matrix_row(s, agents, instrs) for s in sorted(others)
    )
    out = f"""\
# Compatibility matrix

One row per harness, one column per asset [kind](glossary.md#kind). Every
harness links to its own page with per-kind detail; every tick links straight
to the relevant section. Derived from the machine-read
[SSOT](glossary.md#ssot) (`docs/agent-toolkit/harness-matrix.md`) by
`scripts/gen_harness_docs.py` — edit the SSOT, then regenerate; never edit
this page by hand.

**Legend:** ✅ supported · ❌ not supported (a gap that could be filled) ·
— not applicable (no such concept in the harness, by design) ·
❓ unknown (no public evidence found)

## Main harnesses

{MATRIX_HEADER}
{MATRIX_RULE}
{main_rows}

## Others

??? note "All other harnesses ({len(others)})"

    {MATRIX_HEADER}
    {MATRIX_RULE}
{other_rows}

## The kinds

- **[Instructions](kinds/instructions.md)** — one canonical `AGENTS.md`,
  pointer symlinks for harnesses that read an own-name file.
- **[Skills](kinds/skills.md)** — `SKILL.md` folders projected into each
  harness's skills directory.
- **[Agents (subagents)](kinds/agents.md)** — subagent definitions projected
  per-harness (symlink, translate, or registry mechanisms).
- **[MCP servers](kinds/mcp.md)** — placeholder; not yet a managed kind.
- **[Pi extensions](kinds/pi-extensions.md)** — Pi-only extension packages.
"""
    (DOCS / "matrix.md").write_text(out)


def instr_section(row: InstrRow) -> str:
    lines = ["## Instructions { #instructions }", ""]
    if row.verdict == "native":
        lines.append(
            "Reads the canonical `AGENTS.md` natively — no pointer needed; "
            "the [instructions kind](../kinds/instructions.md) is satisfied as-is."
        )
    elif row.verdict == "symlink":
        lines.append(
            f"Reads a fixed own-name file ({row.default_file}) instead of "
            "`AGENTS.md`. The [instructions kind](../kinds/instructions.md) "
            "creates a same-name pointer symlink → `AGENTS.md`."
        )
    elif row.verdict == "unsupported (gap)":
        lines.append(
            "Not supported (gap) — no default root instruction file a pointer "
            "symlink could satisfy."
        )
    elif row.verdict == "unsupported (by design)":
        lines.append("Not applicable — no root instruction-file concept at all.")
    else:
        lines.append("Unknown — bounded search surfaced no public evidence.")
    lines += [
        "",
        f"- **Verdict:** {row.verdict}",
        f"- **Default file:** {row.default_file or '—'}",
        f"- **Project / global path:** {row.paths or '—'}",
        f"- **Reads `AGENTS.md` natively:** {row.native or '—'}",
        f"- **Source:** {row.citation}",
    ]
    return "\n".join(lines)


def skills_section(slug: str) -> str:
    cfg = AGENTS[slug]
    general = (
        "yes — reads the per-kind general directory directly"
        if cfg.is_universal
        else "no — gets its own projection"
    )
    return "\n".join([
        "## Skills { #skills }",
        "",
        "Supported — every harness in the catalog has a skills directory the "
        "[skills kind](../kinds/skills.md) projects into.",
        "",
        f"- **Project dir:** `{cfg.skills_dir}`",
        f"- **Global dir:** `{tilde(cfg.global_skills_dir)}`",
        f"- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** {general}",
    ])


def agent_section(slug: str, row: AgentRow) -> str:
    cfg = AGENTS[slug]
    lines = ["## Agents (subagents) { #agents }", ""]
    if row.verdict in AGENT_SUPPORTED:
        lines.append(
            f"Supported via the **{row.verdict}** mechanism — see the "
            "[agents kind](../kinds/agents.md) for what each mechanism means."
        )
        lines += [
            "",
            f"- **Mechanism:** {row.verdict}",
            f"- **User / project path:** {row.paths or '—'}",
            f"- **Format:** {row.fmt or '—'}",
        ]
        code_mech = cfg.subagent_mechanism.replace("config_file_folder", "config_file+folder")
        if code_mech == "none":
            lines.append(
                f"- **Toolkit adapter:** currently disabled — {cfg.disabled_reason}"
            )
        else:
            lines.append(f"- **Toolkit adapter:** enabled ({code_mech})")
    else:
        if row.verdict == "unsupported (gap)":
            lines.append("Not supported (gap) — tracked for possible future work.")
        elif row.verdict == "unsupported (by design)":
            lines.append("Not applicable — no subagent concept; won't be filled.")
        else:
            lines.append("Unknown — bounded search surfaced no public evidence.")
        lines += ["", f"- **Verdict:** {row.verdict}"]
        if row.fmt:
            lines.append(f"- **Why:** {row.fmt}")
    lines.append(f"- **Source:** {row.citation}")
    return "\n".join(lines)


def pi_ext_section(slug: str) -> str:
    if slug != "pi":
        return ""
    return "\n".join([
        "## Pi extensions { #pi-extensions }",
        "",
        "Pi is the only harness with an extension-package concept, so the",
        "[pi-extension kind](../kinds/pi-extensions.md) targets Pi alone.",
        "Extensions are git-sourced (branch- or SHA-pinned) and projected by",
        "symlink into Pi's extension directory.",
    ])


def write_harness_page(slug: str, agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> None:
    cfg = AGENTS[slug]
    a, i = agents[slug], instrs[slug]
    instr_s, agent_s = sym_instr(i.verdict), sym_agent(a.verdict)
    instr_how = {
        "✅": "native `AGENTS.md` reader" if i.verdict == "native"
        else f"pointer symlink ({i.default_file} → `AGENTS.md`)",
        "❌": "no pointer-satisfiable root file",
        "—": "no instruction-file concept",
        "❓": "no public evidence",
    }[instr_s]
    agent_how = {
        "✅": a.verdict, "❌": "no file-drop convention",
        "—": "no subagent concept", "❓": "no public evidence",
    }[agent_s]
    pi_row = (
        "| [Pi extensions](../kinds/pi-extensions.md) | [✅](#pi-extensions) | symlink |"
        if slug == "pi"
        else "| [Pi extensions](../kinds/pi-extensions.md) | — | Pi-only kind |"
    )
    instr_cell = f"[{instr_s}](#instructions)" if instr_s != "—" else "—"
    agent_cell = f"[{agent_s}](#agents)" if agent_s != "—" else "—"
    sections = [
        instr_section(i),
        skills_section(slug),
        agent_section(slug, a),
    ]
    pi_sec = pi_ext_section(slug)
    if pi_sec:
        sections.append(pi_sec)
    body = "\n\n".join(sections)
    out = f"""\
# {cfg.display_name}

`{slug}` · one row of the [compatibility matrix](../matrix.md)

| Kind | Support | How |
|---|:-:|---|
| [Instructions](../kinds/instructions.md) | {instr_cell} | {instr_how} |
| [Skills](../kinds/skills.md) | [✅](#skills) | `{cfg.skills_dir}` |
| [Agents (subagents)](../kinds/agents.md) | {agent_cell} | {agent_how} |
| [MCP servers](../kinds/mcp.md) | — | planned kind |
{pi_row}

{body}
"""
    (HARNESS_DIR / f"{slug}.md").write_text(out)


def rewrite_nav(slugs: list[str]) -> None:
    text = MKDOCS_YML.read_text()
    begin = "      # BEGIN GENERATED HARNESS NAV (scripts/gen_harness_docs.py)\n"
    end = "      # END GENERATED HARNESS NAV\n"
    entries = "".join(
        f"      - {AGENTS[s].display_name}: harnesses/{s}.md\n" for s in sorted(slugs)
    )
    pattern = re.compile(re.escape(begin) + ".*?" + re.escape(end), re.DOTALL)
    new, n = pattern.subn(begin + entries + end, text)
    if n != 1:
        raise SystemExit("GENERATED HARNESS NAV markers not found in mkdocs.yml")
    MKDOCS_YML.write_text(new)


def main() -> None:
    agents, instrs = parse_ssot()
    catalog = {s for s in AGENTS if s not in SYNTHETIC}
    if not (set(agents) == set(instrs) == catalog):
        raise SystemExit(
            "harness sets disagree:\n"
            f"  agent table only: {sorted(set(agents) - catalog)}\n"
            f"  instr table only: {sorted(set(instrs) - catalog)}\n"
            f"  catalog only:     {sorted(catalog - set(agents))}"
        )
    slugs = sorted(catalog)
    HARNESS_DIR.mkdir(exist_ok=True)
    for stale in HARNESS_DIR.glob("*.md"):
        stale.unlink()
    for slug in slugs:
        write_harness_page(slug, agents, instrs)
    write_matrix(slugs, agents, instrs)
    rewrite_nav(slugs)
    print(f"wrote docs/matrix.md + {len(slugs)} harness pages + nav block")


if __name__ == "__main__":
    main()
