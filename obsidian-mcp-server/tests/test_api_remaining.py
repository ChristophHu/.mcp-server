import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


def api_with(handler, *, writes=False, limit=100):
    return ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test",
            enable_writes=writes,
            max_content_bytes=limit,
        ),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_get_note_json_rejects_response_over_byte_limit():
    api = api_with(lambda request: httpx.Response(200, json={"long": "body"}), limit=2)
    try:
        with pytest.raises(ValueError, match="content limit"):
            await api.get_note_json("Note.md")
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_search_notes_returns_valid_hit_list():
    hits = [{"filename": "Note.md", "matches": []}]
    api = api_with(lambda request: httpx.Response(200, json=hits))
    try:
        assert await api.search_notes("term", context_length=120) == hits
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_search_notes_rejects_non_list_response():
    api = api_with(lambda request: httpx.Response(200, json={"hits": []}))
    try:
        with pytest.raises(RuntimeError, match="invalid search response"):
            await api.search_notes("term")
    finally:
        await api.aclose()
