import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


def _migration_settings() -> Settings:
    return Settings(
        api_url="https://obsidian.local",
        api_key="test-key",
        enable_writes=True,
        enable_frontmatter_migration=True,
        frontmatter_migration_root="Archive",
    )


@pytest.mark.asyncio
async def test_apply_rejects_a_path_outside_the_operator_configured_scope() -> None:
    requests = []
    api = ObsidianApi(
        _migration_settings(),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(200, json={"files": []}))[1]
        ),
    )
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_audit_frontmatter",
                {"path": "Archive/Other", "apply": True},
            )
    finally:
        await api.aclose()

    assert result.is_error is True
    assert requests == []


@pytest.mark.asyncio
async def test_apply_is_blocked_when_scan_exceeds_file_limit() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/vault/Archive/":
            return httpx.Response(200, json={"files": ["First.md", "Second.md"]})
        return httpx.Response(200, text="# Legacy\n")

    api = ObsidianApi(_migration_settings(), transport=httpx.MockTransport(handler))
    try:
        async with Client(create_server(api)) as client:
            result = await client.call_tool(
                "obsidian_audit_frontmatter",
                {"path": "Archive", "apply": True, "max_files": 1},
            )
    finally:
        await api.aclose()

    assert result.structured_content["complete"] is False
    assert result.structured_content["truncated"] is True
    assert result.structured_content["apply_status"] == "blocked_incomplete_scan"
    assert result.structured_content["applied_count"] == 0
    assert all(request.method == "GET" for request in requests)
