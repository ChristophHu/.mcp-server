from collections import OrderedDict
import json
import re
from urllib.parse import unquote, urlparse
import threading
import time

import httpx
from .shaping import sanitize_error_body

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024
MAX_CACHE_ENTRIES = 500
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHEABLE_CHARS = 1024 * 1024
MAX_QUEUE_DEPTH = 32


class OsmApiError(RuntimeError):
    def __init__(self, status, body, service, url):
        self.status = status
        self.body = sanitize_error_body(body)
        self.service = service
        self.url = url
        origin = urlparse(url).netloc or "(unparseable URL)"
        hint = " wait ~30 seconds and retry" if status in (408, 429) or status >= 500 else ""
        super().__init__("{} request to {} failed with HTTP {}.{}".format(service, origin, status, hint))


def _safe_cache_size(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    except (TypeError, ValueError):
        return len(repr(value))

DEFAULTS = {
    "NOMINATIM_BASE_URL": "https://nominatim.openstreetmap.org",
    "PHOTON_BASE_URL": "https://photon.komoot.io",
    "OSRM_BASE_URL": "https://routing.openstreetmap.de",
    "OVERPASS_BASE_URL": "https://z.overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter",
    "VALHALLA_BASE_URL": "https://valhalla1.openstreetmap.de",
    "ORS_BASE_URL": "https://api.openrouteservice.org",
}


class OsmClient:
    def __init__(self):
        import os
        self.key = os.environ.pop("ORS_API_KEY", None)
        self.user_agent = os.getenv("OSM_USER_AGENT", "osm-mcp/0.3.2 (+https://github.com/ni-c/osm-mcp)")
        self.ttl = int(os.getenv("OSM_CACHE_TTL", "3600"))
        if self.ttl < 0:
            raise ValueError("OSM_CACHE_TTL must be a number of seconds")
        if self.key and (not 8 <= len(self.key) <= 256 or any(ord(ch) < 33 or ord(ch) > 126 for ch in self.key)):
            raise ValueError("ORS_API_KEY must be 8 to 256 visible ASCII characters without whitespace")
        self.urls = {k: os.getenv(k, v).rstrip("/") for k, v in DEFAULTS.items()}
        for name, value in self.urls.items():
            parsed = urlparse(value)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("{} must be a plain http(s) base URL without credentials, query or fragment".format(name))
            if name == "ORS_BASE_URL" and self.key and parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError("ORS_BASE_URL must use https:// when ORS_API_KEY is set")
        self.overpass = [v.strip() for v in os.getenv("OVERPASS_BASE_URL", DEFAULTS["OVERPASS_BASE_URL"]).split(",") if v.strip()]
        if not self.overpass or len(self.overpass) > 8:
            raise ValueError("OVERPASS_BASE_URL must contain 1 to 8 endpoints")
        for endpoint in self.overpass:
            parsed = urlparse(endpoint)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("OVERPASS_BASE_URL endpoints must be plain http(s) URLs without credentials, query or fragment")
        self.cache = OrderedDict()
        self._cache_bytes = 0
        self.client = httpx.Client(headers={"User-Agent": self.user_agent, "Accept": "application/json"}, timeout=30, follow_redirects=False)
        self._rate_lock = threading.Lock()
        self._last_request = {}
        self._pending = {}
        self.secret_fragments = {self.key} if self.key and len(self.key) >= 8 else set()
        for value in self.urls.values():
            for segment in urlparse(value).path.split("/"):
                if len(segment) >= 8:
                    self.secret_fragments.add(segment)
                    self.secret_fragments.add(unquote(segment))

    def get(self, url, *, params=None, post=None, headers=None, cache=True, timeout=None):
        method = "POST" if post is not None else "GET"
        service = self._service_for(url)
        cache_key = (service, method, url, repr(params), repr(post))
        cached = self.cache.get(cache_key) if cache else None
        if cached is not None:
            if cached[0] > time.monotonic():
                return cached[1]
            self._delete_cache(cache_key)
        origin = urlparse(url).netloc.lower()
        with self._rate_lock:
            now = time.monotonic()
            pending = self._pending.get(origin, 0)
            if pending >= MAX_QUEUE_DEPTH:
                raise RuntimeError("too many queued requests for this service — rate-limit queue is full; retry in a moment or batch fewer locations per call")
            self._pending[origin] = pending + 1
            slot = max(now, self._last_request.get(origin, now))
            wait = slot - now
            self._last_request[origin] = slot + (1.6 if service == "ors" else 1.1)
        try:
            if wait > 0:
                time.sleep(wait)
            method = "POST" if post is not None else "GET"
            if hasattr(self.client, "stream"):
                with self.client.stream(method, url, params=params, data=post, headers=headers, timeout=timeout) as response:
                    return self._handle_response(response, url, cache_key, cache)
            response = self.client.post(url, data=post, headers=headers) if post is not None else self.client.get(url, params=params, headers=headers)
            return self._handle_response(response, url, cache_key, cache)
        finally:
            with self._rate_lock:
                remaining = self._pending.get(origin, 1) - 1
                if remaining:
                    self._pending[origin] = remaining
                else:
                    self._pending.pop(origin, None)

    def _handle_response(self, response, url, cache_key, cache):
        status = response.status_code
        error = status >= 400
        limit = MAX_ERROR_BYTES if error else MAX_RESPONSE_BYTES
        chunks = []
        headers = getattr(response, "headers", {}) or {}
        try:
            declared = int(headers.get("content-length", 0) or 0)
        except (TypeError, ValueError):
            declared = 0
        if not error and declared > MAX_RESPONSE_BYTES:
            raise RuntimeError("upstream response is too large ({} bytes, cap {})".format(declared, MAX_RESPONSE_BYTES))
        if hasattr(response, "iter_bytes"):
            received = 0
            for chunk in response.iter_bytes():
                remaining = limit - received
                if len(chunk) > remaining:
                    if not error:
                        raise RuntimeError("upstream response exceeded the {}-byte cap".format(MAX_RESPONSE_BYTES))
                    chunks.append(chunk[:max(0, remaining)])
                    break
                chunks.append(chunk)
                received += len(chunk)
        else:
            content = getattr(response, "content", None)
            if content is None:
                if error:
                    try:
                        content = json.dumps(response.json()).encode()
                    except ValueError:
                        content = b""
                else:
                    content = None
            if content is not None:
                if not error and len(content) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("upstream response exceeded the {}-byte cap".format(MAX_RESPONSE_BYTES))
                chunks.append(content[:limit])
        if error:
            body = self._redact(sanitize_error_body(b"".join(chunks).decode("utf-8", errors="replace")))
            raise OsmApiError(status, body, self._service_for(url), self._redact_url(url))
        try:
            if chunks:
                raw = b"".join(chunks)
                data = json.loads(raw)
                text_size = len(raw.decode("utf-8", errors="replace"))
            elif hasattr(response, "json"):
                data = response.json()
                text_size = _safe_cache_size(data)
            else:
                raise ValueError("empty response")
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError("upstream service returned invalid JSON")
        if cache and self.ttl > 0 and text_size <= MAX_CACHEABLE_CHARS:
            self._set_cache(cache_key, data, text_size)
        return data

    def _service_for(self, url):
        for name, base in self.urls.items():
            if url.startswith(base):
                return name.removesuffix("_BASE_URL").lower()
        return urlparse(url).hostname or "upstream"

    def _redact(self, text):
        for fragment in sorted(self.secret_fragments, key=len, reverse=True):
            text = text.replace(fragment, "[redacted]")
        return text

    def _redact_url(self, url):
        return re.sub(r"([?&](?:api_?key|key|token|access_token)=)[^&]*", r"\1[redacted]", url, flags=re.IGNORECASE)

    def _set_cache(self, key, value, size):
        self._delete_cache(key)
        now = time.monotonic()
        for old_key, (expires, _, _) in list(self.cache.items()):
            if expires <= now:
                self._delete_cache(old_key)
        while self.cache and (len(self.cache) >= MAX_CACHE_ENTRIES or self._cache_bytes + size > MAX_CACHE_BYTES):
            oldest = next(iter(self.cache))
            self._delete_cache(oldest)
        if size <= MAX_CACHE_BYTES:
            self.cache[key] = (now + self.ttl, value, size)
            self._cache_bytes += size

    def _delete_cache(self, key):
        entry = self.cache.pop(key, None)
        if entry is not None:
            self._cache_bytes -= entry[2]
