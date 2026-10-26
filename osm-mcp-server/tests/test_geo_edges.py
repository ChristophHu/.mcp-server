import pytest

from osm_mcp.geo import bounding_box, flatten_coordinates, format_distance, format_duration, parse_coordinates


def test_coordinate_parser_rejects_nonfinite_and_malformed_values():
    for value in ("1,2,3", "NaN,0", "Infinity,0", "", "-.5,1"):
        assert parse_coordinates(value) is None


def test_distance_and_duration_formatting_boundaries():
    assert format_distance(float("nan")) == "unknown"
    assert format_distance(10_000) == "10 km"
    assert format_distance(9_999) == "10.0 km"
    assert format_duration(0) == "< 1 min"
    assert format_duration(61 * 60) == "1 h 1 min"
    assert format_duration(2 * 60 * 60) == "2 h"


def test_flatten_coordinates_recurses_and_skips_invalid_nodes():
    assert flatten_coordinates([None, [200, 10], [[2, 1]], (4, 3, 99)]) == [(1, 2), (3, 4)]
    assert flatten_coordinates({"coordinates": [[2, 1]]}) == []


def test_flatten_coordinates_enforces_point_limit():
    with pytest.raises(ValueError, match="500000"):
        flatten_coordinates([[1, 2]] * 500_001)


def test_bounding_box_rejects_empty_points():
    with pytest.raises(ValueError, match="no coordinates"):
        bounding_box([])
