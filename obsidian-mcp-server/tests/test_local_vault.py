from pathlib import Path

import pytest

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


def test_settings_select_local_vault_without_rest_credentials(tmp_path: Path):
    settings = Settings.from_env({"OBSIDIAN_VAULT_PATH": str(tmp_path)})
    assert settings.backend == "filesystem"
    assert settings.vault_path == tmp_path.resolve()
    assert settings.api_key == ""


@pytest.mark.asyncio
async def test_local_vault_lists_and_reads_visible_markdown_without_following_symlinks(
    tmp_path: Path,
):
    (tmp_path / "Note.md").write_text("safe", encoding="utf-8")
    (tmp_path / ".hidden.md").write_text("secret", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config.md").write_text("private", encoding="utf-8")
    (tmp_path / "Folder").mkdir()
    (tmp_path / "Folder" / "Child.md").write_text("child", encoding="utf-8")
    (tmp_path / "linked.md").symlink_to(tmp_path / "Note.md")

    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path))
    assert await vault.list_files(None) == ["Folder/", "Note.md"]
    assert await vault.list_files("Folder") == ["Child.md"]
    assert await vault.get_note("Note.md") == "safe"
    with pytest.raises(PermissionError, match="Symbolic links"):
        await vault.get_note("linked.md")


@pytest.mark.asyncio
async def test_local_vault_rejects_traversal_and_oversized_note(tmp_path: Path):
    (tmp_path / "large.md").write_text("12345", encoding="utf-8")
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path, max_content_bytes=4))

    with pytest.raises(ValueError, match="invalid path"):
        await vault.get_note("../outside.md")
    with pytest.raises(ValueError, match="content limit"):
        await vault.get_note("large.md")


@pytest.mark.asyncio
async def test_local_vault_searches_markdown_and_counts_frontmatter_tags(tmp_path: Path):
    (tmp_path / "A.md").write_text("---\ntags: [work, work]\n---\nKiwi note", encoding="utf-8")
    (tmp_path / "B.md").write_text("Mango", encoding="utf-8")
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path))

    assert await vault.search_notes("kiwi") == [
        {
            "filename": "A.md",
            "matches": ["---\ntags: [work, work]\n---\nKiwi note"],
        }
    ]
    assert await vault.list_tags() == [{"name": "work", "count": 1}]
    assert (await vault.get_note_json("A.md"))["path"] == "A.md"


@pytest.mark.asyncio
async def test_local_vault_rejects_mutations_in_read_only_mode(tmp_path: Path):
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path))
    with pytest.raises(PermissionError, match="read-only"):
        await vault.write_note("new.md", "text")
