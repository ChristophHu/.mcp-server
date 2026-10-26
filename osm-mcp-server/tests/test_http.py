import pytest

from osm_mcp.http import OsmClient


def test_ors_secret_is_removed_and_rejected_when_header_unsafe(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "unsafe\nsecret")
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        OsmClient()
    assert "ORS_API_KEY" not in __import__("os").environ


def test_ors_secret_requires_https_for_remote_endpoint(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "valid-key-123456")
    monkeypatch.setenv("ORS_BASE_URL", "http://ors.example.test")
    with pytest.raises(ValueError, match="https"):
        OsmClient()


def test_overpass_config_is_limited_to_eight_endpoints(monkeypatch):
    monkeypatch.setenv("OVERPASS_BASE_URL", ",".join("https://m{}.example/api".format(i) for i in range(9)))
    with pytest.raises(ValueError, match="8"):
        OsmClient()


def test_credentials_and_query_components_are_rejected_in_base_urls(monkeypatch):
    monkeypatch.setenv("OSRM_BASE_URL", "https://user:secret@example.test/api")
    with pytest.raises(ValueError, match="plain http"):
        OsmClient()


def test_nominatim_requests_are_spaced_by_reference_interval(monkeypatch):
    import time

    sleeps = []
    now = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    def fake_sleep(delay):
        sleeps.append(delay)
        now[0] += delay
    monkeypatch.setattr(time, "sleep", fake_sleep)

    class Response:
        status_code = 200
        @staticmethod
        def json():
            return {"ok": True}

    class FakeHttpx:
        def __init__(self, **kwargs):
            pass
        @staticmethod
        def get(*args, **kwargs):
            return Response()

    monkeypatch.setattr("osm_mcp.http.httpx.Client", FakeHttpx)
    client = OsmClient()
    client.get("https://nominatim.openstreetmap.org/search", params={"q": "A"}, cache=False)
    client.get("https://nominatim.openstreetmap.org/reverse", params={"q": "B"}, cache=False)
    assert len(sleeps) == 1
    assert round(sleeps[0], 1) == 1.1
