from pathlib import Path

import httpx
import pytest
from mcp import Client

from obsidian_mcp_server.api import ObsidianApi
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault
from obsidian_mcp_server.server import create_server


def make_vault(root: Path, **settings_overrides) -> LocalVault:
    return LocalVault(Settings(api_url="", api_key="", vault_path=root, **settings_overrides))


@pytest.mark.asyncio
async def test_consistency_scan_reports_broken_links_and_notes_without_outgoing_links(
    tmp_path: Path,
):
    (tmp_path / "Home.md").write_text(
        "[[Present]] [[Absent]] `[[CodeOnly]]`\n```md\n[[FenceOnly]]\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "Present.md").write_text("No outgoing links", encoding="utf-8")
    (tmp_path / "Orphan.md").write_text("Also no outgoing links", encoding="utf-8")
    (tmp_path / "Readme.txt").write_text("not a Markdown note", encoding="utf-8")
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    async with Client(create_server(make_vault(tmp_path))) as client:
        result = await client.call_tool("obsidian_check_consistency", {})

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert after == before
    assert result.structured_content == {
        "complete": True,
        "truncated": False,
        "link_targets_complete": True,
        "scanned_count": 3,
        "links_checked": 2,
        "broken_links": [{"source": "Home.md", "target": "Absent"}],
        "notes_without_outgoing_links": ["Orphan.md", "Present.md"],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_consistency_scan_marks_truncated_results_incomplete(tmp_path: Path):
    (tmp_path / "A.md").write_text("[[B]]", encoding="utf-8")
    (tmp_path / "B.md").write_text("present but outside scan", encoding="utf-8")

    async with Client(create_server(make_vault(tmp_path, max_limit=1))) as client:
        result = await client.call_tool("obsidian_check_consistency", {"limit": 1})

    assert result.structured_content["complete"] is False
    assert result.structured_content["truncated"] is True
    assert result.structured_content["scanned_count"] == 1
    assert result.structured_content["links_checked"] == 1
    assert result.structured_content["link_targets_complete"] is False
    assert result.structured_content["broken_links"] == []


@pytest.mark.asyncio
async def test_consistency_scan_marks_unreadable_notes_incomplete_without_leaking_content(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Broken.md").write_text("sensitive note body", encoding="utf-8")
    vault = make_vault(tmp_path)
    monkeypatch.setattr(vault, "_read", lambda _path: (_ for _ in ()).throw(OSError("secret")))

    async with Client(create_server(vault)) as client:
        result = await client.call_tool("obsidian_check_consistency", {})

    assert result.structured_content["complete"] is False
    assert result.structured_content["errors"] == [
        {"path": "Broken.md", "issue": "note_unreadable"}
    ]
    assert "sensitive note body" not in str(result.structured_content)
    assert "secret" not in str(result.structured_content)


@pytest.mark.asyncio
async def test_consistency_scan_reports_unavailable_directories(tmp_path: Path, monkeypatch):
    (tmp_path / "Folder").mkdir()
    (tmp_path / "Folder" / "HiddenFromScan.md").write_text("body", encoding="utf-8")
    vault = make_vault(tmp_path)
    original_entries = vault._entries

    def entries(directory: str | None) -> list[str]:
        if directory == "Folder":
            raise PermissionError("private path")
        return original_entries(directory)

    monkeypatch.setattr(vault, "_entries", entries)
    async with Client(create_server(vault)) as client:
        result = await client.call_tool("obsidian_check_consistency", {})

    assert result.structured_content["complete"] is False
    assert result.structured_content["link_targets_complete"] is False
    assert result.structured_content["errors"] == [
        {"path": "Folder", "issue": "directory_unavailable"}
    ]


@pytest.mark.asyncio
async def test_consistency_scan_marks_directory_budget_and_depth_limits(
    tmp_path: Path, monkeypatch
):
    vault = make_vault(tmp_path)
    monkeypatch.setattr(
        vault,
        "_entries",
        lambda directory: [f"D{index}/" for index in range(201)] if directory is None else [],
    )
    paths, truncated, errors = vault._bounded_markdown_paths(10)
    assert paths == []
    assert truncated is True
    assert errors == []

    root = tmp_path / "deep"
    root.mkdir()
    current = root
    for index in range(21):
        current = current / f"D{index}"
        current.mkdir()
    deep_vault = make_vault(root)
    _, depth_truncated, depth_errors = deep_vault._bounded_markdown_paths(10)
    assert depth_truncated is True
    assert depth_errors == []


@pytest.mark.asyncio
async def test_consistency_scan_rejects_invalid_limit_and_skips_duplicate_directories(
    tmp_path: Path, monkeypatch
):
    vault = make_vault(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        await vault.check_consistency(0)
    with pytest.raises(ValueError, match="limit"):
        await vault.check_consistency(vault.settings.max_limit + 1)

    def entries(directory: str | None) -> list[str]:
        if directory is None:
            return ["Folder/", "Folder/"]
        return ["Note.md"]

    monkeypatch.setattr(vault, "_entries", entries)
    paths, truncated, errors = vault._bounded_markdown_paths(10)
    assert paths == ["Folder/Note.md"]
    assert truncated is False
    assert errors == []


@pytest.mark.asyncio
async def test_consistency_scan_validates_limit_and_requires_local_backend():
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"files": []})),
    )
    try:
        async with Client(create_server(api)) as client:
            invalid = await client.call_tool("obsidian_check_consistency", {"limit": 0})
            unavailable = await client.call_tool("obsidian_check_consistency", {})
    finally:
        await api.aclose()

    assert invalid.is_error is True
    assert unavailable.is_error is True


