import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


@pytest.mark.asyncio
async def test_migration_write_is_rejected_outside_root_when_writes_are_enabled() -> None:
    requests = []
    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            enable_writes=True,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Archive",
        ),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError):
            await api.write_note("Elsewhere/Note.md", "content", frontmatter_migration=True)
    finally:
        await api.aclose()

    assert requests == []


@pytest.mark.asyncio
async def test_rest_note_write_requires_conditional_create_support() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError, match="conditional no-clobber"):
            await api.write_note("New.md", "content")
    finally:
        await api.aclose()

    assert requests == []
