import asyncio

from osm_mcp.http import DEFAULTS
from osm_mcp.server import create_server


class FixtureClient:
    def __init__(self):
        self.urls = dict(DEFAULTS)
        self.overpass = ["https://overpass.example/api"]
        self.key = None
        self.calls = []

    def get(self, url, *, params=None, post=None, headers=None, cache=True):
        self.calls.append((url, params, post, headers))
        if "/search" in url:
            if params and params.get("q") == "No Such Place":
                return []
            name = "Trier " + self.key if self.key else "Trier"
            return [{"lat": "49.75", "lon": "6.64", "display_name": name, "osm_type": "node", "osm_id": 42}]
        if "/reverse" in url:
            return {"lat": "49.75", "lon": "6.64", "display_name": "Trier"}
        if "/api" in url and "photon" in url:
            return {"features": [{"geometry": {"coordinates": [6.64, 49.75]}, "properties": {"name": "Trier"}}]}
        if "/route/" in url:
            return {"code": "Ok", "routes": [{"distance": 1200, "duration": 900, "legs": [{"distance": 1200, "duration": 900, "summary": "Main road", "steps": [{"distance": 500, "name": "A street", "maneuver": {"type": "turn", "modifier": "left"}}]}]}]}
        if "/table/" in url:
            if params and params.get("sources") == "0;1":
                return {"code": "Ok", "durations": [[600], [900]], "distances": [[1500], [2200]]}
            return {"code": "Ok", "durations": [[600]], "distances": [[1500]]}
        if "/v2/directions/" in url:
            return {"routes": [{"summary": {"distance": 1200, "duration": 900}, "segments": [{"distance": 1200, "duration": 900, "steps": [{"instruction": "turn left", "distance": 500}]}]}]}
        if "/v2/matrix/" in url:
            return {"durations": [[600]], "distances": [[1500]]}
        if "/trip/" in url:
            return {"code": "Ok", "trips": [{"distance": 3000, "duration": 2400, "legs": [{"distance": 1500, "duration": 1200}, {"distance": 1500, "duration": 1200}]}], "waypoints": [{"waypoint_index": 0}, {"waypoint_index": 1}, {"waypoint_index": 2}]}
        if "/isochrone" in url:
            return {"features": [{"geometry": {"coordinates": [[6.60, 49.74], [6.66, 49.77]]}, "properties": {"contour": 15}}]}
        if "overpass" in url:
            return {"elements": [{"type": "node", "id": 10, "lat": 49.75, "lon": 6.64, "tags": {"name": "Cafe One", "amenity": "cafe"}}]}
        raise AssertionError("unexpected upstream URL: " + url)


async def invoke(server, tool, arguments):
    return await server._tool_manager.call_tool(tool, arguments, convert_result=False)


def test_geocoding_tools_return_tagged_untrusted_results():
    client = FixtureClient()
    server = create_server(client)
    geocoded = asyncio.run(invoke(server, "geocode", {"query": "Trier"}))
    assert geocoded["results"][0]["osm"] == "node/42"
    assert geocoded["untrusted"] is True
    reverse = asyncio.run(invoke(server, "reverse_geocode", {"latitude": 49.75, "longitude": 6.64}))
    assert reverse["result"]["label"] == "Trier"
    fuzzy = asyncio.run(invoke(server, "geocode", {"query": "Trier", "provider": "photon"}))
    assert fuzzy["results"][0]["label"] == "Trier"


def test_routing_tools_compute_routes_matrix_and_itinerary():
    server = create_server(FixtureClient())
    route = asyncio.run(invoke(server, "route", {"waypoints": ["49.75,6.64", "49.76,6.65"], "profile": "foot", "include_steps": True}))
    assert route["distance_m"] == 1200
    assert route["steps"][0]["instruction"] == "turn left onto A street"
    matrix = asyncio.run(invoke(server, "route_matrix", {"origins": ["49.75,6.64"], "destinations": ["49.76,6.65"], "profile": "car"}))
    assert matrix["durations_minutes"] == [[10.0]]
    itinerary = asyncio.run(invoke(server, "optimize_route", {"stops": ["49.75,6.64", "49.76,6.65", "49.77,6.66"], "profile": "bike"}))
    assert itinerary["optimized_order"][-1] == "49.75,6.64 (back to start)"


def test_isochrone_poi_search_and_poi_details():
    server = create_server(FixtureClient())
    reach = asyncio.run(invoke(server, "isochrone", {"center": "49.75,6.64", "profile": "foot", "minutes": 15}))
    assert reach["bounding_box"] == {"north": 49.77, "south": 49.74, "east": 6.66, "west": 6.6}
    found = asyncio.run(invoke(server, "find_nearby_pois", {"near": "49.75,6.64", "category": "cafe"}))
    assert found["results"][0]["name"] == "Cafe One"
    detail = asyncio.run(invoke(server, "poi_details", {"osm_id": "node/10"}))
    assert detail["tags"]["amenity"] == "cafe"


