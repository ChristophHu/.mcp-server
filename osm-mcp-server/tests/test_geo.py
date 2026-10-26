import pytest

from osm_mcp.geo import parse_coordinates, haversine_meters, format_distance
from osm_mcp.categories import resolve_category
from osm_mcp.server import create_server


def test_coordinates_accept_whitespace_and_validate_globe_bounds():
    assert parse_coordinates(" 49.6116, 6.1319 ") == (49.6116, 6.1319)
    assert parse_coordinates("91,0") is None
    assert parse_coordinates("0,181") is None
    assert parse_coordinates("Berlin") is None


def test_haversine_and_distance_formatting():
    assert haversine_meters((0, 0), (0, 1)) == pytest.approx(111195, abs=10)
    assert format_distance(1234) == "1.2 km"
    assert format_distance(850) == "850 m"


def test_category_shortcut_and_tag_selector_validation():
    assert resolve_category("cafe") == ("amenity", "cafe")
    assert resolve_category("diet:vegan=yes") == ("diet:vegan", "yes")
    with pytest.raises(ValueError):
        resolve_category('amenity="]; (node(1);out;')


def test_server_registers_exactly_all_eleven_tools():
    server = create_server()
    assert set(server._tool_manager._tools) == {
        "geocode", "reverse_geocode", "route", "route_matrix", "optimize_route",
        "isochrone", "find_nearby_pois", "poi_details", "suggest_meeting_point",
        "straight_line_distance", "map_link",
    }


def test_literal_from_parameter_names_match_typescript_contract():
    server = create_server()
    expected = {"straight_line_distance": "from", "map_link": "from"}
    for name, parameter in expected.items():
        assert parameter in server._tool_manager._tools[name].parameters["properties"]
        assert parameter + "_" not in server._tool_manager._tools[name].parameters["properties"]


def test_all_typescript_category_shortcuts_are_preserved():
    from osm_mcp.categories import CATEGORIES
    expected = {
        "restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream", "hotel", "hostel",
        "guest_house", "apartment", "camp_site", "attraction", "museum", "gallery", "viewpoint",
        "information", "artwork", "castle", "monument", "ruins", "supermarket", "bakery",
        "convenience", "pharmacy", "hospital", "doctors", "police", "atm", "bank", "fuel",
        "charging_station", "parking", "toilets", "drinking_water", "bus_stop", "train_station",
        "tram_stop", "ferry_terminal", "bicycle_rental", "car_rental", "playground", "park", "beach",
        "swimming_pool",
    }
    assert set(CATEGORIES) == expected
