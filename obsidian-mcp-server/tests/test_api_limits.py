import httpx
import pytest

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.yielded = 0

    async def __aiter__(self):
        for chunk in (b"abcd", b"e", b"never read"):
            self.yielded += 1
            yield chunk

    async def aclose(self) -> None:
        pass


class JsonChunkStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.yielded = 0

    async def __aiter__(self):
        for chunk in (b'{"ok', b'":true}', b'"ignored":true}'):
            self.yielded += 1
            yield chunk

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_oversized_note_stops_reading_stream_when_limit_is_crossed() -> None:
    stream = ChunkStream()
    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            max_content_bytes=4,
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)),
    )
    try:
        with pytest.raises(ValueError, match="content limit"):
            await api.get_note("Large.md")
    finally:
        await api.aclose()

    assert stream.yielded == 2


@pytest.mark.asyncio
async def test_oversized_json_response_stops_reading_stream_when_limit_is_crossed() -> None:
    stream = JsonChunkStream()
    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            max_content_bytes=4,
        ),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)),
    )
    try:
        with pytest.raises(ValueError, match="response exceeds.*limit"):
            await api.get_status()
    finally:
        await api.aclose()

    assert stream.yielded == 2


@pytest.mark.asyncio
async def test_json_request_disables_and_rejects_compressed_responses() -> None:
    requests = []
    stream = JsonChunkStream()
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: (
                requests.append(request),
                httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream),
            )[1]
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="Compressed API responses"):
            await api.get_status()
    finally:
        await api.aclose()

    assert requests[0].headers["accept-encoding"] == "identity"
    assert stream.yielded == 0


class ExactLimitJsonStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"{"
        yield b"}"

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_json_response_exactly_at_limit_is_accepted() -> None:
    api = ObsidianApi(
        Settings(
            api_url="https://obsidian.local",
            api_key="test-key",
            max_content_bytes=2,
        ),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=ExactLimitJsonStream())
        ),
    )
    try:
        assert await api.get_status() == {}
    finally:
        await api.aclose()


@pytest.mark.asyncio
async def test_note_request_rejects_compressed_response_without_reading_body() -> None:
    stream = JsonChunkStream()
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream)
        ),
    )
    try:
        with pytest.raises(RuntimeError, match="Compressed API responses"):
            await api.get_note("Note.md")
    finally:
        await api.aclose()

    assert stream.yielded == 0
