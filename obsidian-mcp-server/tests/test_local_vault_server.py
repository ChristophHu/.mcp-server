from pathlib import Path

import pytest
from mcp import Client

from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_configured_filesystem_backend_exposes_read_tools_and_blocks_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "Note.md").write_text("hello local vault", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        status = await client.call_tool("obsidian_status", {})
        listing = await client.call_tool("obsidian_list_notes", {})
        note = await client.call_tool("obsidian_get_note", {"path": "Note.md"})
        denied = await client.call_tool(
            "obsidian_write_note", {"path": "New.md", "content": "not written"}
        )

    assert status.structured_content["backend"] == "filesystem"
    assert listing.structured_content["entries"] == ["Note.md"]
    assert note.structured_content["content"] == "hello local vault"
    assert denied.is_error
    assert not (tmp_path / "New.md").exists()
