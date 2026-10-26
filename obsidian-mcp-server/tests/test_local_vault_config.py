from pathlib import Path

import pytest

from obsidian_mcp_server.config import Settings


def test_local_backend_reads_operator_write_and_migration_flags(tmp_path: Path):
    settings = Settings.from_env(
        {
            "OBSIDIAN_VAULT_PATH": str(tmp_path),
            "OBSIDIAN_ENABLE_WRITES": "true",
            "OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "true",
            "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT": "Notes/Legacy",
            "OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE": "Journal/{date}.md",
        }
    )

    assert settings.enable_writes is True
    assert settings.enable_frontmatter_migration is True
    assert settings.frontmatter_migration_root == "Notes/Legacy"
    assert settings.daily_note_path_template == "Journal/{date}.md"
    assert settings.api_key == ""


def test_local_migration_configuration_requires_operator_scope(tmp_path: Path):
    with pytest.raises(ValueError, match="ROOT is required"):
        Settings.from_env(
            {
                "OBSIDIAN_VAULT_PATH": str(tmp_path),
                "OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "true",
            }
        )


@pytest.mark.parametrize(
    "template",
    ["Daily.md", "../Daily/{date}.md", "Daily/{date}.txt"],
)
def test_local_daily_note_template_is_validated(tmp_path: Path, template: str):
    with pytest.raises(ValueError):
        Settings.from_env(
            {
                "OBSIDIAN_VAULT_PATH": str(tmp_path),
                "OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE": template,
            }
        )
