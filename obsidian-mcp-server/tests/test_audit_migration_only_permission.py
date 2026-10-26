import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_scoped_migration_does_not_enable_general_write_tools() -> None:
    stored = {"Archive/Legacy.md": "# Legacy\n"}
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["Legacy.md"]})
        path = request.url.path.removeprefix("/vault/")
        if request.method == "GET":
            return httpx.Response(200, text=stored[path])
        stored[path] = request.content.decode()
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            enable_writes=False,
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
            general_write = await client.call_tool(
                "obsidian_write_note", {"path": "General.md", "content": "not allowed"}
            )
    finally:
        await api.aclose()

    assert result.is_error is False
    assert result.structured_content["apply_status"] == "applied"
    assert general_write.is_error is True
    assert len([request for request in requests if request.method == "PUT"]) == 1
