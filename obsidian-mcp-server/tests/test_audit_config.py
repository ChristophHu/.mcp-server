from obsidian_mcp_server.config import Settings


def test_frontmatter_migration_requires_a_separate_flag_and_exact_root() -> None:
    settings = Settings.from_env(
        {
            "OBSIDIAN_ENABLE_WRITES": "true",
            "OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "true",
            "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT": "Archive/2026",
        }
    )

    assert settings.enable_frontmatter_migration is True
    assert settings.frontmatter_migration_root == "Archive/2026"


def test_frontmatter_migration_is_disabled_by_default() -> None:
    settings = Settings.from_env({})

    assert settings.enable_frontmatter_migration is False
    assert settings.frontmatter_migration_root is None


def test_frontmatter_migration_rejects_hidden_configured_root() -> None:
    try:
        Settings.from_env(
            {
                "OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "true",
                "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT": ".obsidian",
            }
        )
    except ValueError as exc:
        assert "vault path" in str(exc)
    else:
        raise AssertionError("hidden migration root must be rejected")
