from datetime import date

import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


@pytest.mark.asyncio
async def test_periodic_daily_note_uses_date_segments() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="Daily content")

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await api.get_periodic_note("daily", date(2026, 10, 26))
    finally:
        await api.aclose()

    assert result == "Daily content"
    assert requests[0].url.path == "/periodic/daily/2026/10/26/"


@pytest.mark.asyncio
async def test_open_in_ui_uses_documented_new_leaf_parameter() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    try:
        await api.open_in_ui("Notes/Some Note.md", new_pane=True)
    finally:
        await api.aclose()

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/open/Notes/Some Note.md"
    assert dict(requests[0].url.params) == {"newLeaf": "true"}


@pytest.mark.asyncio
async def test_list_tags_returns_plugin_tag_entries() -> None:
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"tags": [{"name": "work", "count": 2}]})
        ),
    )
    try:
        result = await api.list_tags()
    finally:
        await api.aclose()

    assert result == [{"name": "work", "count": 2}]


@pytest.mark.asyncio
async def test_jsonlogic_search_uses_local_rest_api_vendor_media_type() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"filename": "Target.md", "result": {"links": []}}])

    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )
    tree = {"==": [{"var": "path"}, "Target.md"]}
    try:
        result = await api.search_jsonlogic(tree)
    finally:
        await api.aclose()

    assert result == [{"filename": "Target.md", "result": {"links": []}}]
    assert requests[0].headers["Content-Type"] == "application/vnd.olrapi.jsonlogic+json"


@pytest.mark.asyncio
async def test_append_periodic_note_fails_closed_when_writes_are_disabled() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError, match="Writes are disabled"):
            await api.append_periodic_note("daily", date(2026, 10, 26), "content")
    finally:
        await api.aclose()

    assert requests == []


@pytest.mark.asyncio
async def test_append_periodic_note_requires_conditional_create_support() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError, match="conditional no-clobber"):
            await api.append_periodic_note("daily", date(2026, 10, 26), "content")
    finally:
        await api.aclose()

    assert requests == []


@pytest.mark.asyncio
async def test_replace_periodic_note_requires_target_bound_approval() -> None:
    requests = []
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key", enable_writes=True),
        transport=httpx.MockTransport(
            lambda request: (requests.append(request), httpx.Response(204))[1]
        ),
    )
    try:
        with pytest.raises(PermissionError, match="target-bound approval"):
            await api.replace_periodic_note("daily", date(2026, 10, 26), "content")
    finally:
        await api.aclose()

    assert requests == []
