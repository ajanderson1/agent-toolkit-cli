"""Generate the docs-site compatibility matrix and per-harness pages.

Sources (never edited by this script):
  - docs/agent-toolkit/harness-matrix.md — machine-read SSOT (wheel data +
    parity tests). Parsed for the `agent` and `instructions` verdict tables.
  - src/agent_toolkit_cli/skill_agents.py — the skills catalog (skill dirs,
    display names, live adapter status).
  - MCP_ADAPTERS (below) — the hand-maintained set of harnesses with an MCP
    config-injection adapter, kept in lockstep with mcp_install.py.

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

SYNTHETIC = {"standard", "standard-skill", "standard-agent"}

# Harnesses the toolkit can project an MCP server into, via a config-injection
# adapter (src/agent_toolkit_cli/mcp_install.py — target-config detection at
# :77-83). This is the hand-maintained MCP support source until per-harness MCP
# data lands in the machine-read SSOT (harness-matrix.md). Keep it in lockstep
# with mcp_install.py: ✅ only for slugs here, `—` (toolkit gap) for the rest.
# `standard` is a projection token, NOT a harness, so it is not listed.
MCP_ADAPTERS = {"claude-code", "codex", "opencode", "pi"}

# Headline harnesses: pinned to the top of the matrix (in this order) and
# listed first + bolded in the nav; everything else folds into the expandable
# alphabetical rest.
MAIN = ["claude-code", "pi", "codex", "gemini-cli", "opencode"]


def _gh(org: str) -> str:
    """GitHub org/user avatar — the project's de-facto logo."""
    return f"https://github.com/{org}.png?size=64"


def _fav(domain: str) -> str:
    """Favicon of the product's home domain, via Google's favicon service."""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


# Small logo shown in each harness page title. Empty string = no public logo
# identified; the page renders without one. Every catalog slug MUST have an
# entry — main() fails loudly otherwise.
LOGOS: dict[str, str] = {
    "adal": _fav("sylph.ai"),
    "aider-desk": _gh("hotovo"),
    "amp": _fav("ampcode.com"),
    "antigravity": _fav("antigravity.google"),
    "augment": _fav("augmentcode.com"),
    "bob": _fav("bob.ibm.com"),
    "claude-code": _fav("claude.com"),
    "cline": _fav("cline.bot"),
    "codearts-agent": _fav("huaweicloud.com"),
    "codebuddy": _fav("codebuddy.ai"),
    "codemaker": _gh("codemakerai"),
    "codestudio": "",  # product unidentified (SSOT: exhaustive search, no source)
    "codex": _fav("openai.com"),
    "command-code": _fav("commandcode.ai"),
    "continue": _fav("continue.dev"),
    "cortex": _fav("snowflake.com"),
    "crush": _gh("charmbracelet"),
    "cursor": _fav("cursor.com"),
    "deepagents": _gh("langchain-ai"),
    "devin": _fav("devin.ai"),
    "dexto": _gh("truffle-ai"),
    "droid": _fav("factory.ai"),
    "firebender": _fav("firebender.com"),
    "forgecode": _fav("forgecode.dev"),
    "gemini-cli": _gh("google-gemini"),
    "github-copilot": _gh("github"),
    "goose": _gh("block"),
    "hermes-agent": _fav("nousresearch.com"),
    "iflow-cli": _fav("iflow.cn"),
    "junie": _fav("jetbrains.com"),
    "kilo": _fav("kilo.ai"),
    "kimi-cli": _gh("moonshotai"),
    "kiro-cli": _fav("kiro.dev"),
    "kode": _gh("shareAI-lab"),
    "mcpjam": _fav("mcpjam.com"),
    "mistral-vibe": _fav("mistral.ai"),
    "mux": _fav("coder.com"),
    "neovate": _gh("neovateai"),
    "openclaw": _fav("openclaw.ai"),
    "opencode": _fav("opencode.ai"),
    "openhands": _fav("all-hands.dev"),
    "pi": _fav("pi.dev"),
    "pochi": _fav("getpochi.com"),
    "qoder": _fav("qoder.com"),
    "qwen-code": _gh("QwenLM"),
    "replit": _fav("replit.com"),
    "roo": _fav("roocode.com"),
    "rovodev": _fav("atlassian.com"),
    "tabnine-cli": _fav("tabnine.com"),
    "trae": _fav("trae.ai"),
    "trae-cn": _fav("trae.cn"),
    "warp": _fav("warp.dev"),
    "windsurf": _fav("windsurf.com"),
    "zencoder": _fav("zencoder.ai"),
}

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


