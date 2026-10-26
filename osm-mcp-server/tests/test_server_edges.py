import pytest
import httpx

from test_tools import FixtureClient
from osm_mcp.server import create_server


def call(server, name, **kwargs):
    return server._tool_manager.get_tool(name).fn(**kwargs)


def test_geocode_handles_direct_coordinates_photon_sparse_results_and_country_filter():
    client = FixtureClient()
    server = create_server(client)
    direct = call(server, "geocode", query="49.75,6.64")
    assert direct["results"][0]["lat"] == 49.75

    def photon(*args, **kwargs):
        return {"features": [{"geometry": {"coordinates": [None, 49.7]}, "properties": {}}, {"geometry": {"coordinates": [6.6, 49.7]}, "properties": {"city": "Trier"}}]}
    client.get = photon
    results = call(server, "geocode", query="somewhere", provider="photon")
    assert results["results"] == [{"lat": 49.7, "lon": 6.6, "label": "Trier"}]

    captured = []
    def country_response(url, params=None, **kwargs):
        captured.append(params)
        return [{"lat": "49.7", "lon": "6.6", "display_name": "Trier"}]
    client.get = country_response
    call(server, "geocode", query="Trier", countrycodes="de,lu")
    assert captured[-1]["countrycodes"] == "de,lu"
    client.get = lambda *args, **kwargs: []
    assert "note" in call(server, "geocode", query="Trier")


def test_geocoding_and_routing_reject_invalid_inputs_and_upstream_errors():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="waypoint"):
        call(server, "geocode", query="")
    with pytest.raises(ValueError, match="coordinates out of range"):
        call(server, "reverse_geocode", latitude=91, longitude=0)
    with pytest.raises(ValueError, match="2–25"):
        call(server, "route", waypoints=["1,2"], profile="foot")

    failing = FixtureClient()
    failing.get = lambda *args, **kwargs: {"code": "NoRoute", "message": "no road"}
    with pytest.raises(RuntimeError, match="OSRM route failed"):
        call(create_server(failing), "route", waypoints=["1,2", "3,4"], profile="foot")


def test_reverse_geocode_no_result_and_matrix_and_trip_errors():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"error": "not found"}
    assert call(create_server(client), "reverse_geocode", latitude=0, longitude=0)["result"] is None

    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="origins"):
        call(server, "route_matrix", origins=[], destinations=["1,2"], profile="car")
    with pytest.raises(ValueError, match="3–12"):
        call(server, "optimize_route", stops=["1,2"], profile="car")
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"code": "Ok", "trips": []}
    with pytest.raises(RuntimeError, match="OSRM trip failed"):
        call(create_server(client), "optimize_route", stops=["1,2", "3,4", "5,6"], profile="car")


def test_isochrone_validates_budget_and_uses_ors_for_keyed_requests():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="exactly one"):
        call(server, "isochrone", center="1,2", profile="foot")
    with pytest.raises(ValueError, match="minutes must"):
        call(server, "isochrone", center="1,2", profile="foot", minutes=0)
    with pytest.raises(ValueError, match="kilometers must"):
        call(server, "isochrone", center="1,2", profile="foot", kilometers=101)
    client = FixtureClient()
    client.key = "test-key-0123456789"
    result = call(create_server(client), "isochrone", center="1,2", profile="bike", minutes=5)
    assert result["engine"] == "openrouteservice"
    assert any("/v2/isochrones/cycling-regular" in c[0] for c in client.calls)
    client.get = lambda *args, **kwargs: {"features": []}
    with pytest.raises(RuntimeError, match="no contour"):
        call(create_server(client), "isochrone", center="1,2", profile="foot", minutes=5)


def test_nearby_poi_validation_fallback_filtering_and_error_path():
    client = FixtureClient()
    server = create_server(client)
    with pytest.raises(ValueError, match="radius_m"):
        call(server, "find_nearby_pois", near="1,2", category="cafe", radius_m=1)
    client.get = lambda *args, **kwargs: {"elements": [{"type": "node", "id": 1, "lat": None, "lon": 0, "tags": {}}, {"type": "node", "id": 2, "lat": 1, "lon": 2, "tags": {}}]}
    result = call(create_server(client), "find_nearby_pois", near="1,2", category="cafe")
    assert result["count"] == 1
    assert result["results"][0]["name"] == "(unnamed)"

    client = FixtureClient()
    def fail(*args, **kwargs):
        raise httpx.ConnectError("upstream down")
    client.get = fail
    with pytest.raises(RuntimeError, match="all Overpass endpoints failed"):
        call(create_server(client), "find_nearby_pois", near="1,2", category="cafe")


def test_poi_details_validates_identifiers_and_caps_tags():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="expected"):
        call(server, "poi_details", osm_id="bad")
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"elements": []}
    with pytest.raises(ValueError, match="no OSM element"):
        call(create_server(client), "poi_details", osm_id="way/4")
    client = FixtureClient()
    tags = {"k{}".format(i): "x" * 600 for i in range(61)}
    client.get = lambda *args, **kwargs: {"elements": [{"type": "way", "id": 4, "center": {"lat": 1, "lon": 2}, "tags": tags}]}
    detail = call(create_server(client), "poi_details", osm_id="way/4")
    assert len(detail["tags"]) == 60
    assert detail["tags"]["k0"].startswith("x" * 500)
    assert "(truncated)" in detail["tags"]["k0"]
    assert "tags_truncated" in detail


def test_meeting_point_empty_unreachable_and_validation_paths():
    client = FixtureClient()
    server = create_server(client)
    with pytest.raises(ValueError, match="2–8"):
        call(server, "suggest_meeting_point", locations=["1,2"])
    client.get = lambda *args, **kwargs: {"elements": []}
    result = call(create_server(client), "suggest_meeting_point", locations=["1,2", "3,4"])
    assert "midpoint" in result

    client = FixtureClient()
    def response(url, **kwargs):
        if "/search" in url:
            return [{"lat": "1", "lon": "2", "display_name": "place"}]
        if "overpass" in url:
            return {"elements": [{"type": "node", "id": 8, "lat": 1, "lon": 2, "tags": {"name": "Cafe"}}]}
        if "/table/" in url:
            return {"code": "Ok", "durations": [[None], [None]]}
        raise AssertionError(url)
    client.get = response
    result = call(create_server(client), "suggest_meeting_point", locations=["A", "B"])
    assert result["suggestion"]["name"] == "Cafe"
    assert [entry["duration"] for entry in result["travel_times"]] == ["unknown", "unknown"]


def test_map_link_requires_one_supported_shape():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="provide either"):
        call(server, "map_link")


def test_address_resolution_failure_multileg_steps_and_truncation():
    client = FixtureClient()
    client.get = lambda url, params=None, **kwargs: [] if "/search" in url else None
    with pytest.raises(ValueError, match="no location found"):
        call(create_server(client), "route", waypoints=["Unknown", "1,2"], profile="foot")

    def routed(url, params=None, **kwargs):
        if "/search" in url:
            return [{"lat": "1", "lon": "2", "display_name": params["q"]}]
        steps = [{"distance": 10, "name": "Road", "maneuver": {"type": "turn", "modifier": "left"}} for _ in range(101)]
        steps.append({"distance": 0, "name": "", "maneuver": {"type": "arrive"}})
        return {"code": "Ok", "routes": [{"distance": 900, "duration": 100, "legs": [{"distance": 400, "duration": 40, "summary": "A", "steps": steps}, {"distance": 500, "duration": 60, "steps": []}]}]}
    client.get = routed
    result = call(create_server(client), "route", waypoints=["A", "B", "C"], profile="foot", include_steps=True)
    assert len(result["legs"]) == 2
    assert len(result["steps"]) == 100
    assert "steps_truncated" in result


def test_routing_boundary_and_profile_validation_branches():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="foot, car or bike"):
        call(server, "route", waypoints=["1,2", "3,4"], profile="train")
    with pytest.raises(ValueError, match="origins \\+ destinations"):
        call(server, "route_matrix", origins=["1,2"] * 13, destinations=["3,4"], profile="car")
    with pytest.raises(ValueError, match="origins \\+ destinations"):
        call(server, "route_matrix", origins=["1,2"] * 12, destinations=["3,4"] * 13, profile="car")
    with pytest.raises(ValueError, match="3–12"):
        call(server, "optimize_route", stops=["1,2"] * 13, profile="car")
    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"code": "NoRoute", "trips": []}
    with pytest.raises(RuntimeError, match="OSRM trip failed"):
        call(create_server(client), "optimize_route", stops=["1,2", "3,4", "5,6"], profile="car")


