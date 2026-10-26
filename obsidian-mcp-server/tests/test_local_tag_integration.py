from pathlib import Path

import pytest

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


@pytest.mark.asyncio
async def test_local_tag_counts_union_frontmatter_and_body_tags_per_note(tmp_path: Path):
    (tmp_path / "Tagged.md").write_text(
        "---\ntags: [work, shared]\n---\nBody #work and #inline #shared", encoding="utf-8"
    )
    (tmp_path / "Other.md").write_text("#shared", encoding="utf-8")
    vault = LocalVault(Settings(api_url="", api_key="", vault_path=tmp_path))

    assert await vault.list_tags() == [
        {"name": "inline", "count": 1},
        {"name": "shared", "count": 2},
        {"name": "work", "count": 1},
    ]
