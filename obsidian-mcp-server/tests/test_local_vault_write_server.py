from pathlib import Path

import pytest
from mcp import Client

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault
from obsidian_mcp_server.server import create_server


@pytest.mark.asyncio
async def test_filesystem_backend_allows_operator_enabled_note_creation(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_ENABLE_WRITES", "true")
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        result = await client.call_tool(
            "obsidian_write_note", {"path": "New.md", "content": "hello", "overwrite": False}
        )
        duplicate = await client.call_tool(
            "obsidian_write_note", {"path": "New.md", "content": "replacement", "overwrite": False}
        )

    assert not result.is_error
    note = (tmp_path / "New.md").read_text(encoding="utf-8")
    assert note.startswith("---\n")
    assert "hello" in note
    assert duplicate.is_error
    assert (tmp_path / "New.md").read_text(encoding="utf-8") == note


@pytest.mark.asyncio
async def test_filesystem_backend_rejects_overwrite_before_reading_target(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Existing.md").write_text("original", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_ENABLE_WRITES", "true")
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        result = await client.call_tool(
            "obsidian_write_note",
            {"path": "Existing.md", "content": "replacement", "overwrite": True},
        )

    assert result.is_error
    assert (tmp_path / "Existing.md").read_text(encoding="utf-8") == "original"


@pytest.mark.asyncio
async def test_filesystem_backend_append_creates_new_note(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_ENABLE_WRITES", "true")
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        result = await client.call_tool(
            "obsidian_append_to_note", {"path": "New.md", "content": "first"}
        )

    assert not result.is_error
    assert "first" in (tmp_path / "New.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_filesystem_backend_append_denies_empty_and_existing_note_without_mutation(
    tmp_path: Path,
):
    original = "original"
    (tmp_path / "Existing.md").write_text(original, encoding="utf-8")
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path, enable_writes=True))

    async with Client(create_server(vault)) as client:
        empty = await client.call_tool("obsidian_append_to_note", {"path": "New.md", "content": ""})
        existing = await client.call_tool(
            "obsidian_append_to_note", {"path": "Existing.md", "content": "extra"}
        )

    assert empty.is_error
    assert existing.is_error
    assert (tmp_path / "Existing.md").read_text(encoding="utf-8") == original
    assert not (tmp_path / "New.md").exists()


@pytest.mark.asyncio
async def test_filesystem_backend_note_write_enforces_prepared_content_limit(tmp_path: Path):
    vault = LocalVault(
        Settings(
            api_url="",
            api_key="",
            vault_path=tmp_path,
            enable_writes=True,
            max_content_bytes=1,
        )
    )

    async with Client(create_server(vault)) as client:
        result = await client.call_tool(
            "obsidian_write_note", {"path": "New.md", "content": "x", "overwrite": False}
        )

    assert result.is_error
    assert not (tmp_path / "New.md").exists()


@pytest.mark.asyncio
async def test_filesystem_backend_daily_note_enforces_prepared_content_limit(tmp_path: Path):
    (tmp_path / "Journal").mkdir()
    vault = LocalVault(
        Settings(
            api_url="",
            api_key="",
            vault_path=tmp_path,
            enable_writes=True,
            daily_note_path_template="Journal/{date}.md",
            max_content_bytes=1,
        )
    )

    async with Client(create_server(vault)) as client:
        result = await client.call_tool(
            "obsidian_write_daily_note", {"note_date": "2026-10-26", "content": "x"}
        )

    assert result.is_error
    assert not (tmp_path / "Journal" / "2026-10-26.md").exists()


@pytest.mark.asyncio
async def test_filesystem_backend_creates_daily_note_but_denies_overwrite(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Journal").mkdir()
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("OBSIDIAN_ENABLE_WRITES", "true")
    monkeypatch.setenv("OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE", "Journal/{date}.md")
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        created = await client.call_tool(
            "obsidian_write_daily_note", {"note_date": "2026-10-26", "content": "daily"}
        )
        duplicate = await client.call_tool(
            "obsidian_write_daily_note", {"note_date": "2026-10-26", "content": "daily"}
        )
        denied = await client.call_tool(
            "obsidian_write_daily_note",
            {"note_date": "2026-10-26", "content": "replacement", "overwrite": True},
        )

    note_path = tmp_path / "Journal" / "2026-10-26.md"
    assert not created.is_error
    assert duplicate.is_error
    assert denied.is_error
    assert "daily" in note_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_filesystem_backend_migration_flag_does_not_enable_general_writes(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Legacy").mkdir()
    (tmp_path / "Legacy" / "old.md").write_text("legacy body", encoding="utf-8")
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_ENABLE_WRITES", raising=False)
    monkeypatch.setenv("OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION", "true")
    monkeypatch.setenv("OBSIDIAN_FRONTMATTER_MIGRATION_ROOT", "Legacy")
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)

    async with Client(create_server()) as client:
        denied = await client.call_tool(
            "obsidian_write_note", {"path": "Other.md", "content": "no"}
        )
        applied = await client.call_tool(
            "obsidian_audit_frontmatter", {"path": "Legacy", "apply": True}
        )

    assert denied.is_error
    assert not (tmp_path / "Other.md").exists()
    assert applied.structured_content["apply_status"] == "applied"
    migrated = (tmp_path / "Legacy" / "old.md").read_text(encoding="utf-8")
    assert "legacy body" in migrated
