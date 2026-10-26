from datetime import date

import pytest
from mcp import Client
from mcp.server import MCPServer

from obsidian_mcp_server import server as server_module
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.server import create_server


class StubApi:
    def __init__(
        self, *, settings=None, notes=None, files=None, tags=None, hits=None, link_hits=None
    ):
        self.settings = settings or Settings(api_url="https://obsidian.local", api_key="test")
        self.notes = dict(notes or {})
        self.files = files or {None: []}
        self.tags = tags or []
        self.hits = hits or []
        self.link_hits = link_hits or []
        self.calls = []
        self.periodic = {}
        self.periodic_errors = set()
        self.fail_write = False

    async def get_status(self):
        return {"versions": {"local": "1"}}

    async def get_note(self, path):
        self.calls.append(("get_note", path))
        if path not in self.notes:
            raise FileNotFoundError(path)
        return self.notes[path]

    async def write_note(self, path, content, **kwargs):
        self.calls.append(("write_note", path, content, kwargs))
        if self.fail_write:
            raise RuntimeError("remote write failed")
        self.notes[path] = content

    async def list_files(self, path=None):
        self.calls.append(("list_files", path))
        value = self.files.get(path, [])
        if isinstance(value, Exception):
            raise value
        return value

    async def search_notes(self, query, *, context_length=80):
        self.calls.append(("search_notes", query, context_length))
        return self.hits

    async def list_tags(self):
        return self.tags

    async def search_jsonlogic(self, tree):
        self.calls.append(("search_jsonlogic", tree))
        return self.link_hits

    async def open_in_ui(self, path, *, new_pane=False):
        self.calls.append(("open_in_ui", path, new_pane))

    async def get_periodic_note(self, period, note_date):
        self.calls.append(("get_periodic_note", period, note_date))
        key = (period, note_date)
        if key in self.periodic_errors:
            raise FileNotFoundError(key)
        return self.periodic[key]

    async def append_periodic_note(self, period, note_date, content):
        self.calls.append(("append_periodic_note", period, note_date, content))
        self.periodic[(period, note_date)] = content

    async def replace_periodic_note(self, period, note_date, content):
        self.calls.append(("replace_periodic_note", period, note_date, content))
        self.periodic[(period, note_date)] = content


async def invoke(api, tool, arguments):
    async with Client(create_server(api)) as client:
        return await client.call_tool(tool, arguments)


def note(body="Body\n", *, title="Note", tags=None, extra=""):
    tags = tags or []
    return (
        f"---\ntitle: {title}\ntags: {tags}\ncreatedAt: null\n"
        "updatedAt: '2026-01-01T00:00:00Z'\nstatus: active\n"
        f"{extra}---\n{body}"
    )


@pytest.mark.asyncio
async def test_status_tool_returns_api_status():
    result = await invoke(StubApi(), "obsidian_status", {})
    assert result.structured_content == {"versions": {"local": "1"}}


@pytest.mark.asyncio
async def test_list_notes_filters_hidden_entries_and_reports_pagination():
    api = StubApi(files={None: ["A.md", ".hidden/", "Folder/.private.md", "B.md"]})
    result = await invoke(api, "obsidian_list_notes", {"limit": 1})
    assert result.structured_content == {
        "path": "",
        "entries": ["A.md"],
        "has_more": True,
        "total_returned": 1,
    }
    assert (await invoke(api, "obsidian_list_notes", {"limit": 0})).is_error


@pytest.mark.asyncio
async def test_search_filters_malformed_and_hidden_hits_and_validates_bounds():
    api = StubApi(
        hits=[
            {"filename": "A.md", "matches": []},
            {"filename": ".hidden/A.md"},
            {"filename": 3},
            "bad",
            {"filename": "B.md"},
        ]
    )
    result = await invoke(api, "obsidian_search_notes", {"query": " term ", "limit": 1})
    assert result.structured_content["results"] == [{"filename": "A.md", "matches": []}]
    assert result.structured_content["has_more"] is True
    for arguments in [
        {"query": " "},
        {"query": "x" * 201},
        {"query": "x", "limit": 0},
        {"query": "x", "context_length": 19},
        {"query": "x", "context_length": 501},
    ]:
        assert (await invoke(api, "obsidian_search_notes", arguments)).is_error