def test_distance_meeting_suggestion_and_map_links():
    server = create_server(FixtureClient())
    distance = asyncio.run(invoke(server, "straight_line_distance", {"from": "49.75,6.64", "to": "49.76,6.65"}))
    assert distance["distance_m"] > 0
    meeting = asyncio.run(invoke(server, "suggest_meeting_point", {"locations": ["49.75,6.64", "49.76,6.65"]}))
    assert meeting["suggestion"]["name"] == "Cafe One"
    assert len(meeting["travel_times"]) == 2
    marker = asyncio.run(invoke(server, "map_link", {"place": "49.75,6.64"}))
    assert "openstreetmap.org" in marker["marker"]
    directions = asyncio.run(invoke(server, "map_link", {"from": "49.75,6.64", "to": "49.76,6.65"}))
    assert "fossgis_osrm_foot" in directions["directions"]


def test_ors_key_switches_route_and_matrix_to_openrouteservice():
    client = FixtureClient()
    client.key = "test-key-0123456789"
    server = create_server(client)
    result = asyncio.run(invoke(server, "route", {"waypoints": ["49.75,6.64", "49.76,6.65"], "profile": "car"}))
    assert result["engine"] == "openrouteservice"
    assert any("/v2/directions/driving-car" in call[0] for call in client.calls)
    matrix = asyncio.run(invoke(server, "route_matrix", {"origins": ["49.75,6.64"], "destinations": ["49.76,6.65"], "profile": "foot"}))
    assert matrix["engine"] == "openrouteservice"
    assert any("/v2/matrix/foot-walking" in call[0] for call in client.calls)


def test_allow_and_deny_environment_filters_registered_tools(monkeypatch):
    monkeypatch.setenv("OSM_ALLOW_TOOLS", "geocode,route,route_*")
    monkeypatch.setenv("OSM_DENY_TOOLS", "route_matrix")
    server = create_server(FixtureClient())
    assert set(server._tool_manager._tools) == {"geocode", "route"}


def test_every_tool_is_annotated_as_read_only_and_non_destructive():
    server = create_server(FixtureClient())
    for tool in server._tool_manager._tools.values():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.output_schema["type"] == "object"
        assert {"untrusted", "source"}.issubset(tool.output_schema["properties"])

    assert "from" in server._tool_manager._tools["straight_line_distance"].output_schema["properties"]
    assert "from_" not in server._tool_manager._tools["straight_line_distance"].output_schema["properties"]
    assert "results" in server._tool_manager._tools["geocode"].output_schema["required"]


def test_every_tool_serializes_a_structured_result_against_its_schema():
    server = create_server(FixtureClient())
    examples = {
        "geocode": {"query": "Trier"},
        "reverse_geocode": {"latitude": 49.75, "longitude": 6.64},
        "route": {"waypoints": ["49.75,6.64", "49.76,6.65"], "profile": "foot", "include_steps": True},
        "route_matrix": {"origins": ["49.75,6.64"], "destinations": ["49.76,6.65"], "profile": "car"},
        "optimize_route": {"stops": ["49.75,6.64", "49.76,6.65", "49.77,6.66"], "profile": "bike"},
        "isochrone": {"center": "49.75,6.64", "profile": "foot", "minutes": 15},
        "find_nearby_pois": {"near": "49.75,6.64", "category": "cafe"},
        "poi_details": {"osm_id": "node/10"},
        "suggest_meeting_point": {"locations": ["49.75,6.64", "49.76,6.65"]},
        "straight_line_distance": {"from": "49.75,6.64", "to": "49.76,6.65"},
        "map_link": {"place": "49.75,6.64"},
    }
    for name, arguments in examples.items():
        contents, structured = asyncio.run(
            server._tool_manager.call_tool(name, arguments, convert_result=True)
        )
        assert contents and structured["untrusted"] is True
        assert structured["source"] == "openstreetmap"


def test_routing_profile_schema_restricts_modes_to_supported_values():
    server = create_server(FixtureClient())
    for name in ("route", "route_matrix", "optimize_route", "isochrone", "suggest_meeting_point"):
        schema = server._tool_manager.get_tool(name).parameters
        assert schema["properties"]["profile"]["enum"] == ["foot", "car", "bike"]


def test_mcp_input_schemas_publish_reference_validation_constraints():
    server = create_server(FixtureClient())
    geocode = server._tool_manager.get_tool("geocode").parameters["properties"]
    assert geocode["query"]["minLength"] == 1
    assert geocode["query"]["maxLength"] == 300
    assert geocode["language"]["pattern"] == "^[a-zA-Z-]{2,10}$"
    assert geocode["provider"]["enum"] == ["nominatim", "photon"]
    route = server._tool_manager.get_tool("route").parameters["properties"]
    assert route["waypoints"]["minItems"] == 2
    assert route["waypoints"]["items"]["maxLength"] == 300


def test_server_identity_and_tool_titles_match_reference_metadata():
    server = create_server(FixtureClient())
    assert server._mcp_server.version == "0.3.2"
    assert server._mcp_server.website_url == "https://osm-mcp.ni-c.de"
    assert len(server._mcp_server.icons) == 2
    assert server._tool_manager.get_tool("geocode").title == "Geocode a place"


def test_tool_results_redact_the_configured_ors_secret():
    client = FixtureClient()
    client.key = "private-key-123456"
    result = asyncio.run(invoke(create_server(client), "geocode", {"query": "Trier"}))
    assert "private-key-123456" not in repr(result)
    assert "[redacted]" in repr(result)

