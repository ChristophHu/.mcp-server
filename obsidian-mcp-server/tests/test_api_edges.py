from datetime import date

import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


def make_api(handler, *, settings=None):
    return ObsidianApi(
        settings or Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_status_and_note_json_accept_mapping_responses():
    def handler(request):
        if request.url.path == "/":
            return httpx.Response(200, json={"versions": {"local": "1"}})
        return httpx.Response(200, json={"path": "Note.md", "frontmatter": {}})

    api = make_api(handler)
    try:
        assert await api.get_status() == {"versions": {"local": "1"}}
        assert await api.get_note_json("Folder/Note.md") == {"path": "Note.md", "frontmatter": {}}
    finally:
        await api.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "payload", "method"),
    [
        ("/", [], "get_status"),
        ("/vault/Note.md", [], "get_note_json"),
    ],
)
async def test_json_endpoints_reject_non_mapping_payloads(url, payload, method):
    api = make_api(lambda request: httpx.Response(200, json=payload))
    try:
        with pytest.raises(RuntimeError, match="invalid"):
            if method == "get_note_json":
                await api.get_note_json("Note.md")
            else:
                await api.get_status()
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_get_note_uses_encoded_vault_path_and_text_accept_header():
    requests = []
    api = make_api(lambda request: (requests.append(request), httpx.Response(200, text="body"))[1])
    try:
        assert await api.get_note("Folder/A note.md") == "body"
    finally:
        await api.aclose()
    assert requests[0].url.path == "/vault/Folder/A note.md"
    assert requests[0].headers["accept"] == "text/markdown"


@pytest.mark.asyncio
async def test_periodic_note_rejects_unsupported_period():
    api = make_api(lambda request: httpx.Response(200, text="unused"))
    try:
        with pytest.raises(ValueError, match="Unsupported periodic"):
            await api.get_periodic_note("biweekly", date(2026, 1, 2))
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_request_fails_closed_without_api_key():
    api = make_api(
        lambda request: httpx.Response(200),
        settings=Settings(api_url="https://obsidian.local", api_key=""),
    )
    try:
        with pytest.raises(RuntimeError, match="API_KEY is required"):
            await api.get_status()
        with pytest.raises(RuntimeError, match="API_KEY is required"):
            await api.get_note("Note.md")
    finally:
        await api.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (httpx.TimeoutException("secret timeout"), "request timed out"),
        (httpx.ConnectError("secret connection"), "request failed"),
    ],
)
async def test_request_maps_transport_errors_without_leaking_details(exception, message):
    def handler(request):
        raise exception

    api = make_api(handler)
    try:
        with pytest.raises(RuntimeError, match=message) as caught:
            await api.get_status()
        assert "secret" not in str(caught.value)
    finally:
        await api.aclose()


@pytest.mark.parametrize(
    ("status", "error", "message"),
    [
        (401, RuntimeError, "rejected the API key"),
        (404, FileNotFoundError, "not found"),
        (500, RuntimeError, "HTTP 500"),
    ],
)
def test_http_status_errors_are_mapped(status, error, message):
    with pytest.raises(error, match=message):
        ObsidianApi._raise_response_error(httpx.Response(status))


def test_successful_response_is_not_rejected():
    ObsidianApi._raise_response_error(httpx.Response(200))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "encoding"),
    [(b"\xff", "ascii"), (b"body", "not-a-real-codec")],
)
async def test_note_decode_errors_are_sanitized(body, encoding):
    def handler(request):
        response = httpx.Response(200, content=body)
        response.encoding = encoding
        return response

    api = make_api(handler)
    try:
        with pytest.raises(RuntimeError, match="not valid text"):
            await api.get_note("Note.md")
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_stream_request_maps_timeout_and_http_failures():
    for exception, expected in [
        (httpx.TimeoutException("timeout"), "timed out"),
        (httpx.ConnectError("connection"), "request failed"),
    ]:
        api = make_api(lambda request, exc=exception: (_ for _ in ()).throw(exc))
        try:
            with pytest.raises(RuntimeError, match=expected):
                await api.get_note("Note.md")
        finally:
            await api.aclose()


