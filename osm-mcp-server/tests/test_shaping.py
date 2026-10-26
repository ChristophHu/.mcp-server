import pytest

from osm_mcp.shaping import clean_tags, clean_untrusted, measure, nonnegative_integer, sanitize_error_body, valid_latlon


def test_measure_and_integer_accept_only_finite_safe_values():
    assert measure(0) == 0
    assert measure(1e12) == 1e12
    assert measure(-1) is None
    assert measure(float("inf")) is None
    assert nonnegative_integer(4) == 4
    assert nonnegative_integer(4.5) is None
    assert nonnegative_integer(2**53) is None


def test_valid_latlon_rejects_booleans_and_out_of_range_values():
    assert valid_latlon(90, -180)
    assert not valid_latlon(True, 0)
    assert not valid_latlon(91, 0)


def test_tags_are_stringified_and_bounded():
    tags = clean_tags({"name": "x" * 501, "ele": 250, "bad": {"x": 1}, "": "no"})
    assert tags["name"] == "x" * 500 + "… (truncated)"
    assert tags["ele"] == "250"
    assert "bad" not in tags and "" not in tags


def test_recursive_cleaning_redacts_data_and_drops_proto_keys():
    data = {"nested": ["x\u202e secret-value", {"__proto__": "drop", "safe": "secret-value"}]}
    assert clean_untrusted(data, "secret-value") == {"nested": ["x [redacted]", {"safe": "[redacted]"}]}


def test_error_body_html_controls_and_length_are_sanitized():
    assert sanitize_error_body("<html>blocked</html>") == "(HTML error page omitted)"
    assert sanitize_error_body("a\u202e" + "b" * 5, 3) == "abb… (truncated)"
