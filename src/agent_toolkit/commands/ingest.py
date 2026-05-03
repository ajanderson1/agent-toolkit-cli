"""`agent-toolkit ingest` — IDENTIFY/RESEARCH/STAGE primitives + finalize/abort."""
from __future__ import annotations

import json
from pathlib import Path

import click

from agent_toolkit._repo_resolution import RepoNotFoundError, resolve_toolkit_root

from agent_toolkit.ingest.finalize import FinalizeError, finalize
from agent_toolkit.ingest.identify import classify_input
from agent_toolkit.ingest.research import infer_from_snapshot
from agent_toolkit.ingest.stage import abort_staging, stage_proposal, staging_root
from agent_toolkit.ingest.types import InputForm, Proposal


@click.command(name="ingest")
@click.argument("value", required=False)
@click.option(
    "--toolkit-repo",
    "toolkit_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the agent-toolkit repo (defaults to group --toolkit-repo / env / walk-up / ~/GitHub/agent-toolkit).",
)
@click.option("--scan-only", is_flag=True,
              help="Run security review only, no staging. Skill-led when invoked via the agent-toolkit skill.")
@click.option("--finalize", "do_finalize", is_flag=True,
              help="Finalise an already-staged asset by slug.")
@click.option("--abort", "do_abort", is_flag=True,
              help="Clear staging for a slug.")
@click.option("--snapshot-dir", type=click.Path(exists=True, file_okay=False),
              help="For STAGE: directory containing the candidate (typically a checkout of the upstream).")
@click.option("--slug", help="Slug of an existing staging dir (with --finalize / --abort).")
@click.pass_context
def ingest(
    ctx: click.Context,
    value: str | None,
    toolkit_root: Path | None,
    scan_only: bool,
    do_finalize: bool,
    do_abort: bool,
    snapshot_dir: str | None,
    slug: str | None,
) -> None:
    """Ingest an asset from a URL, name, or local file."""
    if toolkit_root is None:
        toolkit_root = (ctx.obj or {}).get("toolkit_root")
    if toolkit_root is None:
        try:
            toolkit_root = resolve_toolkit_root(explicit=None)
        except RepoNotFoundError as exc:
            raise click.ClickException(str(exc))
    else:
        toolkit_root = Path(toolkit_root).resolve()
    root = toolkit_root

    if do_abort:
        if not slug:
            raise click.UsageError("--abort requires --slug")
        abort_staging(toolkit_root=root, slug=slug)
        click.echo(f"aborted staging for {slug}")
        return

    if do_finalize:
        if not slug:
            raise click.UsageError("--finalize requires --slug")
        proposal = _read_proposal_from_staging(root, slug=slug)
        try:
            result = finalize(toolkit_root=root, proposal=proposal)
        except FinalizeError as e:
            raise click.ClickException(str(e))
        click.echo(json.dumps({
            "target_path": str(result.target_path),
            "committed": result.committed,
            "commit_sha": result.commit_sha,
        }))
        return

    if not value:
        raise click.UsageError("provide a value (URL / name / file) or use --finalize/--abort")

    target = classify_input(value)
    if scan_only:
        click.echo(json.dumps({
            "input_form": target.input_form.value,
            "upstream_url": target.upstream_url,
            "owner": target.owner,
            "repo": target.repo,
            "kind_guess": target.kind_guess,
            "slug_guess": target.slug_guess,
            "next": "skill_should_run_security_review_now",
        }))
        return

    if target.input_form == InputForm.NAME:
        click.echo(json.dumps({
            "status": "NEEDS_DISAMBIGUATION",
            "input_form": target.input_form.value,
            "name": target.input_value,
            "next": "skill_should_run_web_search_and_present_candidates",
        }))
        return

    if not snapshot_dir:
        click.echo(json.dumps({
            "status": "NEEDS_SNAPSHOT",
            "input_form": target.input_form.value,
            "upstream_url": target.upstream_url,
            "next": "skill_should_clone_or_download_then_re-invoke_with_snapshot_dir",
        }))
        return

    snap = Path(snapshot_dir).resolve()
    proposal = infer_from_snapshot(
        snapshot_dir=snap,
        slug=target.slug_guess,
        upstream=target.upstream_url,
    )
    staged = stage_proposal(toolkit_root=root, proposal=proposal, snapshot_dir=snap)
    click.echo(json.dumps({
        "status": "STAGED",
        "staging_dir": str(staged),
        "proposal": proposal.to_dict(),
        "target_path": proposal.target_path,
        "next": "skill_should_run_security_review_then_present_GO_NO_GO_gate",
    }, indent=2))


def _read_proposal_from_staging(toolkit_root: Path, *, slug: str) -> Proposal:
    import yaml
    p = staging_root(toolkit_root) / slug / "PROPOSED_FRONTMATTER.yaml"
    if not p.exists():
        raise click.UsageError(f"no PROPOSED_FRONTMATTER.yaml in staging/{slug}")
    payload = yaml.safe_load(p.read_text())
    meta = payload.get("metadata") or {}
    spec = payload.get("spec") or {}
    kind = _kind_from_target_path(meta.get("name", slug), payload)
    return Proposal(
        slug=meta.get("name", slug),
        kind=kind,
        origin=spec.get("origin", "third-party"),
        harnesses=list(spec.get("harnesses") or []),
        lifecycle=meta.get("lifecycle", "experimental"),
        target_path=_canonical(kind, slug),
        vendor_via=spec.get("vendored_via", "copy"),
        upstream=spec.get("upstream"),
        fork=spec.get("fork"),
        description=meta.get("description", "TODO."),
    )


def _kind_from_target_path(slug: str, payload: dict) -> str:
    # Heuristic: PROPOSED_FRONTMATTER.yaml does not record kind, infer from neighbours.
    return "skill"


def _canonical(kind: str, slug: str) -> str:
    return {
        "skill": f"skills/{slug}/SKILL.md",
        "agent": f"agents/{slug}.md",
        "command": f"commands/{slug}.md",
        "hook": f"hooks/{slug}.meta.yaml",
        "mcp": f"mcps/{slug}/mcp.json",
        "plugin": f"plugins/{slug}/marketplace.json",
    }[kind]
