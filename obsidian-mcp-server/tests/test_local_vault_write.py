from pathlib import Path

import pytest

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


def local_settings(root: Path, *, enable_writes: bool = False, max_content_bytes: int = 1_048_576):
    return Settings(
        api_url="",
        api_key="",
        vault_path=root,
        enable_writes=enable_writes,
        max_content_bytes=max_content_bytes,
    )


@pytest.mark.asyncio
async def test_local_vault_creates_without_clobbering_and_rejects_unapproved_overwrite(
    tmp_path: Path,
):
    (tmp_path / "Folder").mkdir()
    vault = LocalVault(local_settings(tmp_path, enable_writes=True))

    await vault.write_note("Folder/New.md", "initial", overwrite=False)
    assert (tmp_path / "Folder" / "New.md").read_text(encoding="utf-8") == "initial"

    with pytest.raises(FileExistsError):
        await vault.write_note("Folder/New.md", "rejected", overwrite=False)
    assert (tmp_path / "Folder" / "New.md").read_text(encoding="utf-8") == "initial"

    with pytest.raises(PermissionError, match="target-bound approval"):
        await vault.write_note("Folder/New.md", "replacement", overwrite=True)
    assert (tmp_path / "Folder" / "New.md").read_text(encoding="utf-8") == "initial"


@pytest.mark.asyncio
async def test_local_vault_write_requires_operator_flag_and_respects_byte_limit(tmp_path: Path):
    disabled = LocalVault(local_settings(tmp_path))
    with pytest.raises(PermissionError, match="read-only"):
        await disabled.write_note("New.md", "content")
    assert not (tmp_path / "New.md").exists()

    limited = LocalVault(local_settings(tmp_path, enable_writes=True, max_content_bytes=3))
    with pytest.raises(ValueError, match="content limit"):
        await limited.write_note("Large.md", "four")
    assert not (tmp_path / "Large.md").exists()


@pytest.mark.asyncio
async def test_local_vault_write_refuses_symlink_targets_without_touching_target(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("keep", encoding="utf-8")
    (tmp_path / "Legacy").mkdir()
    (tmp_path / "Legacy" / "linked.md").symlink_to(outside)
    vault = LocalVault(
        Settings(
            api_url="",
            api_key="",
            vault_path=tmp_path,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Legacy",
        )
    )

    with pytest.raises(PermissionError, match="Symbolic links"):
        await vault.write_note(
            "Legacy/linked.md", "replace", overwrite=True, frontmatter_migration=True
        )
    assert outside.read_text(encoding="utf-8") == "keep"


@pytest.mark.asyncio
async def test_local_vault_status_reports_operator_write_mode(tmp_path: Path):
    readonly = LocalVault(local_settings(tmp_path))
    writable = LocalVault(local_settings(tmp_path, enable_writes=True))

    assert (await readonly.get_status())["read_only"] is True
    assert (await writable.get_status())["read_only"] is False