@pytest.mark.asyncio
async def test_list_files_supports_vault_root_and_subdirectories():
    requests = []
    api = make_api(
        lambda request: (requests.append(request), httpx.Response(200, json={"files": ["A.md"]}))[1]
    )
    try:
        assert await api.list_files() == ["A.md"]
        assert await api.list_files("Folder") == ["A.md"]
    finally:
        await api.aclose()
    assert [request.url.path for request in requests] == ["/vault/", "/vault/Folder/"]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"files": "bad"}, {"files": [1]}])
async def test_list_files_rejects_invalid_payloads(payload):
    api = make_api(lambda request: httpx.Response(200, json=payload))
    try:
        with pytest.raises(RuntimeError, match="invalid file listing"):
            await api.list_files()
    finally:
        await api.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "payload", "message"),
    [
        ("list_tags", {}, "invalid tag listing"),
        ("search_notes", {}, "invalid search response"),
        ("search_jsonlogic", {}, "invalid structured search"),
    ],
)
async def test_collection_endpoints_reject_invalid_json_shapes(method, payload, message):
    api = make_api(lambda request: httpx.Response(200, json=payload))
    try:
        with pytest.raises(RuntimeError, match=message):
            if method == "list_tags":
                await api.list_tags()
            elif method == "search_notes":
                await api.search_notes("term")
            else:
                await api.search_jsonlogic({"==": [1, 1]})
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_write_note_obeys_permission_scope_method_and_size_limit():
    requests = []
    transport = httpx.MockTransport(
        lambda request: (requests.append(request), httpx.Response(204))[1]
    )
    denied = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="x"), transport=transport
    )
    try:
        with pytest.raises(PermissionError):
            await denied.write_note("Note.md", "x")
    finally:
        await denied.aclose()
    limited = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="x",
            enable_writes=True,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Archive",
            max_content_bytes=1,
        ),
        transport=transport,
    )
    try:
        with pytest.raises(ValueError, match="content limit"):
            await limited.write_note("Archive/Note.md", "xx", frontmatter_migration=True)
    finally:
        await limited.aclose()
    assert requests == []


@pytest.mark.asyncio
async def test_rest_write_requires_migration_and_rejects_append():
    requests = []
    settings = Settings(
        api_url="https://obsidian.local",
        api_key="x",
        enable_writes=True,
        enable_frontmatter_migration=True,
        frontmatter_migration_root="Archive",
    )
    api = make_api(
        lambda request: (requests.append(request), httpx.Response(204))[1], settings=settings
    )
    try:
        with pytest.raises(PermissionError):
            await api.write_note("Elsewhere/Note.md", "x", frontmatter_migration=True)
        with pytest.raises(PermissionError, match="conditional no-clobber"):
            await api.write_note("Archive/Note.md", "created")
        with pytest.raises(PermissionError, match="append writes"):
            await api.write_note(
                "Archive/Note.md", "appended", append=True, frontmatter_migration=True
            )
        await api.write_note("Archive/Note.md", "migrated", frontmatter_migration=True)
    finally:
        await api.aclose()
    assert [request.method for request in requests] == ["PUT"]


@pytest.mark.asyncio
async def test_write_note_denies_migration_without_separate_permission_or_root():
    for settings in [
        Settings(api_url="https://obsidian.local", api_key="x", enable_writes=True),
        Settings(
            api_url="https://obsidian.local",
            api_key="x",
            enable_writes=True,
            enable_frontmatter_migration=True,
        ),
    ]:
        api = make_api(lambda request: httpx.Response(204), settings=settings)
        try:
            with pytest.raises(PermissionError):
                await api.write_note("Archive/Note.md", "x", frontmatter_migration=True)
        finally:
            await api.aclose()


@pytest.mark.asyncio
async def test_open_in_ui_omits_new_leaf_parameter_by_default():
    requests = []
    api = make_api(lambda request: (requests.append(request), httpx.Response(204))[1])
    try:
        await api.open_in_ui("Note.md")
    finally:
        await api.aclose()
    assert dict(requests[0].url.params) == {}
