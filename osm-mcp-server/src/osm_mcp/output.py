from typing import Literal, NotRequired, Required, TypedDict


class Untrusted(TypedDict):
    untrusted: Literal[True]
    source: Literal["openstreetmap"]


class Place(TypedDict, total=False):
    label: str | None
    lat: float | None
    lon: float | None
    osm: str | None
    kind: str | None


class Poi(TypedDict, total=False):
    name: str | None
    lat: float | None
    lon: float | None
    osm: str | None
    distance: str | None
    amenity: str | None
    tourism: str | None
    shop: str | None
    leisure: str | None
    historic: str | None
    cuisine: str | None
    opening_hours: str | None
    website: str | None
    phone: str | None
    wheelchair: str | None


setattr(Poi, "__pydantic_config__", {"extra": "allow"})


RouteLeg = TypedDict("RouteLeg", {
    "from": NotRequired[str | None],
    "to": NotRequired[str | None],
    "distance": str,
    "duration": str,
    "via": NotRequired[str | None],
})


class BoundingBox(TypedDict):
    north: float
    south: float
    east: float
    west: float


class GeocodeOutput(Untrusted, total=False):
    provider: Literal["nominatim", "photon"] | None
    results: Required[list[Place]]
    note: str | None


class ReverseGeocodeOutput(Untrusted, total=False):
    result: Required[Place | None]
    note: str | None


class RouteOutput(Untrusted, total=False):
    profile: Required[Literal["foot", "car", "bike"]]
    engine: Required[Literal["openrouteservice", "osrm"]]
    waypoints: Required[list[str]]
    distance: Required[str]
    distance_m: Required[int]
    duration: Required[str]
    duration_s: Required[int]
    legs: list[RouteLeg] | None
    steps: list[dict[str, str]] | None
    steps_truncated: str | None


class MatrixOutput(Untrusted, total=False):
    profile: Required[Literal["foot", "car", "bike"]]
    engine: Required[Literal["openrouteservice", "osrm"]]
    origins: Required[list[str]]
    destinations: Required[list[str]]
    durations_minutes: Required[list[list[float | None]]]
    distances_km: Required[list[list[float | None]]]


class OptimizeOutput(Untrusted, total=False):
    profile: Required[Literal["foot", "car", "bike"]]
    engine: Required[Literal["osrm"]]
    optimized_order: Required[list[str]]
    distance: Required[str]
    duration: Required[str]
    legs: Required[list[RouteLeg]]


class IsochroneOutput(Untrusted, total=False):
    center: Required[str]
    profile: Required[Literal["foot", "car", "bike"]]
    engine: Required[Literal["openrouteservice", "valhalla"]]
    budget: Required[str]
    bounding_box: Required[BoundingBox]
    reach: Required[dict[str, str]]


class NearbyOutput(Untrusted, total=False):
    near: Required[str]
    category: Required[str]
    count: Required[int]
    note: str | None
    results: Required[list[Poi]]


class PoiDetailsOutput(Untrusted, total=False):
    osm: Required[str]
    name: Required[str]
    tags: Required[dict[str, str]]
    lat: float | None
    lon: float | None
    map: str | None
    tags_truncated: str | None


class MeetingPointOutput(Untrusted, total=False):
    profile: Literal["foot", "car", "bike"] | None
    note: str | None
    midpoint: dict[str, float] | None
    suggestion: Poi | None
    travel_times: list[dict[str, str]] | None
    alternatives: list[dict[str, str]] | None


DistanceOutput = TypedDict("DistanceOutput", {
    "untrusted": Literal[True],
    "source": Literal["openstreetmap"],
    "from": str,
    "to": str,
    "distance": str,
    "distance_m": int,
})


MapLinkOutput = TypedDict("MapLinkOutput", {
    "untrusted": Literal[True],
    "source": Literal["openstreetmap"],
    "place": NotRequired[str | None],
    "marker": NotRequired[str | None],
    "from": NotRequired[str | None],
    "to": NotRequired[str | None],
    "profile": NotRequired[Literal["foot", "car", "bike"] | None],
    "directions": NotRequired[str | None],
}, total=False)
