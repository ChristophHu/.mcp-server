import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_apply_migrates_legacy_note_after_rechecking_and_keeps_created_at_unknown() -> None:
    requests = []
    old_content = "# Legacy\nHistorical body\n"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["Legacy.md"]})
        if request.method == "GET":
            return httpx.Response(200, text=old_content)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            enable_writes=True,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Archive",
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_audit_frontmatter",
                {"path": "Archive", "apply": True, "max_files": 10},
            )
    finally:
        await api.aclose()

    assert result.structured_content["apply_status"] == "applied"
    assert result.structured_content["applied_count"] == 1
    assert result.structured_content["entries"][0]["status"] == "migrated"
    put_requests = [request for request in requests if request.method == "PUT"]
    assert len(put_requests) == 1
    assert b"createdAt: null" in put_requests[0].content
    assert b"Historical body" in put_requests[0].content


@pytest.mark.asyncio
async def test_apply_aborts_all_writes_when_a_note_changed_since_scan() -> None:
    requests = []
    get_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal get_count
        requests.append(request)
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["Legacy.md"]})
        if request.method == "GET":
            get_count += 1
            text = "# Original\n" if get_count == 1 else "# Edited externally\n"
            return httpx.Response(200, text=text)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            enable_writes=True,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Archive",
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_audit_frontmatter", {"path": "Archive", "apply": True}
            )
    finally:
        await api.aclose()

    assert result.structured_content["apply_status"] == "blocked_conflict"
    assert result.structured_content["conflict_count"] == 1
    assert [request.method for request in requests].count("PUT") == 0
