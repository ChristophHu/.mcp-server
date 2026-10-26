from datetime import date

import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


@pytest.mark.asyncio
async def test_replace_periodic_note_fails_closed_when_writes_are_disabled() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError, match="Writes are disabled"):
            await api.replace_periodic_note("daily", date(2026, 10, 26), "content")
    finally:
        await api.aclose()

    assert requests == []
