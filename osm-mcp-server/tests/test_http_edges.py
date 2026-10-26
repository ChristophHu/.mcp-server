import pytest

from osm_mcp.http import OsmClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self.payload = payload if payload is not None else {"ok": True}
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("invalid")
        return self.payload


class FakeTransport:
    response = FakeResponse()

    def __init__(self, **kwargs):
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append(("get", url, params, headers))
        return type(self).response

    def post(self, url, data=None, headers=None):
        self.calls.append(("post", url, data, headers))
        return type(self).response


def patch_transport(monkeypatch):
    monkeypatch.setattr("osm_mcp.http.httpx.Client", FakeTransport)


def test_invalid_ttl_is_rejected_and_secret_is_removed(monkeypatch):
    monkeypatch.setenv("ORS_API_KEY", "valid-secret-123")
    monkeypatch.setenv("OSM_CACHE_TTL", "-1")
    with pytest.raises(ValueError, match="OSM_CACHE_TTL"):
        OsmClient()
    assert "ORS_API_KEY" not in __import__("os").environ


def test_non_numeric_ttl_is_rejected(monkeypatch):
    monkeypatch.setenv("OSM_CACHE_TTL", "soon")
    with pytest.raises(ValueError):
        OsmClient()


def test_overpass_endpoint_urls_are_validated(monkeypatch):
    monkeypatch.setenv("OVERPASS_BASE_URL", "https://valid.example/api,not-a-url")
    with pytest.raises(ValueError, match="OVERPASS_BASE_URL endpoints"):
        OsmClient()


def test_cache_hit_skips_http_and_post_requests_are_supported(monkeypatch):
    patch_transport(monkeypatch)
    monkeypatch.setattr("osm_mcp.http.time.sleep", lambda _: None)
    FakeTransport.response = FakeResponse(payload={"value": 7})
    client = OsmClient()
    first = client.get("https://service.example/one", params={"q": "x"})
    second = client.get("https://service.example/one", params={"q": "x"})
    posted = client.get("https://service.example/two", post={"data": "query"}, headers={"Content-Type": "application/x-www-form-urlencoded"}, cache=False)
    assert first == second == {"value": 7}
    assert posted == {"value": 7}
    assert len(client.client.calls) == 2
    assert client.client.calls[-1][0] == "post"


@pytest.mark.parametrize("status,hint", [(400, ""), (429, "wait ~30 seconds"), (503, "wait ~30 seconds")])
def test_http_errors_are_sanitized_and_rate_limit_hint_is_status_specific(monkeypatch, status, hint):
    patch_transport(monkeypatch)
    monkeypatch.setattr("osm_mcp.http.time.sleep", lambda _: None)
    FakeTransport.response = FakeResponse(status_code=status)
    with pytest.raises(RuntimeError) as error:
        OsmClient().get("https://service.example/path?token=secret", cache=False)
    assert "secret" not in str(error.value)
    assert hint in str(error.value)


def test_invalid_json_is_reported(monkeypatch):
    patch_transport(monkeypatch)
    monkeypatch.setattr("osm_mcp.http.time.sleep", lambda _: None)
    FakeTransport.response = FakeResponse(json_error=True)
    with pytest.raises(RuntimeError, match="invalid JSON"):
        OsmClient().get("https://service.example/path", cache=False)


def test_response_body_over_eight_mib_is_rejected_before_json_parse(monkeypatch):
    patch_transport(monkeypatch)
    monkeypatch.setattr("osm_mcp.http.time.sleep", lambda _: None)

    class LargeResponse:
        status_code = 200
        headers = {"content-length": str(8 * 1024 * 1024 + 1)}

        @staticmethod
        def json():
            raise AssertionError("oversized body must not be parsed")

    FakeTransport.response = LargeResponse()
    with pytest.raises(RuntimeError, match="too large"):
        OsmClient().get("https://service.example/large", cache=False)


def test_cache_retains_no_more_than_500_entries(monkeypatch):
    patch_transport(monkeypatch)
    monkeypatch.setattr("osm_mcp.http.time.sleep", lambda _: None)
    FakeTransport.response = FakeResponse()
    client = OsmClient()
    for index in range(501):
        client.get("https://service-{}.example/path".format(index))
    assert len(client.cache) == 500