@pytest.mark.asyncio
async def test_rest_write_note_overwrite_is_denied_without_target_approval():
    existing = note("Body\n", title="Old", extra="custom: keep\n")
    api = StubApi(
        settings=Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True),
        notes={"Note.md": existing},
    )
    result = await invoke(
        api, "obsidian_write_note", {"path": "Note.md", "content": existing, "overwrite": True}
    )
    assert result.is_error is True
    assert not any(call[0] == "write_note" for call in api.calls)
    assert (await invoke(api, "obsidian_write_note", {"path": "Note.txt", "content": "x"})).is_error


@pytest.mark.asyncio
async def test_write_note_rejects_prepared_content_over_size_limit():
    api = StubApi(
        settings=Settings(
            api_url="https://obsidian.local",
            api_key="test",
            enable_writes=True,
            max_content_bytes=10,
        )
    )
    assert (await invoke(api, "obsidian_write_note", {"path": "Note.md", "content": "x"})).is_error


@pytest.mark.asyncio
async def test_rest_append_note_is_denied_without_conditional_write_support():
    settings = Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True)
    api = StubApi(settings=settings)
    created = await invoke(api, "obsidian_append_to_note", {"path": "New.md", "content": "first"})
    assert created.is_error is True
    assert "New.md" not in api.notes
    api.notes["Existing.md"] = note("First")
    existing = api.notes["Existing.md"]
    appended = await invoke(
        api, "obsidian_append_to_note", {"path": "Existing.md", "content": "Second"}
    )
    assert appended.is_error is True
    assert api.notes["Existing.md"] == existing
    assert (
        await invoke(api, "obsidian_append_to_note", {"path": "x.txt", "content": "x"})
    ).is_error
    assert (
        await invoke(api, "obsidian_append_to_note", {"path": "Empty.md", "content": ""})
    ).is_error


@pytest.mark.asyncio
async def test_get_daily_note_validates_canonical_date_and_reads_periodic_endpoint():
    api = StubApi()
    api.periodic[("daily", date(2026, 10, 26))] = "Daily body"
    result = await invoke(api, "obsidian_get_daily_note", {"note_date": "2026-10-26"})
    assert result.structured_content == {"date": "2026-10-26", "content": "Daily body"}
    assert (await invoke(api, "obsidian_get_daily_note", {"note_date": "20261026"})).is_error
    assert (await invoke(api, "obsidian_get_daily_note", {"note_date": "bad"})).is_error


@pytest.mark.asyncio
async def test_daily_note_overwrite_unchanged_body_does_not_write():
    settings = Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True)
    api = StubApi(settings=settings)
    existing = note("Body\n")
    api.periodic[("daily", date(2026, 10, 26))] = existing
    result = await invoke(
        api,
        "obsidian_write_daily_note",
        {"note_date": "2026-10-26", "content": existing, "overwrite": True},
    )
    assert result.is_error is True
    assert not any(
        call[0] in {"append_periodic_note", "replace_periodic_note", "get_periodic_note"}
        for call in api.calls
    )


@pytest.mark.asyncio
async def test_list_tags_sorts_filters_and_limits_results():
    api = StubApi(
        tags=[
            {"name": "z", "count": 2},
            {"name": "b", "count": 2},
            {"name": "a", "count": 3},
            "invalid",
            {"name": 4, "count": 9},
        ]
    )
    result = await invoke(api, "obsidian_list_tags", {"limit": 2})
    assert result.structured_content["tags"] == [
        {"name": "a", "count": 3},
        {"name": "b", "count": 2},
    ]
    assert result.structured_content["has_more"] is True
    assert (await invoke(api, "obsidian_list_tags", {"limit": 201})).is_error


@pytest.mark.asyncio
async def test_manage_frontmatter_reads_but_denies_unapproved_mutations():
    api = StubApi(
        settings=Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True),
        notes={"Note.md": note(extra="custom: old\n")},
    )
    got = await invoke(
        api, "obsidian_manage_frontmatter", {"path": "Note.md", "operation": "get", "key": "custom"}
    )
    assert got.structured_content["value"] == "old"
    set_result = await invoke(
        api,
        "obsidian_manage_frontmatter",
        {"path": "Note.md", "operation": "set", "key": "custom", "value": "new"},
    )
    assert set_result.is_error is True
    assert "custom: old" in api.notes["Note.md"]
    deleted = await invoke(
        api,
        "obsidian_manage_frontmatter",
        {"path": "Note.md", "operation": "delete", "key": "custom"},
    )
    assert deleted.is_error is True
    assert "custom: old" in api.notes["Note.md"]


