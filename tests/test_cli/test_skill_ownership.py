"""is_owned_owner: which monorepo parents are writable-by-default."""
from agent_toolkit_cli.skill_ownership import OWNED_OWNERS, is_owned_owner


def test_ajanderson1_is_owned():
    assert is_owned_owner("ajanderson1") is True


def test_owner_match_is_case_insensitive():
    assert is_owned_owner("AJAnderson1") is True


def test_other_owner_is_not_owned():
    assert is_owned_owner("anthropics") is False
    assert is_owned_owner("mattpocock") is False


def test_synthetic_local_owner_is_not_owned():
    # file:// sources synthesise owner "local"; not owned without --owned.
    assert is_owned_owner("local") is False


def test_owned_owners_constant_seeded():
    assert "ajanderson1" in OWNED_OWNERS