def test_isochrone_other_budget_edges_and_valhalla_request_shape():
    server = create_server(FixtureClient())
    with pytest.raises(ValueError, match="exactly one"):
        call(server, "isochrone", center="1,2", profile="foot", minutes=5, kilometers=1)
    with pytest.raises(ValueError, match="minutes must"):
        call(server, "isochrone", center="1,2", profile="foot", minutes=121)
    with pytest.raises(ValueError, match="kilometers must"):
        call(server, "isochrone", center="1,2", profile="foot", kilometers=0.05)
    client = FixtureClient()
    captured = []
    def valhalla(url, params=None, **kwargs):
        captured.append((url, params))
        return {"features": [{"geometry": {"coordinates": [[2, 1], [4, 3]]}}]}
    client.get = valhalla
    result = call(create_server(client), "isochrone", center="1,2", profile="car", kilometers=2)
    assert result["engine"] == "valhalla"
    assert '"costing": "auto"' in captured[0][1]["json"]


def test_poi_endpoint_failures_and_missing_coordinates():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline"))
    with pytest.raises(RuntimeError, match="all Overpass endpoints failed"):
        call(create_server(client), "poi_details", osm_id="node/1")

    client = FixtureClient()
    client.get = lambda *args, **kwargs: {"elements": [{"type": "way", "id": 1, "center": {}, "tags": {}}]}
    result = call(create_server(client), "poi_details", osm_id="way/1")
    assert "lat" not in result

    client = FixtureClient()
    client.get = lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline"))
    with pytest.raises(RuntimeError, match="all Overpass endpoints failed"):
        call(create_server(client), "suggest_meeting_point", locations=["1,2", "3,4"])


def test_tool_selector_errors_and_empty_filter(monkeypatch):
    monkeypatch.setenv("OSM_ALLOW_TOOLS", "not_a_tool")
    with pytest.raises(ValueError, match="unknown OSM tool selector"):
        create_server(FixtureClient())
    monkeypatch.setenv("OSM_ALLOW_TOOLS", "geocode")
    monkeypatch.setenv("OSM_DENY_TOOLS", "geocode")
    with pytest.raises(ValueError, match="empty tool list"):
        create_server(FixtureClient())


def test_main_runs_stdio_and_reports_startup_errors(monkeypatch, capsys):
    import osm_mcp.server as server_module

    class FakeServer:
        def run(self, transport):
            assert transport == "stdio"
    monkeypatch.setattr(server_module, "create_server", lambda: FakeServer())
    server_module.main()

    def failed_server():
        raise RuntimeError("bad config")
    monkeypatch.setattr(server_module, "create_server", failed_server)
    with pytest.raises(SystemExit) as error:
        server_module.main()
    assert error.value.code == 1
    assert "bad config" in capsys.readouterr().err


def test_ors_route_steps_matrix_and_non_roundtrip_trip():
    client = FixtureClient()
    client.key = "test-key-0123456789"
    server = create_server(client)
    route = call(server, "route", waypoints=["1,2", "3,4"], profile="foot", include_steps=True)
    assert route["steps"][0]["instruction"] == "turn left"
    assert call(server, "route_matrix", origins=["1,2"], destinations=["3,4"], profile="car")["engine"] == "openrouteservice"

    client = FixtureClient()
    captured = []
    def trip(url, params=None, **kwargs):
        captured.append(params)
        return {"code": "Ok", "trips": [{"distance": 100, "duration": 60, "legs": [{"distance": 100, "duration": 60}] }], "waypoints": [{"waypoint_index": 0}, {"waypoint_index": 1}, {"waypoint_index": 2}]}
    client.get = trip
    result = call(create_server(client), "optimize_route", stops=["1,2", "3,4", "5,6"], profile="car", roundtrip=False)
    assert not result["optimized_order"][-1].endswith("back to start")
    assert captured[0]["destination"] == "last"


def test_mcp_dispatch_preserves_tool_errors():
    import asyncio
    server = create_server(FixtureClient())
    with pytest.raises(Exception):
        asyncio.run(server._tool_manager.call_tool("route", {"waypoints": ["1,2"], "profile": "foot"}, convert_result=False))


def test_nearby_search_reports_exhausted_overpass_backends():
    client = FixtureClient()
    client.get = lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline"))
    with pytest.raises(RuntimeError, match="all Overpass endpoints failed"):
        call(create_server(client), "find_nearby_pois", near="1,2", category="cafe")


def test_overpass_http_200_runtime_remark_fails_over_to_next_mirror():
    client = FixtureClient()
    client.overpass = ["https://mirror-one.example/api", "https://mirror-two.example/api"]
    calls = []

    def response(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return {"remark": "runtime error: attic out of memory", "elements": []}
        return {"elements": [{"type": "node", "id": 9, "lat": 1, "lon": 2, "tags": {"name": "Cafe"}}]}

    client.get = response
    result = call(create_server(client), "find_nearby_pois", near="1,2", category="cafe")
    assert len(calls) == 2
    assert result["results"][0]["osm"] == "node/9"
