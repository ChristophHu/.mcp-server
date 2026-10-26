import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_apply_is_idempotent_after_first_successful_migration() -> None:
    stored = {"Archive/Legacy.md": "# Legacy\n"}
    put_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal put_count
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["Legacy.md"]})
        path = request.url.path.removeprefix("/vault/")
        if request.method == "GET":
            return httpx.Response(200, text=stored[path])
        put_count += 1
        stored[path] = request.content.decode()
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
            first = await client.call_tool(
                "obsidian_audit_frontmatter", {"path": "Archive", "apply": True}
            )
            second = await client.call_tool(
                "obsidian_audit_frontmatter", {"path": "Archive", "apply": True}
            )
    finally:
        await api.aclose()

    assert first.structured_content["apply_status"] == "applied"
    assert second.structured_content["apply_status"] == "no_changes"
    assert second.structured_content["compliant_count"] == 1
    assert put_count == 1


@pytest.mark.asyncio
async def test_apply_reports_partial_failure_if_a_later_remote_write_fails() -> None:
    requests = []
    original = "# Legacy\n"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["A.md", "B.md"]})
        if request.method == "GET":
            return httpx.Response(200, text=original)
        if request.url.path.endswith("/B.md"):
            return httpx.Response(503)
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

    assert result.structured_content["apply_status"] == "partial_failure"
    assert result.structured_content["applied_count"] == 1
    assert result.structured_content["entries"][0]["status"] == "migrated"
    assert result.structured_content["entries"][1]["status"] == "write_failed"
    assert [request.method for request in requests].count("PUT") == 2
