import pytest

from obsidian_mcp_server.paths import normalize_vault_path


@pytest.mark.parametrize("path", [None, "", "folder\x00note.md"])
def test_rejects_missing_or_nul_paths(path):
    with pytest.raises(ValueError, match="non-empty relative path"):
        normalize_vault_path(path)


def test_rejects_noncanonical_subclass_representation():
    class NonCanonicalPath(str):
        def __ne__(self, other):
            return True

    with pytest.raises(ValueError, match="not canonical"):
        normalize_vault_path(NonCanonicalPath("Note.md"))
