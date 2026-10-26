import errno
from pathlib import Path

import pytest

import obsidian_mcp_server.local_vault as local_vault_module
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


def local_settings(root: Path, **overrides) -> Settings:
    return Settings(api_url="", api_key="", vault_path=root, **overrides)


@pytest.mark.asyncio
async def test_local_directory_open_propagates_permission_error(tmp_path: Path, monkeypatch):
    (tmp_path / "child").mkdir()
    vault = LocalVault(local_settings(tmp_path))
    original_open = local_vault_module.os.open

    def denied_open(path, flags, *args, **kwargs):
        if path == "child":
            raise PermissionError("denied")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(local_vault_module.os, "open", denied_open)
    with pytest.raises(PermissionError, match="denied"):
        await vault.list_files("child")


@pytest.mark.asyncio
async def test_local_atomic_write_creates_parentless_target_with_replace_mode(tmp_path: Path):
    vault = LocalVault(local_settings(tmp_path, enable_writes=True))

    await vault.write_note("New.md", "initial")

    assert (tmp_path / "New.md").read_text(encoding="utf-8") == "initial"


@pytest.mark.asyncio
async def test_local_atomic_write_requires_exact_migration_scope(tmp_path: Path):
    (tmp_path / "Legacy").mkdir()
    disabled_migration = LocalVault(local_settings(tmp_path))
    with pytest.raises(PermissionError, match="outside the configured scope"):
        await disabled_migration.write_note("Legacy/old.md", "blocked", frontmatter_migration=True)
    vault = LocalVault(
        local_settings(
            tmp_path,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Legacy",
        )
    )

    with pytest.raises(PermissionError, match="outside the configured scope"):
        await vault.write_note("Other.md", "blocked", frontmatter_migration=True)
    await vault.write_note("Legacy/old.md", "migrated", frontmatter_migration=True)

    assert (tmp_path / "Legacy" / "old.md").read_text(encoding="utf-8") == "migrated"
    assert not (tmp_path / "Other.md").exists()


@pytest.mark.asyncio
async def test_local_atomic_write_retries_temporary_name_collision(tmp_path: Path, monkeypatch):
    vault = LocalVault(local_settings(tmp_path, enable_writes=True))
    (tmp_path / ".Note.md.collision.tmp").write_text("foreign", encoding="utf-8")
    candidates = iter(["collision", "next"])
    monkeypatch.setattr(local_vault_module.secrets, "token_hex", lambda _size: next(candidates))

    await vault.write_note("Note.md", "content", overwrite=False)

    assert (tmp_path / ".Note.md.collision.tmp").read_text(encoding="utf-8") == "foreign"
    assert (tmp_path / "Note.md").read_text(encoding="utf-8") == "content"


@pytest.mark.asyncio
async def test_local_atomic_write_fails_after_temporary_name_collisions(
    tmp_path: Path, monkeypatch
):
    vault = LocalVault(local_settings(tmp_path, enable_writes=True))
    collision = tmp_path / ".Note.md.collision.tmp"
    collision.write_text("foreign", encoding="utf-8")
    monkeypatch.setattr(local_vault_module.secrets, "token_hex", lambda _size: "collision")

    with pytest.raises(RuntimeError, match="allocate a temporary"):
        await vault.write_note("Note.md", "content")

    assert not (tmp_path / "Note.md").exists()
    assert collision.read_text(encoding="utf-8") == "foreign"


@pytest.mark.asyncio
async def test_local_atomic_write_removes_temp_file_when_write_fails(tmp_path: Path, monkeypatch):
    vault = LocalVault(local_settings(tmp_path, enable_writes=True))
    monkeypatch.setattr(local_vault_module.os, "write", lambda *_args: 0)

    with pytest.raises(OSError, match="complete note"):
        await vault.write_note("Note.md", "content", overwrite=False)

    assert not (tmp_path / "Note.md").exists()
    assert list(tmp_path.glob(".Note.md.*.tmp")) == []


@pytest.mark.asyncio
async def test_local_atomic_overwrite_rejects_directory_target_and_cleans_temp(tmp_path: Path):
    (tmp_path / "Legacy").mkdir()
    (tmp_path / "Legacy" / "Note.md").mkdir()
    vault = LocalVault(
        local_settings(
            tmp_path,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Legacy",
        )
    )

    with pytest.raises(ValueError, match="regular file"):
        await vault.write_note(
            "Legacy/Note.md", "content", overwrite=True, frontmatter_migration=True
        )

    assert (tmp_path / "Legacy" / "Note.md").is_dir()
    assert list((tmp_path / "Legacy").glob(".Note.md.*.tmp")) == []


@pytest.mark.asyncio
async def test_local_atomic_overwrite_propagates_target_open_error_and_cleans_temp(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Legacy").mkdir()
    vault = LocalVault(
        local_settings(
            tmp_path,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Legacy",
        )
    )
    original_open = local_vault_module.os.open

    def failing_target_open(path, flags, *args, **kwargs):
        if path == "Note.md":
            raise OSError(errno.EIO, "injected target error")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(local_vault_module.os, "open", failing_target_open)
    with pytest.raises(OSError, match="injected target error"):
        await vault.write_note(
            "Legacy/Note.md", "content", overwrite=True, frontmatter_migration=True
        )

    assert not (tmp_path / "Legacy" / "Note.md").exists()
    assert list((tmp_path / "Legacy").glob(".Note.md.*.tmp")) == []


@pytest.mark.asyncio
async def test_local_atomic_overwrite_cleanup_tolerates_missing_temp(tmp_path: Path, monkeypatch):
    (tmp_path / "Legacy").mkdir()
    vault = LocalVault(
        local_settings(
            tmp_path,
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Legacy",
        )
    )
    original_replace = local_vault_module.os.replace

    def remove_then_fail(source, destination, **kwargs):
        local_vault_module.os.unlink(source, dir_fd=kwargs["src_dir_fd"])
        raise FileNotFoundError("injected disappearance")

    monkeypatch.setattr(local_vault_module.os, "replace", remove_then_fail)
    with pytest.raises(FileNotFoundError, match="injected disappearance"):
        await vault.write_note(
            "Legacy/Note.md", "content", overwrite=True, frontmatter_migration=True
        )
    monkeypatch.setattr(local_vault_module.os, "replace", original_replace)

    assert not (tmp_path / "Legacy" / "Note.md").exists()
