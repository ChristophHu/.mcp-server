import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_mcp_client_can_discover_and_call_get_note() -> None:
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="# Hello")),
    )
    server = create_server(api)
    try:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {"obsidian_get_note", "obsidian_list_notes", "obsidian_search_notes"} <= names
            result = await client.call_tool("obsidian_get_note", {"path": "Inbox.md"})
    finally:
        await api.aclose()

    assert result.structured_content == {"content": "# Hello", "path": "Inbox.md"}


@pytest.mark.asyncio
async def test_rest_write_note_is_disabled_without_conditional_create_support() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_note", {"path": "Inbox/New.md", "content": "# New\n"}
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_write_note_overwrite_is_rejected_without_target_bound_approval() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(200, text="existing"))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_note",
                {"path": "Inbox.md", "content": "replacement", "overwrite": True},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_write_note_fails_closed_when_writes_are_not_enabled() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_note", {"path": "Inbox.md", "content": "New text"}
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_get_note_links_returns_plugin_link_metadata() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "filename": "Notes/Target.md",
                    "result": [["Other.md"], ["Source.md"], ["Missing.md"]],
                }
            ],
        )

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool("obsidian_get_note_links", {"path": "Notes/Target.md"})
    finally:
        await api.aclose()

    assert result.structured_content == {
        "path": "Notes/Target.md",
        "links": ["Other.md"],
        "backlinks": ["Source.md"],
        "unresolved_links": ["Missing.md"],
        "metadata_complete": True,
    }
    assert requests[0].headers["content-type"] == "application/vnd.olrapi.jsonlogic+json"


@pytest.mark.asyncio
async def test_get_note_links_falls_back_to_outgoing_parser_without_plugin_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="[[Linked.md]] and `[[Example]]`")
        return httpx.Response(
            200, json=[{"filename": "Notes/Target.md", "result": [None, None, None]}]
        )

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool("obsidian_get_note_links", {"path": "Notes/Target.md"})
    finally:
        await api.aclose()

    assert result.structured_content == {
        "path": "Notes/Target.md",
        "links": ["Linked.md"],
        "backlinks": None,
        "unresolved_links": None,
        "metadata_complete": False,
    }


@pytest.mark.asyncio
async def test_hidden_vault_paths_are_rejected_before_api_access() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(200, text="secret"))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_get_note", {"path": ".obsidian/plugins/settings.json"}
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_write_daily_note_rejects_existing_note_without_overwrite() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="# Existing\n")

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_daily_note",
                {"note_date": "2026-10-26", "content": "# New\n"},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_rest_daily_note_overwrite_is_denied_before_backend_access() -> None:
    requests = []
    existing = (
        "---\ntitle: Monday\ntags: []\ncreatedAt: '2026-10-26T08:00:00Z'\n"
        "updatedAt: '2026-10-26T08:00:00Z'\nstatus: active\n---\n# Existing\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, text=existing)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_daily_note",
                {"note_date": "2026-10-26", "content": "# Updated\n", "overwrite": True},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_rest_append_is_denied_before_backend_access() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(200, text="# Existing"))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_append_to_note", {"path": "Inbox.md", "content": "append"}
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_write_daily_note_fails_closed_when_writes_are_disabled() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(404))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_daily_note",
                {"note_date": "2026-10-26", "content": "# Monday\n"},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_write_daily_note_requires_canonical_iso_date() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(404))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_daily_note",
                {"note_date": "20261026", "content": "# Monday\n"},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_rest_daily_note_create_is_denied_before_backend_access() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_write_daily_note",
                {"note_date": "2026-10-26", "content": "# Monday\n"},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []
