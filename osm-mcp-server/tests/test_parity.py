import asyncio

import pytest

from osm_mcp.server import create_server
from test_tools import FixtureClient, invoke


def call(server, name, **arguments):
    return server._tool_manager.get_tool(name).fn(**arguments)


def test_photon_result_matches_reference_label_and_metadata():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {
        "features": [{
            "geometry": {"coordinates": [6.64, 49.75]},
            "properties": {
                "name": "Hauptmarkt", "housenumber": "1", "postcode": "54290",
                "city": "Trier", "state": "Rheinland-Pfalz", "country": "Deutschland",
                "osm_type": "W", "osm_id": 42, "osm_key": "place", "osm_value": "square",
            },
        }]
    }
    result = call(create_server(client), "geocode", query="Hauptmarkt", provider="photon")
    assert result["results"] == [{
        "lat": 49.75,
        "lon": 6.64,
        "label": "Hauptmarkt 1, 54290 Trier, Rheinland-Pfalz, Deutschland",
        "osm": "way/42",
        "kind": "place/square",
    }]


def test_untrusted_cleaning_removes_controls_proto_and_secret_recursively():
    client = FixtureClient()
    setattr(client, "key", "secret-key-123456")
    client.get = lambda *args, **kwargs: [{
        "lat": "49.75", "lon": "6.64",
        "display_name": "safe\u202e secret-key-123456",
    }]
    clean_result = call(create_server(client), "geocode", query="Trier")
    assert clean_result["untrusted"] is True
    assert "\u202e" not in clean_result["results"][0]["label"]
    assert "secret-key-123456" not in repr(clean_result)


def test_language_and_waypoint_contracts_are_validated_for_direct_calls():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="language"):
        call(server, "geocode", query="Trier", language="bad language")
    with pytest.raises(ValueError, match="waypoint"):
        call(server, "route", waypoints=["x" * 301, "49,6"], profile="foot")


def test_matrix_rejects_unknown_profile_and_rounds_half_up_like_javascript():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="profile"):
        call(server, "route_matrix", origins=["1,2"], destinations=["3,4"], profile="train")
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"code": "Ok", "durations": [[3]], "distances": [[5]]}
    result = call(create_server(client), "route_matrix", origins=["1,2"], destinations=["3,4"], profile="foot")
    assert result["durations_minutes"] == [[0.1]]
    assert result["distances_km"] == [[0.01]]


def test_reverse_geocode_drops_malformed_upstream_coordinates():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"lat": "nan", "lon": "6.64", "display_name": "Bad"}
    result = call(create_server(client), "reverse_geocode", latitude=49.75, longitude=6.64)
    assert result["result"] is None


def test_route_rejects_nonfinite_backend_measures_with_a_stable_error():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"code": "Ok", "routes": [{"distance": float("inf"), "duration": 60, "legs": []}]}
    with pytest.raises(RuntimeError, match="usable distance and duration"):
        call(create_server(client), "route", waypoints=["1,2", "3,4"], profile="car")


def test_optimize_route_rejects_duplicate_or_incomplete_backend_order():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {
        "code": "Ok", "trips": [{"distance": 1, "duration": 1, "legs": []}],
        "waypoints": [{"waypoint_index": 0}, {"waypoint_index": 0}, {"waypoint_index": 2}],
    }
    with pytest.raises(RuntimeError, match="visiting order does not cover the stops"):
        call(create_server(client), "optimize_route", stops=["1,2", "3,4", "5,6"], profile="car")


def test_meeting_point_uses_ors_matrix_when_key_is_configured():
    client = FixtureClient()
    setattr(client, "key", "valid-test-key-123456")
    server = create_server(client)
    asyncio.run(invoke(server, "suggest_meeting_point", {
        "locations": ["49.75,6.64", "49.76,6.65"], "profile": "foot",
    }))
    assert any("/v2/matrix/foot-walking" in call[0] for call in client.calls)


def test_tool_annotations_include_idempotent_hint():
    server = create_server(FixtureClient())
    for tool in server._tool_manager._tools.values():
        assert tool.annotations.idempotentHint is True


def test_poi_results_drop_malformed_osm_elements_and_bound_untrusted_tags():
    client = FixtureClient()
    def upstream(url, params=None, **kwargs):
        if "search" in url:
            return [{"lat": "1", "lon": "2", "display_name": "place"}]
        if "node(4)" in (kwargs.get("post") or {}).get("data", ""):
            return {"elements": [{"type": "node", "id": 4, "lat": float("nan"), "lon": 2, "tags": {"name": "x" * 800}}]}
        return {"elements": [None,
            {"type": "node", "id": 3, "lat": float("nan"), "lon": 2, "tags": {"name": "bad"}},
            {"type": "node", "id": 4, "lat": 1, "lon": 2, "tags": {"name": "x" * 800}},
        ]}
    client.get = upstream
    server = create_server(client)
    nearby = call(server, "find_nearby_pois", near="1,2", category="cafe")
    assert len(nearby["results"]) == 1
    assert len(nearby["results"][0]["name"]) < 800

    detail = call(server, "poi_details", osm_id="node/4")
    assert len(detail["name"]) < 800
    assert "lat" not in detail
