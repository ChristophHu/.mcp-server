import pytest
from test_server_tools import StubApi, invoke, note

from obsidian_mcp_server.config import Settings


@pytest.mark.asyncio
async def test_append_note_requires_write_permission():
    api = StubApi()
    result = await invoke(api, "obsidian_append_to_note", {"path": "Note.md", "content": "x"})
    assert result.is_error


@pytest.mark.asyncio
async def test_daily_note_write_rejects_malformed_date_and_oversized_content():
    enabled = Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True)
    api = StubApi(settings=enabled)
    assert (
        await invoke(api, "obsidian_write_daily_note", {"note_date": "bad", "content": "x"})
    ).is_error
    limited = StubApi(
        settings=Settings(
            api_url="https://obsidian.local",
            api_key="test",
            enable_writes=True,
            max_content_bytes=10,
        )
    )
    limited.periodic_errors.add(("daily", __import__("datetime").date(2026, 1, 1)))
    assert (
        await invoke(
            limited, "obsidian_write_daily_note", {"note_date": "2026-01-01", "content": "x"}
        )
    ).is_error


@pytest.mark.asyncio
async def test_frontmatter_and_tag_noop_paths_skip_remote_writes(monkeypatch):
    import obsidian_mcp_server.server as module

    settings = Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True)
    original = note(extra="custom: kept\n")
    api = StubApi(settings=settings, notes={"Note.md": original})
    monkeypatch.setattr(
        module, "apply_frontmatter_contract", lambda path, candidate, **kwargs: original
    )
    fm = await invoke(
        api,
        "obsidian_manage_frontmatter",
        {"path": "Note.md", "operation": "set", "key": "custom", "value": "kept"},
    )
    tags = await invoke(
        api, "obsidian_manage_tags", {"path": "Note.md", "operation": "add", "tags": ["work"]}
    )
    assert fm.structured_content["changed"] is False
    assert tags.structured_content["changed"] is False
    assert not any(call[0] == "write_note" for call in api.calls)


@pytest.mark.asyncio
async def test_frontmatter_audit_rejects_disabled_or_wrong_scope_apply():
    disabled = StubApi(files={None: []})
    assert (
        await invoke(disabled, "obsidian_audit_frontmatter", {"apply": True, "path": "Archive"})
    ).is_error
    enabled_without_root = StubApi(
        settings=Settings(
            api_url="https://obsidian.local",
            api_key="test",
            enable_frontmatter_migration=True,
        )
    )
    assert (
        await invoke(
            enabled_without_root, "obsidian_audit_frontmatter", {"apply": True, "path": "Archive"}
        )
    ).is_error
    enabled = StubApi(
        settings=Settings(
            api_url="https://obsidian.local",
            api_key="test",
            enable_frontmatter_migration=True,
            frontmatter_migration_root="Archive",
        )
    )
    assert (
        await invoke(enabled, "obsidian_audit_frontmatter", {"apply": True, "path": "Elsewhere"})
    ).is_error
    assert (await invoke(enabled, "obsidian_audit_frontmatter", {"max_files": 0})).is_error


@pytest.mark.asyncio
async def test_frontmatter_audit_skips_invalid_hidden_non_markdown_and_duplicate_entries():
    api = StubApi(
        files={
            None: ["/", ".obsidian/", "Folder/", "Folder/", "bad//path.md", "Readme.txt"],
            "Folder": ["Child.md", ".hidden.md", "Ignore.txt"],
        },
        notes={"Folder/Child.md": note(title="Child")},
    )
    result = await invoke(api, "obsidian_audit_frontmatter", {})
    assert result.structured_content["complete"] is False
    issues = {
        entry["issues"][0] for entry in result.structured_content["entries"] if entry["issues"]
    }
    assert "invalid_listing_entry" in issues
    assert result.structured_content["scanned_count"] == 1
    assert [call for call in api.calls if call[0] == "list_files"].count(
        ("list_files", "Folder")
    ) == 1


@pytest.mark.asyncio
async def test_frontmatter_audit_reports_unavailable_root_and_unreadable_note():
    unavailable = StubApi(files={None: RuntimeError("offline")})
    result = await invoke(unavailable, "obsidian_audit_frontmatter", {})
    assert result.structured_content["entries"][0]["path"] == ""
    assert result.structured_content["entries"][0]["issues"] == ["directory_unavailable"]

    class UnreadableApi(StubApi):
        async def get_note(self, path):
            if path == "Missing.md":
                raise FileNotFoundError(path)
            return await super().get_note(path)

    unreadable = UnreadableApi(files={None: ["Missing.md"]})
    result = await invoke(unreadable, "obsidian_audit_frontmatter", {})
    assert result.structured_content["complete"] is False
    assert result.structured_content["entries"][0]["issues"] == ["note_unreadable"]


@pytest.mark.asyncio
async def test_frontmatter_audit_stops_at_directory_request_cap():
    class WideApi(StubApi):
        async def list_files(self, path=None):
            self.calls.append(("list_files", path))
            if path is None:
                return [f"D{index}/" for index in range(200)]
            return []

    result = await invoke(WideApi(), "obsidian_audit_frontmatter", {})
    assert result.structured_content["truncated"] is True
    assert result.structured_content["complete"] is False
    assert result.structured_content["directories_scanned"] == 200


@pytest.mark.asyncio
async def test_frontmatter_audit_enforces_maximum_directory_depth():
    class DeepApi(StubApi):
        async def list_files(self, path=None):
            self.calls.append(("list_files", path))
            if path is None:
                return ["L0/"]
            depth = path.count("/")
            return [f"L{depth + 1}/"]

    result = await invoke(DeepApi(), "obsidian_audit_frontmatter", {})
    assert result.structured_content["complete"] is False
    assert result.structured_content["truncated"] is True
    assert result.structured_content["scanned_count"] == 0


@pytest.mark.asyncio
async def test_frontmatter_audit_apply_with_no_changes_is_safe_noop():
    compliant = (
        "---\ntitle: Ready\ntags: []\ncreatedAt: null\n"
        "updatedAt: '2026-01-01T00:00:00Z'\nstatus: active\n---\nBody\n"
    )
    settings = Settings(
        api_url="https://obsidian.local",
        api_key="test",
        enable_frontmatter_migration=True,
        frontmatter_migration_root="Archive",
    )
    api = StubApi(
        settings=settings, files={"Archive": ["Ready.md"]}, notes={"Archive/Ready.md": compliant}
    )
    result = await invoke(api, "obsidian_audit_frontmatter", {"path": "Archive", "apply": True})
    assert result.structured_content["apply_status"] == "no_changes"
    assert result.structured_content["applied_count"] == 0


@pytest.mark.asyncio
async def test_frontmatter_audit_conflict_read_error_blocks_migration():
    settings = Settings(
        api_url="https://obsidian.local",
        api_key="test",
        enable_frontmatter_migration=True,
        frontmatter_migration_root="Archive",
    )

    class DisappearingApi(StubApi):
        async def get_note(self, path):
            self.calls.append(("get_note", path))
            count = sum(call[:2] == ("get_note", path) for call in self.calls)
            if count > 1:
                raise FileNotFoundError(path)
            return "# Legacy\n"

    api = DisappearingApi(settings=settings, files={"Archive": ["Old.md"]})
    result = await invoke(api, "obsidian_audit_frontmatter", {"path": "Archive", "apply": True})
    assert result.structured_content["apply_status"] == "blocked_conflict"
    assert result.structured_content["conflict_count"] == 1
    assert not any(call[0] == "write_note" for call in api.calls)
