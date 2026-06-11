# #365 — plan: both-spellings architecture guard

**Tier: light** (paragraph-sized plan). Spec:
`docs/superpowers/specs/2026-06-11-arch-guard-both-spellings-design.md`.

Single task, one file: `tests/test_cli/test_asset_type_architecture.py`.

1. Add module-level constants:
   `BANNED_DISCRIMINATORS = ("kind", "asset_type")` and
   `INSTALL_ENTRYPOINTS` mapping the four `agent_toolkit_cli.*_install` module
   paths to their entrypoint tuples (skill: plan/apply/install/uninstall;
   agent: + remove; instructions: plan/apply/uninstall; pi_extension:
   plan/apply).
2. Replace `test_install_is_per_asset_type_not_discriminated` and
   `test_skill_install_has_no_asset_type_param` with one
   `@pytest.mark.parametrize("mod_name", sorted(INSTALL_ENTRYPOINTS))` test:
   import the module, loop its mapped entrypoints, assert each exists, then
   `for banned in BANNED_DISCRIMINATORS: assert banned not in sig.parameters`
   with a self-documenting message naming module, function, and banned spelling.
3. Update `test_install_core_plan_has_no_asset_type_param` to loop
   `BANNED_DISCRIMINATORS` over `_install_core.plan()`'s signature.
4. Prove the guard RED: temporarily add `kind=None` to one covered entrypoint
   locally → suite fails; revert → green (AC3). Run
   `uv run pytest tests/test_cli/test_asset_type_architecture.py` then the full
   suite.

**Files:** `tests/test_cli/test_asset_type_architecture.py` (only).
**Verification:** AC1–4 in the spec; expected diff ≈ 30 lines.
