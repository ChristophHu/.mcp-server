import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "obsidian_get_note",
    "obsidian_status",
    "obsidian_list_notes",
    "obsidian_search_notes",
    "obsidian_write_note",
    "obsidian_append_to_note",
    "obsidian_get_daily_note",
    "obsidian_write_daily_note",
    "obsidian_list_tags",
    "obsidian_manage_frontmatter",
    "obsidian_manage_tags",
    "obsidian_open_in_ui",
    "obsidian_get_note_links",
    "obsidian_check_consistency",
    "obsidian_check_file_consistency",
    "obsidian_audit_frontmatter",
}


@pytest.mark.asyncio
async def test_real_stdio_process_lists_all_registered_tools() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "obsidian_mcp_server.server"],
        cwd=PROJECT_ROOT,
        env={
            "OBSIDIAN_API_URL": "http://127.0.0.1:1",
            "OBSIDIAN_API_KEY": "test-only",
        },
    )
    async with Client(params) as client:
        result = await client.list_tools()

    assert {tool.name for tool in result.tools} == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_real_stdio_process_reads_note_and_resource_from_temp_vault(tmp_path: Path) -> None:
    (tmp_path / "Note.md").write_text("isolated stdio note", encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "obsidian_mcp_server.server"],
        cwd=PROJECT_ROOT,
        env={"OBSIDIAN_VAULT_PATH": str(tmp_path)},
    )

    async with Client(params) as client:
        note = await client.call_tool("obsidian_get_note", {"path": "Note.md"})
        resource = await client.read_resource("obsidian://vault/Note.md")

    assert note.structured_content["content"] == "isolated stdio note"
    assert getattr(resource.contents[0], "text", None) == "isolated stdio note"
