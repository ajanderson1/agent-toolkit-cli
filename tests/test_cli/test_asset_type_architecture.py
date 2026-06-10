"""Architecture guard: pin the per-asset-type-module design for the agent asset type.

These tests assert that the install/lock/paths architecture is PER ASSET TYPE
(one module per asset type), NOT discriminated by a runtime `asset_type=`
parameter. They lock the design decision so future refactors cannot silently
drift back toward a single generic module with an asset-type discriminator.

Background (#252 "generalize install/lock/paths to an asset-type dimension"):
  The original #252 spec anticipated a single install module that accepted
  an asset-type discriminator argument.  The project instead shipped parallel
  modules per asset type:
    - skill_install / skill_lock / skill_paths
    - agent_install / agent_lock / agent_paths
    - instructions_install / instructions_lock / instructions_paths
    - pi_extension_install / pi_extension_lock / pi_extension_paths
  The #252 "generalize" item is obsolete — superseded four times over.
  See the 2026-05-30 agent PR3–5 plan in docs/superpowers/plans/ § PR3.
"""
from __future__ import annotations

import importlib
import inspect


# ── 1. Separate module existence ─────────────────────────────────────────────


def test_agent_install_is_a_separate_module():
    """agent_install imports as its own module, not a re-export of skill_install."""
    import agent_toolkit_cli.agent_install as ai
    import agent_toolkit_cli.skill_install as si

    assert ai.__name__ != si.__name__
    assert ai.__file__ != si.__file__


def test_agent_lock_is_a_separate_module():
    """agent_lock imports as its own module, not a re-export of skill_lock."""
    import agent_toolkit_cli.agent_lock as al
    import agent_toolkit_cli.skill_lock as sl

    assert al.__name__ != sl.__name__
    assert al.__file__ != sl.__file__


def test_agent_paths_is_a_separate_module():
    """agent_paths imports as its own module, not a re-export of skill_paths."""
    import agent_toolkit_cli.agent_paths as ap
    import agent_toolkit_cli.skill_paths as sp

    assert ap.__name__ != sp.__name__
    assert ap.__file__ != sp.__file__


def test_all_four_asset_type_install_modules_exist():
    """All four asset types have their own install module."""
    expected_modules = [
        "agent_toolkit_cli.skill_install",
        "agent_toolkit_cli.agent_install",
        "agent_toolkit_cli.instructions_install",
        "agent_toolkit_cli.pi_extension_install",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


def test_all_four_asset_type_lock_modules_exist():
    """All four asset types have their own lock module."""
    expected_modules = [
        "agent_toolkit_cli.skill_lock",
        "agent_toolkit_cli.agent_lock",
        "agent_toolkit_cli.instructions_lock",
        "agent_toolkit_cli.pi_extension_lock",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


def test_all_four_asset_type_paths_modules_exist():
    """All four asset types have their own paths module."""
    expected_modules = [
        "agent_toolkit_cli.skill_paths",
        "agent_toolkit_cli.agent_paths",
        "agent_toolkit_cli.instructions_paths",
        "agent_toolkit_cli.pi_extension_paths",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


# ── 2. No `asset_type=` parameter on agent install/uninstall entrypoints ─────


def test_install_is_per_asset_type_not_discriminated():
    """No agent install/uninstall entrypoint accepts an `asset_type=` parameter.

    The per-asset-type-module architecture means each module IS the asset
    type — there is no runtime discriminator.  If an `asset_type` param
    appears on any of these functions, the architecture has drifted back
    toward the rejected single-module-with-discriminator design.
    """
    import agent_toolkit_cli.agent_install as ai

    for fn_name in ("plan", "apply", "install", "uninstall"):
        fn = getattr(ai, fn_name, None)
        assert fn is not None, f"agent_install.{fn_name} must exist"
        sig = inspect.signature(fn)
        assert "asset_type" not in sig.parameters, (
            f"agent_install.{fn_name} must NOT accept an `asset_type=` parameter — "
            f"the per-asset-type-module architecture eliminates the need for a "
            f"runtime asset-type discriminator."
        )


def test_skill_install_has_no_asset_type_param():
    """Symmetry check: skill_install also must not accept an `asset_type=` param."""
    import agent_toolkit_cli.skill_install as si

    for fn_name in ("plan", "apply", "install", "uninstall"):
        fn = getattr(si, fn_name, None)
        assert fn is not None, f"skill_install.{fn_name} must exist"
        sig = inspect.signature(fn)
        assert "asset_type" not in sig.parameters, (
            f"skill_install.{fn_name} must NOT accept an `asset_type=` parameter"
        )


# ── 3. _install_core stays asset-type-blind ──────────────────────────────────


def test_install_core_plan_has_no_asset_type_param():
    """_install_core.plan() is asset-type-blind — asset-type-specific logic lives in facades."""
    from agent_toolkit_cli._install_core import plan

    sig = inspect.signature(plan)
    assert "asset_type" not in sig.parameters, (
        "_install_core.plan() must not accept `asset_type=`; asset-type-specific "
        "binding is done at the facade level via canonical_dir_resolver / "
        "standard_bundle_link / synthetic_names / current_linked_resolver."
    )


def test_install_core_accepts_asset_type_specific_overrides_via_callables():
    """The core accepts asset-type-specific behaviour via injected callables, not a param.

    The facade pattern: canonical_dir_resolver, standard_bundle_link,
    synthetic_names, and current_linked_resolver are the injection points.
    All must be present in _install_core.plan()'s signature.
    """
    from agent_toolkit_cli._install_core import plan

    sig = inspect.signature(plan)
    expected_injection_points = {
        "canonical_dir_resolver",
        "standard_bundle_link",
        "synthetic_names",
        "current_linked_resolver",
    }
    missing = expected_injection_points - set(sig.parameters)
    assert not missing, (
        f"_install_core.plan() is missing facade injection points: {missing}. "
        f"These callables let each asset-type facade bind asset-type-specific "
        f"behaviour without a runtime `asset_type=` discriminator."
    )