@pytest.mark.asyncio
async def test_file_consistency_reports_outgoing_links_and_incoming_backlinks(tmp_path: Path):
    (tmp_path / "Source.md").write_text("[[Target]] [[Missing]]", encoding="utf-8")
    (tmp_path / "Target.md").write_text("[[Source]]", encoding="utf-8")
    (tmp_path / "Other.md").write_text("[[Target|alias]]", encoding="utf-8")

    async with Client(create_server(make_vault(tmp_path))) as client:
        result = await client.call_tool("obsidian_check_file_consistency", {"path": "Source.md"})

    assert result.structured_content == {
        "path": "Source.md",
        "complete": True,
        "outgoing_links": ["Target", "Missing"],
        "link_targets_complete": True,
        "broken_links": ["Missing"],
        "backlinks": ["Target.md"],
        "backlinks_complete": True,
        "errors": [],
        "linked_notes": ["Source.md", "Target.md"],
        "recursive_broken_links": [{"source": "Source.md", "target": "Missing"}],
        "recursive_complete": True,
    }


@pytest.mark.asyncio
async def test_file_consistency_checks_reachable_notes_recursively(tmp_path: Path):
    (tmp_path / "Source.md").write_text("[[Middle]]", encoding="utf-8")
    (tmp_path / "Middle.md").write_text("[[MissingFromMiddle]]", encoding="utf-8")

    result = await make_vault(tmp_path).check_file_consistency("Source.md")

    assert result["linked_notes"] == ["Middle.md", "Source.md"]
    assert result["recursive_broken_links"] == [
        {"source": "Middle.md", "target": "MissingFromMiddle"}
    ]
    assert result["recursive_complete"] is True


@pytest.mark.asyncio
async def test_file_consistency_marks_incomplete_when_backlink_scan_has_read_error(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "Source.md").write_text("[[Target]]", encoding="utf-8")
    (tmp_path / "Target.md").write_text("target", encoding="utf-8")
    (tmp_path / "Unreadable.md").write_text("body", encoding="utf-8")
    vault = make_vault(tmp_path)
    original_read = vault._read

    def read(path: str) -> str:
        if path == "Unreadable.md":
            raise OSError("secret")
        return original_read(path)

    monkeypatch.setattr(vault, "_read", read)

    async with Client(create_server(vault)) as client:
        result = await client.call_tool("obsidian_check_file_consistency", {"path": "Source.md"})

    assert result.structured_content["complete"] is False
    assert result.structured_content["backlinks_complete"] is False
    assert result.structured_content["errors"] == [
        {"path": "Unreadable.md", "issue": "note_unreadable"}
    ]


@pytest.mark.asyncio
async def test_file_consistency_marks_recursive_read_error_incomplete(tmp_path: Path, monkeypatch):
    (tmp_path / "Source.md").write_text("[[Target]]", encoding="utf-8")
    (tmp_path / "Target.md").write_text("sensitive target content", encoding="utf-8")
    vault = make_vault(tmp_path)
    original_read = vault._read

    def read(path: str) -> str:
        if path == "Target.md":
            raise OSError("secret detail")
        return original_read(path)

    monkeypatch.setattr(vault, "_read", read)
    result = await vault.check_file_consistency("Source.md")

    assert result["recursive_complete"] is False
    assert result["errors"] == [{"path": "Target.md", "issue": "note_unreadable"}]
    assert "sensitive target content" not in str(result)
    assert "secret detail" not in str(result)


@pytest.mark.asyncio
async def test_file_consistency_rejects_missing_and_unsafe_paths(tmp_path: Path):
    vault = make_vault(tmp_path)
    async with Client(create_server(vault)) as client:
        missing = await client.call_tool("obsidian_check_file_consistency", {"path": "Missing.md"})
        traversal = await client.call_tool(
            "obsidian_check_file_consistency", {"path": "../Outside.md"}
        )

    assert missing.is_error is True
    assert traversal.is_error is True


@pytest.mark.asyncio
async def test_file_consistency_marks_target_inventory_incomplete_when_limited(tmp_path: Path):
    (tmp_path / "A.md").write_text("[[B]]", encoding="utf-8")
    (tmp_path / "B.md").write_text("[[A]] [[Missing]]", encoding="utf-8")
    vault = make_vault(tmp_path, max_limit=1)

    result = await vault.check_file_consistency("B.md")

    assert result["link_targets_complete"] is False
    assert result["backlinks_complete"] is False
    assert result["backlinks"] == ["A.md"]
    assert result["recursive_complete"] is False
    assert result["recursive_broken_links"] == []


@pytest.mark.asyncio
async def test_file_consistency_validates_extension_and_backend(tmp_path: Path):
    vault = make_vault(tmp_path)
    (tmp_path / "Note.txt").write_text("body", encoding="utf-8")
    api = ObsidianApi(
        Settings(api_url="https://obsidian.local", api_key="test-key"),
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"files": []})),
    )
    try:
        async with Client(create_server(vault)) as local_client:
            invalid = await local_client.call_tool(
                "obsidian_check_file_consistency", {"path": "Note.txt"}
            )
        async with Client(create_server(api)) as api_client:
            unavailable = await api_client.call_tool(
                "obsidian_check_file_consistency", {"path": "Note.md"}
            )
    finally:
        await api.aclose()

    assert invalid.is_error is True
    assert unavailable.is_error is True
