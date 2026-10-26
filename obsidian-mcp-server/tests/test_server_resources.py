from pathlib import Path

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError

from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_filesystem_server_exposes_note_tag_and_status_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "Note.md").write_text("resource body", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)

    async with Client(create_server()) as client:
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        note = await client.read_resource("obsidian://vault/Note.md")
        tags = await client.read_resource("obsidian://tags")
        status = await client.read_resource("obsidian://status")

    assert {resource.uri for resource in resources.resources} == {
        "obsidian://tags",
        "obsidian://status",
    }
    assert len(templates.resource_templates) == 1
    assert templates.resource_templates[0].uri_template == "obsidian://vault/{+path}"
    assert getattr(note.contents[0], "text", None) == "resource body"
    assert getattr(tags.contents[0], "text", None) == "[]"
    assert '"backend": "filesystem"' in getattr(status.contents[0], "text", "")


@pytest.mark.asyncio
async def test_vault_note_resource_rejects_hidden_and_traversal_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)

    async with Client(create_server()) as client:
        with pytest.raises(MCPError):
            await client.read_resource("obsidian://vault/.obsidian/config.md")
        with pytest.raises(MCPError):
            await client.read_resource("obsidian://vault/%2e%2e/outside.md")
