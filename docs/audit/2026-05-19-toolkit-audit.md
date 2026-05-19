# Toolkit Audit — 2026-05-19

## Rollup

<!-- BEGIN_AUDIT:rollup -->
Last scaffolded: 2026-05-19T16:48:23Z

_Prioritized issues list — hand-curate below._
<!-- END_AUDIT:rollup -->

## Support matrix

<!-- BEGIN_AUDIT:matrix -->
### Code-derived

|         | claude | codex | gemini | opencode | pi |
|---------|:---:|:---:|:---:|:---:|:---:|
| agent | ✓ | — | ✓ | ✓ | ✓ |
| command | ✓ | — | ✓ | ✓ | — |
| hook | ✓ | ✓ | — | — | — |
| mcp | ✓ | ✓ | ✓ | ✓ | — |
| pi-extension | — | — | — | — | ✓ |
| plugin | ✓ | — | — | — | — |
| skill | ✓ | ✓ | ✓ | ✓ | ✓ |

### Schema-derived

|         | claude | codex | gemini | opencode | pi |
|---------|:---:|:---:|:---:|:---:|:---:|
| agent | ✓ | ✓ | ✓ | ✓ | ✓ |
| command | ✓ | ✓ | ✓ | ✓ | ✓ |
| hook | ✓ | ✓ | ✓ | ✓ | ✓ |
| mcp | ✓ | ✓ | ✓ | ✓ | ✓ |
| pi-extension | ✓ | ✓ | ✓ | ✓ | ✓ |
| plugin | ✓ | ✓ | ✓ | ✓ | ✓ |
| skill | ✓ | ✓ | ✓ | ✓ | ✓ |

### Empirical

|         |
|---------|

### Disagreements

- agent × codex: code=false, schema=true
- command × codex: code=false, schema=true
- command × pi: code=false, schema=true
- hook × gemini: code=false, schema=true
- hook × opencode: code=false, schema=true
- hook × pi: code=false, schema=true
- mcp × pi: code=false, schema=true
- pi-extension × claude: code=false, schema=true
- pi-extension × codex: code=false, schema=true
- pi-extension × gemini: code=false, schema=true
- pi-extension × opencode: code=false, schema=true
- plugin × codex: code=false, schema=true
- plugin × gemini: code=false, schema=true
- plugin × opencode: code=false, schema=true
- plugin × pi: code=false, schema=true

<!-- END_AUDIT:matrix -->

## Cells

### agent × claude

<!-- BEGIN_AUDIT:cell agent-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-claude.sh` (`tmux attach -t audit-agent-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-claude -->

### agent × gemini

<!-- BEGIN_AUDIT:cell agent-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-gemini.sh` (`tmux attach -t audit-agent-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-gemini -->

### agent × opencode

<!-- BEGIN_AUDIT:cell agent-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-opencode.sh` (`tmux attach -t audit-agent-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-opencode -->

### agent × pi

<!-- BEGIN_AUDIT:cell agent-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/agent-pi.sh` (`tmux attach -t audit-agent-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell agent-pi -->

### command × claude

<!-- BEGIN_AUDIT:cell command-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-claude.sh` (`tmux attach -t audit-command-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-claude -->

### command × gemini

<!-- BEGIN_AUDIT:cell command-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-gemini.sh` (`tmux attach -t audit-command-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-gemini -->

### command × opencode

<!-- BEGIN_AUDIT:cell command-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/command-opencode.sh` (`tmux attach -t audit-command-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell command-opencode -->

### hook × claude

<!-- BEGIN_AUDIT:cell hook-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/hook-claude.sh` (`tmux attach -t audit-hook-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell hook-claude -->

### hook × codex

<!-- BEGIN_AUDIT:cell hook-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/hook-codex.sh` (`tmux attach -t audit-hook-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell hook-codex -->

### mcp × claude

<!-- BEGIN_AUDIT:cell mcp-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-claude.sh` (`tmux attach -t audit-mcp-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-claude -->

### mcp × codex

<!-- BEGIN_AUDIT:cell mcp-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-codex.sh` (`tmux attach -t audit-mcp-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-codex -->

### mcp × gemini

<!-- BEGIN_AUDIT:cell mcp-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-gemini.sh` (`tmux attach -t audit-mcp-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-gemini -->

### mcp × opencode

<!-- BEGIN_AUDIT:cell mcp-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/mcp-opencode.sh` (`tmux attach -t audit-mcp-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell mcp-opencode -->

### pi-extension × pi

<!-- BEGIN_AUDIT:cell pi-extension-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/pi-extension-pi.sh` (`tmux attach -t audit-pi-extension-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell pi-extension-pi -->

### plugin × claude

<!-- BEGIN_AUDIT:cell plugin-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/plugin-claude.sh` (`tmux attach -t audit-plugin-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell plugin-claude -->

### skill × claude

<!-- BEGIN_AUDIT:cell skill-claude -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-claude.sh` (`tmux attach -t audit-skill-claude`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-claude -->

### skill × codex

<!-- BEGIN_AUDIT:cell skill-codex -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-codex.sh` (`tmux attach -t audit-skill-codex`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-codex -->

### skill × gemini

<!-- BEGIN_AUDIT:cell skill-gemini -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-gemini.sh` (`tmux attach -t audit-skill-gemini`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-gemini -->

### skill × opencode

<!-- BEGIN_AUDIT:cell skill-opencode -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-opencode.sh` (`tmux attach -t audit-skill-opencode`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-opencode -->

### skill × pi

<!-- BEGIN_AUDIT:cell skill-pi -->
**Overview** — _hand-fill_

**Mechanics** — _hand-fill_

**Operations**
  - *Lifecycle* — _hand-fill_
  - *Validation* — _hand-fill_
  - *Authoring* — _hand-fill_
  - *Inspection+Robustness* — _hand-fill_

**Human-edit robustness** — _hand-fill_

**Demo script** — `audit/demos/skill-pi.sh` (`tmux attach -t audit-skill-pi`)

**Findings**
  - _hand-fill_
<!-- END_AUDIT:cell skill-pi -->

