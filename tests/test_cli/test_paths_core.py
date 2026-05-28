from agent_toolkit_cli._paths_core import KindBinding, SKILL_BINDING


def test_kind_binding_is_frozen_dataclass():
    b = KindBinding(
        kind="x",
        canonical_dirname="xs",
        library_subdir="_library/xs",
        lock_filename="xs-lock.json",
        general_harness_name="general-x",
    )
    import dataclasses
    assert dataclasses.is_dataclass(b)
    # Frozen — assignment should raise.
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.kind = "y"  # type: ignore[misc]


def test_skill_binding_is_the_canonical_skill_binding():
    assert SKILL_BINDING.kind == "skill"
    assert SKILL_BINDING.canonical_dirname == "skills"
    assert SKILL_BINDING.library_subdir == "skills"  # under ~/.agent-toolkit/
    assert SKILL_BINDING.lock_filename == "skills-lock.json"
    assert SKILL_BINDING.general_harness_name == "general-skill"