# Bare URLs in SSOT citations — not already inside a markdown link/autolink.
_BARE_URL = re.compile(r"(?<![(<])(https?://[^\s|)\]>]+)")


def linkify(citation: str) -> str:
    """Make bare citation URLs clickable (the site has no magiclink extension);
    URLs already wrapped in markdown links are left alone."""
    return _BARE_URL.sub(
        lambda m: f"[{m.group(1).removeprefix('https://')}]({m.group(1)})", citation
    )


# Glyphs: ✅ harness + toolkit support · — gap (harness could, toolkit hasn't)
# · N/A asset type not supported by the harness · ? unknown.
def sym_agent(v: str) -> str:
    if v in AGENT_SUPPORTED:
        return "✅"
    if v == "unsupported (gap)":
        return "—"
    if v == "unsupported (by design)":
        return "N/A"
    if v == UNKNOWN:
        return "?"
    raise SystemExit(f"unmapped agent verdict: {v!r}")


def sym_instr(v: str) -> str:
    if v in ("native", "symlink"):
        return "✅"
    if v == "unsupported (gap)":
        return "—"
    if v == "unsupported (by design)":
        return "N/A"
    if v == UNKNOWN:
        return "?"
    raise SystemExit(f"unmapped instructions verdict: {v!r}")


