from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.paths import normalize_vault_path


class ObsidianApi:
    """Small async client for the Obsidian Local REST API plugin."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.api_url,
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
            transport=transport,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "User-Agent": "obsidian-mcp-server/0.1.0",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def settings(self) -> Settings:
        return self._settings

    def _note_url(self, path: str, *, directory: bool = False) -> str:
        safe_path = normalize_vault_path(path)
        encoded = quote(safe_path, safe="/")
        suffix = "/" if directory else ""
        return f"/vault/{encoded}{suffix}"

    @staticmethod
    def _periodic_url(period: str, note_date: date) -> str:
        if period not in {"daily", "weekly", "monthly", "quarterly", "yearly"}:
            raise ValueError("Unsupported periodic note type")
        return f"/periodic/{period}/{note_date.year}/{note_date.month}/{note_date.day}/"

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if not self._settings.api_key:
            raise RuntimeError("OBSIDIAN_API_KEY is required")
        headers = dict(kwargs.pop("headers", {}))
        headers["Accept-Encoding"] = "identity"
        kwargs["headers"] = headers
        try:
            async with self._client.stream(method, url, **kwargs) as response:
                self._raise_response_error(response)
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise RuntimeError("Compressed API responses are not supported")
                body = await self._read_limited_body(
                    response,
                    "Obsidian Local REST API response exceeds the configured content limit",
                )
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=bytes(body),
                    request=response.request,
                )
        except httpx.TimeoutException as exc:
            raise RuntimeError("Obsidian Local REST API request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Obsidian Local REST API request failed") from exc

    @staticmethod
    def _raise_response_error(response: httpx.Response) -> None:
        if response.is_error:
            status = response.status_code
            if status == 401:
                raise RuntimeError("Obsidian Local REST API rejected the API key (HTTP 401)")
            if status == 404:
                raise FileNotFoundError("Obsidian resource was not found (HTTP 404)")
            raise RuntimeError(f"Obsidian Local REST API returned HTTP {status}")

    async def _read_limited_body(self, response: httpx.Response, message: str) -> bytes:
        if response.is_stream_consumed:
            body = response.content
            if len(body) > self._settings.max_content_bytes:
                raise ValueError(message)
            return body

        body = bytearray()
        async for chunk in response.aiter_raw():
            if len(body) + len(chunk) > self._settings.max_content_bytes:
                raise ValueError(message)
            body.extend(chunk)
        return bytes(body)

    async def _get_limited_text(self, url: str, *, accept: str) -> str:
        if not self._settings.api_key:
            raise RuntimeError("OBSIDIAN_API_KEY is required")
        try:
            async with self._client.stream(
                "GET", url, headers={"Accept": accept, "Accept-Encoding": "identity"}
            ) as response:
                self._raise_response_error(response)
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise RuntimeError("Compressed API responses are not supported")
                body = await self._read_limited_body(
                    response, "Note exceeds the configured content limit"
                )
                encoding = response.encoding or "utf-8"
                try:
                    return body.decode(encoding)
                except (LookupError, UnicodeDecodeError) as exc:
                    raise RuntimeError(
                        "Obsidian note is not valid text in its declared encoding"
                    ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("Obsidian Local REST API request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Obsidian Local REST API request failed") from exc

    async def get_status(self) -> Mapping[str, object]:
        response = await self._request("GET", "/")
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("Obsidian Local REST API returned an invalid status response")
        return value

    async def get_note(self, path: str) -> str:
        return await self._get_limited_text(self._note_url(path), accept="text/markdown")

    async def get_periodic_note(self, period: str, note_date: date) -> str:
        return await self._get_limited_text(
            self._periodic_url(period, note_date),
            accept="text/markdown",
        )

    async def append_periodic_note(self, period: str, note_date: date, content: str) -> None:
        if not self._settings.enable_writes:
            raise PermissionError("Writes are disabled; set OBSIDIAN_ENABLE_WRITES=true")
        raise PermissionError(
            "REST daily-note creation is disabled until conditional no-clobber behavior is verified"
        )

    async def replace_periodic_note(self, period: str, note_date: date, content: str) -> None:
        if not self._settings.enable_writes:
            raise PermissionError("Writes are disabled; set OBSIDIAN_ENABLE_WRITES=true")
        raise PermissionError(
            "Replacing daily notes requires trusted target-bound approval; no approval "
            "provider is configured"
        )

    async def get_note_json(self, path: str) -> Mapping[str, object]:
        response = await self._request(
            "GET",
            self._note_url(path),
            headers={"Accept": "application/vnd.olrapi.note+json"},
        )
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("Obsidian Local REST API returned invalid note metadata")
        return value

    async def list_files(self, path: str | None = None) -> list[str]:
        url = "/vault/" if path is None else self._note_url(path, directory=True)
        response = await self._request("GET", url)
        payload = response.json()
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise RuntimeError("Obsidian Local REST API returned an invalid file listing")
        return files

    async def list_tags(self) -> list[object]:
        response = await self._request("GET", "/tags/")
        payload = response.json()
        tags = payload.get("tags") if isinstance(payload, dict) else None
        if not isinstance(tags, list):
            raise RuntimeError("Obsidian Local REST API returned an invalid tag listing")
        return tags

    async def search_notes(self, query: str, *, context_length: int = 80) -> list[object]:
        response = await self._request(
            "POST",
            "/search/simple/",
            params={"query": query, "contextLength": str(context_length)},
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Obsidian Local REST API returned an invalid search response")
        return payload

    async def search_jsonlogic(self, tree: Mapping[str, object]) -> list[object]:
        response = await self._request(
            "POST",
            "/search/",
            json=dict(tree),
            headers={"Content-Type": "application/vnd.olrapi.jsonlogic+json"},
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(
                "Obsidian Local REST API returned an invalid structured search response"
            )
        return payload

    async def write_note(
        self,
        path: str,
        content: str,
        *,
        append: bool = False,
        frontmatter_migration: bool = False,
    ) -> None:
        if frontmatter_migration:
            root = self._settings.frontmatter_migration_root
            migration_allowed = self._settings.enable_frontmatter_migration and root is not None
            if migration_allowed and root is not None:
                safe_path = normalize_vault_path(path)
                safe_root = normalize_vault_path(root)
                migration_allowed = safe_path == safe_root or safe_path.startswith(f"{safe_root}/")
            if not migration_allowed:
                raise PermissionError("Migration writes are outside the configured scope")
        else:
            if not self._settings.enable_writes:
                raise PermissionError("Writes are disabled; set OBSIDIAN_ENABLE_WRITES=true")
            raise PermissionError(
                "REST writes are disabled until conditional no-clobber behavior is verified"
            )
        if append:
            raise PermissionError("REST append writes are not supported in the migration path")
        if len(content.encode("utf-8")) > self._settings.max_content_bytes:
            raise ValueError("Note content exceeds the configured content limit")
        await self._request(
            "PUT",
            self._note_url(path),
            content=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )

    async def open_in_ui(self, path: str, *, new_pane: bool = False) -> None:
        safe_path = normalize_vault_path(path)
        await self._request(
            "POST",
            f"/open/{quote(safe_path, safe='/')}",
            params={"newLeaf": "true"} if new_pane else None,
        )
