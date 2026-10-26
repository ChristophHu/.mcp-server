import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_frontmatter_audit_dry_run_scans_notes_without_writing() -> None:
    requests = []
    compliant = (
        "---\ntitle: Ready\ntags: []\ncreatedAt: '2025-01-01T00:00:00Z'\n"
        "updatedAt: '2025-01-02T00:00:00Z'\nstatus: active\n---\nReady body\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/vault/":
            return httpx.Response(
                200, json={"files": ["Old.md", "Ready.md", ".obsidian/", "Nested/"]}
            )
        if request.url.path == "/vault/Nested/":
            return httpx.Response(200, json={"files": ["Broken.md", ".hidden/"]})
        if request.url.path.endswith("/Ready.md"):
            return httpx.Response(200, text=compliant)
        if request.url.path.endswith("/Broken.md"):
            return httpx.Response(200, text="---\ntitle: [bad\n---\nBody\n")
        return httpx.Response(200, text="# Old\nBody\n")

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(handler),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool("obsidian_audit_frontmatter", {})
    finally:
        await api.aclose()

    assert result.structured_content["mode"] == "dry_run"
    assert result.structured_content["complete"] is True
    assert result.structured_content["scanned_count"] == 3
    assert result.structured_content["compliant_count"] == 1
    assert result.structured_content["needs_update_count"] == 1
    assert result.structured_content["needs_review_count"] == 1
    legacy = next(
        entry for entry in result.structured_content["entries"] if entry["path"] == "Old.md"
    )
    assert legacy["proposed_fields"]["title"] == "Old"
    assert legacy["proposed_fields"]["tags"] == []
    assert legacy["proposed_fields"]["createdAt"] is None
    assert legacy["proposed_fields"]["status"] == "active"
    assert legacy["created_at_unknown"] is True
    assert "Body" not in repr(result.structured_content)
    assert {request.method for request in requests} == {"GET"}
    assert all(
        ".obsidian" not in request.url.path and ".hidden" not in request.url.path
        for request in requests
    )
