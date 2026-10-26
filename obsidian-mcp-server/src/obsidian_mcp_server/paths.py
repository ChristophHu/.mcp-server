from __future__ import annotations

from pathlib import PurePosixPath


def normalize_vault_path(path: str) -> str:
    """Validate and normalize a vault-relative Obsidian path."""
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("Vault path must be a non-empty relative path")
    if "\\" in path or path.startswith("/"):
        raise ValueError("Vault path must use relative POSIX separators")

    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Vault path contains an invalid path segment")
    if any(part.startswith(".") for part in parts):
        raise ValueError("Hidden vault paths are not accessible")

    normalized = str(PurePosixPath(*parts))
    if normalized != path:
        raise ValueError("Vault path is not canonical")
    return normalized
