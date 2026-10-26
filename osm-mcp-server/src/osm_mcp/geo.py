import math
import re
from typing import Optional, Tuple

LatLon = Tuple[float, float]
EARTH_RADIUS_M = 6_371_000


def parse_coordinates(value: str) -> Optional[LatLon]:
    match = re.fullmatch(r"\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*", value)
    if not match:
        return None
    lat, lon = map(float, match.groups())
    return (lat, lon) if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 else None


def haversine_meters(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(h), math.sqrt(max(0, 1 - h)))


def format_distance(meters: float) -> str:
    if not math.isfinite(meters):
        return "unknown"
    if meters < 1000:
        return "{} m".format(js_round(meters))
    km = meters / 1000
    return "{:.1f} km".format(js_round(km * 10) / 10) if km < 10 else "{} km".format(js_round(km))


def format_duration(seconds: float) -> str:
    minutes = js_round(seconds / 60)
    if minutes < 1:
        return "< 1 min"
    if minutes < 60:
        return "{} min".format(minutes)
    hours, rest = divmod(minutes, 60)
    return "{} h{}".format(hours, " {} min".format(rest) if rest else "")


def round_coord(value: float) -> float:
    return js_round(value * 1e5) / 1e5


def js_round(value: float) -> int:
    """Match JavaScript Math.round (ties toward positive infinity)."""
    return math.floor(value + 0.5)


def flatten_coordinates(tree):
    points = []
    def walk(node):
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in node[:2]):
                lon, lat = node[:2]
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    if len(points) >= 500_000:
                        raise ValueError("isochrone returned more than 500000 contour points")
                    points.append((lat, lon))
                    return
            for child in node:
                walk(child)
    walk(tree)
    return points


def bounding_box(points):
    if not points:
        raise ValueError("no coordinates")
    return {"north": max(p[0] for p in points), "south": min(p[0] for p in points), "east": max(p[1] for p in points), "west": min(p[1] for p in points)}
