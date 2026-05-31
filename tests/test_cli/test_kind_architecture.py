"""Architecture guard: pin the per-kind-module design for the agent kind.

These tests assert that the install/lock/paths architecture is PER-KIND
(one module per kind), NOT discriminated by a runtime `kind=` parameter.
They lock the design decision so future refactors cannot silently drift
back toward a single generic module with a kind discriminator.

Background (#252 "generalize install/lock/paths to a kind dimension"):
  The original #252 spec anticipated a single install module that accepted
  a `kind` argument.  The project instead shipped parallel modules per kind:
    - skill_install / skill_lock / skill_paths
    - agent_install / agent_lock / agent_paths
    - instructions_install / instructions_lock / instructions_paths
    - pi_extension_install / pi_extension_lock / pi_extension_paths
  The #252 "generalize" item is obsolete — superseded four times over.
  See docs/superpowers/plans/2026-05-30-agent-kind-pr3-5-plan.md § PR3.
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


def test_all_four_kind_install_modules_exist():
    """All four kinds have their own install module."""
    expected_modules = [
        "agent_toolkit_cli.skill_install",
        "agent_toolkit_cli.agent_install",
        "agent_toolkit_cli.instructions_install",
        "agent_toolkit_cli.pi_extension_install",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


def test_all_four_kind_lock_modules_exist():
    """All four kinds have their own lock module."""
    expected_modules = [
        "agent_toolkit_cli.skill_lock",
        "agent_toolkit_cli.agent_lock",
        "agent_toolkit_cli.instructions_lock",
        "agent_toolkit_cli.pi_extension_lock",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


def test_all_four_kind_paths_modules_exist():
    """All four kinds have their own paths module."""
    expected_modules = [
        "agent_toolkit_cli.skill_paths",
        "agent_toolkit_cli.agent_paths",
        "agent_toolkit_cli.instructions_paths",
        "agent_toolkit_cli.pi_extension_paths",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"module {mod_name!r} must exist"


# ── 2. No `kind=` parameter on agent install/uninstall entrypoints ───────────


def test_install_is_per_kind_not_discriminated():
    """No agent install/uninstall entrypoint accepts a `kind=` parameter.

    The per-kind-module architecture means each module IS the kind — there
    is no runtime discriminator.  If a `kind` param appears on any of these
    functions, the architecture has drifted back toward the rejected
    single-module-with-discriminator design.
    """
    import agent_toolkit_cli.agent_install as ai

    for fn_name in ("plan", "apply", "install", "uninstall"):
        fn = getattr(ai, fn_name, None)
        assert fn is not None, f"agent_install.{fn_name} must exist"
        sig = inspect.signature(fn)
        assert "kind" not in sig.parameters, (
            f"agent_install.{fn_name} must NOT accept a `kind=` parameter — "
            f"the per-kind-module architecture eliminates the need for a "
            f"runtime kind discriminator."
        )


def test_skill_install_has_no_kind_param():
    """Symmetry check: skill_install also must not accept a `kind=` param."""
    import agent_toolkit_cli.skill_install as si

    for fn_name in ("plan", "apply", "install", "uninstall"):
        fn = getattr(si, fn_name, None)
        assert fn is not None, f"skill_install.{fn_name} must exist"
        sig = inspect.signature(fn)
        assert "kind" not in sig.parameters, (
            f"skill_install.{fn_name} must NOT accept a `kind=` parameter"
        )


# ── 3. _install_core stays kind-blind ────────────────────────────────────────


def test_install_core_plan_has_no_kind_param():
    """_install_core.plan() is kind-blind — kind-specific logic lives in facades."""
    from agent_toolkit_cli._install_core import plan

    sig = inspect.signature(plan)
    assert "kind" not in sig.parameters, (
        "_install_core.plan() must not accept `kind=`; kind-specific binding "
        "is done at the facade level via canonical_dir_resolver / "
        "universal_bundle_link / synthetic_names / current_linked_resolver."
    )


def test_install_core_accepts_kind_specific_overrides_via_callables():
    """The core accepts kind-specific behaviour via injected callables, not a kind= param.

    The facade pattern: canonical_dir_resolver, universal_bundle_link,
    synthetic_names, and current_linked_resolver are the injection points.
    All must be present in _install_core.plan()'s signature.
    """
    from agent_toolkit_cli._install_core import plan

    sig = inspect.signature(plan)
    expected_injection_points = {
        "canonical_dir_resolver",
        "universal_bundle_link",
        "synthetic_names",
        "current_linked_resolver",
    }
    missing = expected_injection_points - set(sig.parameters)
    assert not missing, (
        f"_install_core.plan() is missing facade injection points: {missing}. "
        f"These callables let each kind facade bind kind-specific behaviour "
        f"without a runtime `kind=` discriminator."
    )
