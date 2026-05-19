# tests/test_pi_overrides.py
from agent_toolkit_cli._pi_overrides import is_enabled


def test_empty_overrides_enabled():
    assert is_enabled(slug="foo", overrides=[]) is True


def test_plain_include_filter_enables_only_listed():
    # Pi rule: any plain entry switches mode to include-filter — non-listed extensions become disabled.
    assert is_enabled(slug="foo", overrides=["foo"]) is True
    assert is_enabled(slug="bar", overrides=["foo"]) is False


def test_bang_exclude():
    assert is_enabled(slug="foo", overrides=["!foo"]) is False
    assert is_enabled(slug="bar", overrides=["!foo"]) is True


def test_force_include_beats_exclude():
    assert is_enabled(slug="foo", overrides=["!foo", "+foo"]) is True


def test_force_exclude_beats_force_include():
    assert is_enabled(slug="foo", overrides=["+foo", "-foo"]) is False


def test_glob_star_in_include():
    assert is_enabled(slug="status-bar", overrides=["status-*"]) is True
    assert is_enabled(slug="other", overrides=["status-*"]) is False


def test_unknown_pattern_shape_recorded_as_unmatched():
    # Anything other than slug/glob (e.g. a relative path with `/`) doesn't match by name.
    assert is_enabled(slug="foo", overrides=["sub/dir/foo"]) is False
