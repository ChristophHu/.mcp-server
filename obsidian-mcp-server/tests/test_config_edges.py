import pytest

from obsidian_mcp_server.config import Settings


@pytest.mark.parametrize("raw", ["not-a-url", "ftp://host", "https://"])
def test_settings_reject_non_absolute_http_urls(raw):
    with pytest.raises(ValueError, match="absolute HTTP"):
        Settings.from_env({"OBSIDIAN_API_URL": raw})


@pytest.mark.parametrize("raw", ["https://host/path?q=1", "https://host/path#fragment"])
def test_settings_reject_url_query_and_fragment(raw):
    with pytest.raises(ValueError, match="query or fragment"):
        Settings.from_env({"OBSIDIAN_API_URL": raw})


def test_settings_require_migration_root_when_migration_is_enabled():
    with pytest.raises(ValueError, match="MIGRATION_ROOT is required"):
        Settings.from_env({"OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "on"})


def test_settings_normalize_migration_root_and_trim_url():
    settings = Settings.from_env(
        {
            "OBSIDIAN_API_URL": "  https://host/base///  ",
            "OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION": "yes",
            "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT": " Archive/Notes ",
        }
    )
    assert settings.api_url == "https://host/base"
    assert settings.enable_frontmatter_migration is True
    assert settings.frontmatter_migration_root == "Archive/Notes"


@pytest.mark.parametrize("raw", ["maybe", "", "enabled"])
def test_settings_reject_invalid_boolean_values(raw):
    with pytest.raises(ValueError, match="Boolean environment"):
        Settings.from_env({"OBSIDIAN_ENABLE_WRITES": raw})
