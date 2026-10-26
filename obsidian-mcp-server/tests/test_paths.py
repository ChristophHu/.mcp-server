import pytest

from obsidian_mcp_server.paths import normalize_vault_path


@pytest.mark.parametrize(
    "path", ["../secret.md", "/etc/passwd", "folder/../../secret.md", "folder\\note.md"]
)
def test_rejects_paths_that_escape_or_are_not_vault_relative(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_vault_path(path)


def test_normalizes_safe_relative_paths() -> None:
    assert normalize_vault_path("Projects/idea.md") == "Projects/idea.md"


def test_rejects_hidden_obsidian_configuration_paths() -> None:
    with pytest.raises(ValueError):
        normalize_vault_path(".obsidian/plugins/example/data.json")