def matrix_cells(slug: str, agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> list[str]:
    cfg = AGENTS[slug]
    page = f"harnesses/{slug}.md"
    instr_s = sym_instr(instrs[slug].verdict)
    agent_s = sym_agent(agents[slug].verdict)
    return [
        f"[{cfg.display_name}]({page})",
        f"[{instr_s}]({page}#instructions)" if instr_s != "N/A" else "N/A",
        f"[✅]({page}#skills)",
        f"[{agent_s}]({page}#agents)" if agent_s != "N/A" else "N/A",
        f"[✅]({page}#mcp-servers)" if slug in MCP_ADAPTERS else "—",
        f"[✅]({page}#pi-extensions)" if slug == "pi" else "N/A",
    ]


MATRIX_HEADERS = [
    "Harness",
    "[Instructions](asset-types/instructions.md)",
    "[Skills](asset-types/skills.md)",
    "[Agents](asset-types/agents.md)",
    "[MCP](asset-types/mcp.md)",
    "[Pi extensions](asset-types/pi-extensions.md)",
]


# md_in_html requires the markdown attribute on EVERY nesting level
# (table > thead/tbody > tr > td) for the cell markdown to be processed.
def _html_row(cells: list[str]) -> str:
    return "<tr markdown>" + "".join(f"<td markdown>{c}</td>" for c in cells) + "</tr>"


def write_matrix(slugs: list[str], agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> None:
    others = sorted(s for s in slugs if s not in MAIN)
    head = "<tr markdown>" + "".join(f"<th markdown>{h}</th>" for h in MATRIX_HEADERS) + "</tr>"
    main_rows = "\n".join(_html_row(matrix_cells(s, agents, instrs)) for s in MAIN)
    other_rows = "\n".join(_html_row(matrix_cells(s, agents, instrs)) for s in others)
    label = f"Show {len(others)} more harnesses (A–Z) ▸"
    # One table: pinned MAIN rows, then a toggle row (docs/javascripts/extra.js)
    # revealing the alphabetical rest. tbody[hidden] keeps the fold JS-free at
    # render time; without JS the matrix simply stays folded.
    out = f"""\
# Compatibility matrix

One row per harness, one column per [asset type](glossary.md#asset-type). Every
harness links to its own page with per-asset-type detail; every tick links straight
to the relevant section. The main harnesses are pinned at the top — expand the
row beneath them for the rest, alphabetically. Derived from the machine-read
[SSOT](glossary.md#ssot) ([`harness-matrix.md`](agent-toolkit/harness-matrix.md))
by `scripts/gen_harness_docs.py` — edit the SSOT, then regenerate; never edit
this page by hand.

**Legend:** ✅ supported by the harness and the toolkit ·
— gap (the harness supports it; the toolkit hasn't implemented it yet) ·
N/A — the harness has no such concept ·
? unknown (no public evidence of how the harness handles this asset type)

<div class="harness-matrix" markdown>
<table markdown>
<thead markdown>
{head}
</thead>
<tbody markdown>
{main_rows}
</tbody>
<tbody class="matrix-toggle">
<tr><td colspan="6"><button type="button" data-show="{label}" data-hide="Show fewer ▴">{label}</button></td></tr>
</tbody>
<tbody class="matrix-others" markdown hidden>
{other_rows}
</tbody>
</table>
</div>

## The asset types

- **[Instructions](asset-types/instructions.md)** — one canonical `AGENTS.md`,
  pointer symlinks for harnesses that read an own-name file.
- **[Skills](asset-types/skills.md)** — `SKILL.md` folders projected into each
  harness's skills directory.
- **[Agents (subagents)](asset-types/agents.md)** — subagent definitions projected
  per-harness (symlink, translate, or registry mechanisms).
- **[MCP servers](asset-types/mcp.md)** — MCP servers projected into a harness's
  own config by name (config-injection); supported for claude-code, codex,
  opencode, and pi.
- **[Pi extensions](asset-types/pi-extensions.md)** — Pi-only extension packages.
"""
    (DOCS / "matrix.md").write_text(out)


def instr_section(row: InstrRow) -> str:
    lines = ["## Instructions { #instructions }", ""]
    if row.verdict == "native":
        lines.append(
            "Reads the canonical `AGENTS.md` natively — no pointer needed; "
            "the [instructions asset type](../asset-types/instructions.md) is satisfied as-is."
        )
    elif row.verdict == "symlink":
        lines.append(
            f"Reads a fixed own-name file ({row.default_file}) instead of "
            "`AGENTS.md`. The [instructions asset type](../asset-types/instructions.md) "
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
        f"- **Source:** {linkify(row.citation)}",
    ]
    return "\n".join(lines)


def skills_section(slug: str) -> str:
    cfg = AGENTS[slug]
    general = (
        "yes — reads the per-asset-type general directory directly"
        if cfg.is_standard
        else "no — gets its own projection"
    )
    return "\n".join([
        "## Skills { #skills }",
        "",
        "Supported — every harness in the catalog has a skills directory the "
        "[skills asset type](../asset-types/skills.md) projects into.",
        "",
        f"- **Project dir:** `{cfg.skills_dir}`",
        f"- **Global dir:** `{tilde(cfg.global_skills_dir)}`",
        f"- **[General-dir](../glossary.md#general) (`.agents/skills`) reader:** {general}",
        "- **Source:** [vercel-labs/skills · `src/agents.ts`]"
        "(https://github.com/vercel-labs/skills/blob/main/src/agents.ts) — the "
        "upstream per-harness catalog these directories come from (ported as "
        "`skill_agents.py`, parity-tested)",
    ])


def agent_section(slug: str, row: AgentRow) -> str:
    cfg = AGENTS[slug]
    lines = ["## Agents (subagents) { #agents }", ""]
    if row.verdict in AGENT_SUPPORTED:
        lines.append(
            f"Supported via the **{row.verdict}** mechanism — see the "
            "[agents asset type](../asset-types/agents.md) for what each mechanism means."
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
    lines.append(f"- **Source:** {linkify(row.citation)}")
    return "\n".join(lines)


def mcp_section(slug: str) -> str:
    if slug not in MCP_ADAPTERS:
        return ""
    return "\n".join([
        "## MCP servers { #mcp-servers }",
        "",
        "Supported — the [MCP asset type](../asset-types/mcp.md) projects a library",
        f"MCP server into this harness's own config by name (config-injection). `{slug}`",
        "is one of the four harnesses with a config-injection adapter.",
        "",
        "- **Mechanism:** config-injection by name (no symlink/copy)",
        "- **Source:** [`mcp_install.py`]"
        "(https://github.com/ajanderson1/agent-toolkit-cli/blob/main/src/agent_toolkit_cli/mcp_install.py)"
        " — the adapter target-config detection",
    ])


def pi_ext_section(slug: str) -> str:
    if slug != "pi":
        return ""
    return "\n".join([
        "## Pi extensions { #pi-extensions }",
        "",
        "Pi is the only harness with an extension-package concept, so the",
        "[pi-extension asset type](../asset-types/pi-extensions.md) targets Pi alone.",
        "Extensions are git-sourced (branch- or SHA-pinned) and projected by",
        "symlink into Pi's extension directory.",
        "",
        "- **Source:** [pi.dev/docs/latest/extensions]"
        "(https://pi.dev/docs/latest/extensions) — Pi's extension docs "
        "(packages, load paths)",
    ])


def write_harness_page(slug: str, agents: dict[str, AgentRow], instrs: dict[str, InstrRow]) -> None:
    cfg = AGENTS[slug]
    a, i = agents[slug], instrs[slug]
    instr_s, agent_s = sym_instr(i.verdict), sym_agent(a.verdict)
    instr_how = {
        "✅": "native `AGENTS.md` reader" if i.verdict == "native"
        else f"pointer symlink ({i.default_file} → `AGENTS.md`)",
        "—": "no pointer-satisfiable root file",
        "N/A": "no instruction-file concept",
        "?": "no public evidence",
    }[instr_s]
    agent_how = {
        "✅": a.verdict, "—": "no file-drop convention",
        "N/A": "no subagent concept", "?": "no public evidence",
    }[agent_s]
    mcp_row = (
        "| [MCP servers](../asset-types/mcp.md) | [✅](#mcp-servers) | config-injection by name |"
        if slug in MCP_ADAPTERS
        else "| [MCP servers](../asset-types/mcp.md) | — | no toolkit adapter yet |"
    )
    pi_row = (
        "| [Pi extensions](../asset-types/pi-extensions.md) | [✅](#pi-extensions) | symlink |"
        if slug == "pi"
        else "| [Pi extensions](../asset-types/pi-extensions.md) | N/A | Pi-only asset type |"
    )
    instr_cell = f"[{instr_s}](#instructions)" if instr_s != "N/A" else "N/A"
    agent_cell = f"[{agent_s}](#agents)" if agent_s != "N/A" else "N/A"
    sections = [
        instr_section(i),
        skills_section(slug),
        agent_section(slug, a),
    ]
    mcp_sec = mcp_section(slug)
    if mcp_sec:
        sections.append(mcp_sec)
    pi_sec = pi_ext_section(slug)
    if pi_sec:
        sections.append(pi_sec)
    body = "\n\n".join(sections)
    logo = LOGOS[slug]
    title = (
        f'![{cfg.display_name} logo]({logo}){{ .harness-logo }} {cfg.display_name}'
        if logo
        else cfg.display_name
    )
    out = f"""\
# {title}

`{slug}` · one row of the [compatibility matrix](../matrix.md)

| Asset type | Support | How |
|---|:-:|---|
| [Instructions](../asset-types/instructions.md) | {instr_cell} | {instr_how} |
| [Skills](../asset-types/skills.md) | [✅](#skills) | `{cfg.skills_dir}` |
| [Agents (subagents)](../asset-types/agents.md) | {agent_cell} | {agent_how} |
{mcp_row}
{pi_row}

{body}
"""
    (HARNESS_DIR / f"{slug}.md").write_text(out)


def rewrite_nav(slugs: list[str]) -> None:
    text = MKDOCS_YML.read_text()
    begin = "      # BEGIN GENERATED HARNESS NAV (scripts/gen_harness_docs.py)\n"
    end = "      # END GENERATED HARNESS NAV\n"
    others = sorted(s for s in slugs if s not in MAIN)
    entries = "".join(
        f"      - {AGENTS[s].display_name}: harnesses/{s}.md\n" for s in MAIN
    )
    entries += "      - Others:\n" + "".join(
        f"        - {AGENTS[s].display_name}: harnesses/{s}.md\n" for s in others
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
    if missing_logos := sorted(catalog - set(LOGOS)):
        raise SystemExit(f"slugs missing a LOGOS entry: {missing_logos}")
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