@pytest.mark.asyncio
async def test_manage_frontmatter_validates_operation_key_value_and_required_keys():
    api = StubApi(
        settings=Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True),
        notes={"Note.md": note()},
    )
    for args in [
        {"path": "Note.md", "operation": "bad", "key": "x"},
        {"path": "Note.md", "operation": "get", "key": ""},
        {"path": "Note.md", "operation": "set", "key": "x"},
        {"path": "Note.md", "operation": "delete", "key": "title"},
    ]:
        assert (await invoke(api, "obsidian_manage_frontmatter", args)).is_error
    readonly = StubApi(notes={"Note.md": note()})
    assert (
        await invoke(
            readonly,
            "obsidian_manage_frontmatter",
            {"path": "Note.md", "operation": "set", "key": "x", "value": "y"},
        )
    ).is_error


@pytest.mark.asyncio
async def test_manage_tags_reads_but_denies_unapproved_mutations():
    settings = Settings(api_url="https://obsidian.local", api_key="test", enable_writes=True)
    original_note = note(extra="tags: [work]\n")
    api = StubApi(settings=settings, notes={"Note.md": original_note})
    listed = await invoke(api, "obsidian_manage_tags", {"path": "Note.md", "operation": "list"})
    assert listed.structured_content["tags"] == ["work"]
    added = await invoke(
        api,
        "obsidian_manage_tags",
        {"path": "Note.md", "operation": "add", "tags": ["#work", "work", " home "]},
    )
    assert added.is_error is True
    removed = await invoke(
        api, "obsidian_manage_tags", {"path": "Note.md", "operation": "remove", "tags": ["#work"]}
    )
    assert removed.is_error is True
    assert api.notes["Note.md"] == original_note
    for args in [
        {"path": "Note.md", "operation": "bad"},
        {"path": "Note.md", "operation": "add", "tags": []},
        {"path": "Note.md", "operation": "remove", "tags": ["#"]},
    ]:
        assert (await invoke(api, "obsidian_manage_tags", args)).is_error
    bad = StubApi(settings=settings, notes={"Note.md": note(extra="tags: bad\n")})
    assert (
        await invoke(bad, "obsidian_manage_tags", {"path": "Note.md", "operation": "list"})
    ).is_error
    readonly = StubApi(notes={"Note.md": note()})
    assert (
        await invoke(
            readonly,
            "obsidian_manage_tags",
            {"path": "Note.md", "operation": "add", "tags": ["work"]},
        )
    ).is_error


@pytest.mark.asyncio
async def test_open_in_ui_passes_path_and_new_pane_flag():
    api = StubApi()
    result = await invoke(api, "obsidian_open_in_ui", {"path": "Folder/Note.md", "new_pane": True})
    assert result.structured_content == {"path": "Folder/Note.md", "opened": "true"}
    assert ("open_in_ui", "Folder/Note.md", True) in api.calls


@pytest.mark.asyncio
async def test_note_links_skip_unrelated_hits_and_reject_bad_or_missing_metadata():
    api = StubApi(link_hits=["bad", {"filename": "Other.md", "result": [[], [], []]}])
    assert (await invoke(api, "obsidian_get_note_links", {"path": "Note.md"})).is_error
    api.link_hits = [{"filename": "Note.md", "result": [[], [], "bad"]}]
    assert (await invoke(api, "obsidian_get_note_links", {"path": "Note.md"})).is_error


@pytest.mark.asyncio
async def test_create_server_can_build_its_default_api(monkeypatch):
    import obsidian_mcp_server.server as module

    settings = Settings(api_url="https://obsidian.local", api_key="test")
    monkeypatch.setattr(module.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(module, "ObsidianApi", lambda passed: StubApi(settings=passed))
    assert create_server() is not None


@pytest.mark.asyncio
async def test_server_entrypoint_runs_stdio(monkeypatch):
    import runpy

    calls = []
    monkeypatch.setattr(MCPServer, "run", lambda self, *, transport: calls.append(transport))
    runpy.run_path(server_module.__file__, run_name="__main__")
    assert calls == ["stdio"]
