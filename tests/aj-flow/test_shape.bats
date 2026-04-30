#!/usr/bin/env bats
#
# Shape smoke tests for aj-flow. Asserts the router, subcommands, preferences file,
# templates, and hook are present and wired consistently. Does not validate prose —
# the skill is prose meant to be hand-edited.

setup() {
  export ROOT="$(git rev-parse --show-toplevel)"
  export SKILL="$ROOT/skills/first_party/aj-flow"
}

@test "SKILL.md exists and declares aj-flow" {
  [ -f "$SKILL/SKILL.md" ]
  grep -qE '^name:\s*aj-flow\s*$' "$SKILL/SKILL.md"
}

@test "PREFERENCES.md exists (single source of truth)" {
  [ -f "$SKILL/PREFERENCES.md" ]
}

@test "all five subcommands exist" {
  for cmd in init adopt recap issue cycle; do
    [ -f "$SKILL/subcommands/$cmd.md" ] || { echo "missing subcommands/$cmd.md"; return 1; }
  done
}

@test "router dispatches all five subcommands" {
  for cmd in init adopt recap issue cycle; do
    grep -qE "^## $cmd\s*$" "$SKILL/SKILL.md" || { echo "missing ## $cmd heading"; return 1; }
    grep -qE "subcommands/$cmd\.md" "$SKILL/SKILL.md" || { echo "missing subcommands/$cmd.md dispatch"; return 1; }
  done
}

@test "argument-hint lists five subcommands" {
  grep -qE 'argument-hint:.*init.*adopt.*recap.*issue.*cycle' "$SKILL/SKILL.md"
}

@test "no GitLab code paths remain" {
  # Look for the glab CLI or gitlab URLs — not the word GitLab in prose.
  ! grep -qE '\bglab\b|gitlab\.com|/-/(issues|pipelines|labels|milestones|settings)' \
      "$SKILL/SKILL.md" "$SKILL/PREFERENCES.md" "$SKILL/subcommands/"*.md
}

@test "no REFERENCE.md left behind (folded into PREFERENCES.md)" {
  [ ! -f "$SKILL/REFERENCE.md" ]
}

@test "no old subcommand files left behind" {
  for cmd in bootstrap orient readme; do
    [ ! -f "$SKILL/subcommands/$cmd.md" ] || { echo "stale subcommands/$cmd.md"; return 1; }
  done
}

@test "templates directory has the five core templates" {
  for f in AGENTS.md CLAUDE.md README.md gitignore ci.yml pr-template.md; do
    [ -f "$SKILL/templates/$f" ] || { echo "missing templates/$f"; return 1; }
  done
}

@test "no dependabot template remains" {
  [ ! -f "$SKILL/templates/dependabot.yml.tmpl" ]
}

@test "no issue-templates directory remains" {
  [ ! -d "$SKILL/templates/issue-templates" ]
}

@test "license templates are present" {
  for lic in MIT Apache-2.0 GPL-3.0; do
    [ -f "$SKILL/templates/license-templates/$lic.txt" ] || { echo "missing templates/license-templates/$lic.txt"; return 1; }
  done
}

@test "recap hook exists and is executable" {
  [ -x "$ROOT/hooks/core/aj-flow-recap.js" ]
}

@test "no old orient hook remains" {
  [ ! -f "$ROOT/hooks/core/aj-flow-orient.js" ]
  [ ! -f "$ROOT/hooks/core/aj-flow-orient.install.md" ]
}

@test "PREFERENCES.md contains the three cycle modes" {
  grep -qE '\-\-guided' "$SKILL/PREFERENCES.md"
  grep -qE '\-\-auto' "$SKILL/PREFERENCES.md"
  grep -qE '\-\-ship-it' "$SKILL/PREFERENCES.md"
}

@test "PREFERENCES.md states CI-local-first rule" {
  grep -qiE 'locally first|pre-flight|before.*push' "$SKILL/PREFERENCES.md"
}

@test "cycle.md runs pre-flight CI before push" {
  # The word "push" must come AFTER the pre-flight step in the file.
  awk '/pre-flight|Pre-flight/ { found=1 } /git push/ { if (found) print "ok"; exit }' \
    "$SKILL/subcommands/cycle.md" | grep -q ok
}

@test "standalone readme skill exists" {
  [ -f "$ROOT/skills/first_party/readme/SKILL.md" ]
  grep -qE '^name:\s*readme\s*$' "$ROOT/skills/first_party/readme/SKILL.md"
}

@test "AskUserQuestion menu has at least five labelled options" {
  local count
  count="$(awk '/AskUserQuestion/,/Map selected label/' "$SKILL/SKILL.md" | grep -cE '^\s*-?\s*label:' || true)"
  [ "$count" -ge 5 ] || { echo "expected >=5 label: entries, got $count"; return 1; }
}

@test "issue.md previews the draft before filing it" {
  # Approval step must come before the gh issue create command.
  awk '/Approve, edit, or cancel/ { found=1 } /gh issue create/ { if (found) print "ok"; exit }' \
    "$SKILL/subcommands/issue.md" | grep -q ok
}

@test "issue.md documents chained-from-cycle mode" {
  grep -qE '__chained_from_cycle' "$SKILL/subcommands/issue.md"
  grep -qE '__chained_from_cycle' "$SKILL/subcommands/cycle.md"
}
