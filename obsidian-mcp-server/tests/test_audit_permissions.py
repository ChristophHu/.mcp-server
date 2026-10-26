import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_apply_requires_operator_enabled_exact_migration_scope() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(200, json={"files": []}))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_audit_frontmatter", {"path": "Archive", "apply": True}
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []
