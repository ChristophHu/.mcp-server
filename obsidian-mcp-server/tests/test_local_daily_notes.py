from datetime import date
from pathlib import Path

import pytest

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


@pytest.mark.asyncio
async def test_local_daily_note_creates_but_rejects_unapproved_overwrite(tmp_path: Path):
    (tmp_path / "Journal").mkdir()
    settings = Settings(
        api_url="",
        api_key="",
        vault_path=tmp_path,
        enable_writes=True,
        daily_note_path_template="Journal/{date}.md",
    )
    vault = LocalVault(settings)
    note_date = date(2026, 10, 26)

    await vault.append_periodic_note("daily", note_date, "daily content")
    assert await vault.get_periodic_note("daily", note_date) == "daily content"

    with pytest.raises(PermissionError, match="target-bound approval"):
        await vault.replace_periodic_note("daily", note_date, "replaced")
    assert await vault.get_periodic_note("daily", note_date) == "daily content"
    assert (tmp_path / "Journal" / "2026-10-26.md").read_text(encoding="utf-8") == "daily content"


@pytest.mark.asyncio
async def test_local_daily_note_fails_closed_without_path_template(tmp_path: Path):
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path))

    with pytest.raises(RuntimeError, match="path template"):
        await vault.get_periodic_note("daily", date(2026, 10, 26))


@pytest.mark.asyncio
async def test_local_daily_note_rejects_unsupported_period_and_disabled_writes(tmp_path: Path):
    settings = Settings(
        api_url="",
        api_key="",
        vault_path=tmp_path,
        daily_note_path_template="Journal/{date}.md",
    )
    vault = LocalVault(settings)

    with pytest.raises(ValueError, match="daily"):
        await vault.get_periodic_note("weekly", date(2026, 10, 26))
    with pytest.raises(PermissionError, match="read-only"):
        await vault.append_periodic_note("daily", date(2026, 10, 26), "content")
    assert not (tmp_path / "Journal").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("template", ["Journal/{date}.txt", "Journal/{date}/{date}.md"])
async def test_local_daily_note_rejects_invalid_direct_settings(tmp_path: Path, template: str):
    vault = LocalVault(
        Settings(
            api_url="",
            api_key="",
            vault_path=tmp_path,
            daily_note_path_template=template,
        )
    )
    with pytest.raises(ValueError, match="template"):
        await vault.get_periodic_note("daily", date(2026, 10, 26))
