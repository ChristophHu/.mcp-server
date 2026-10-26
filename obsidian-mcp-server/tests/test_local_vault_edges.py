import errno
import os
from datetime import date
from pathlib import Path

import pytest

import obsidian_mcp_server.local_vault as local_vault_module
from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.local_vault import LocalVault


def settings(root: Path, **kwargs):
    return Settings(api_url="", api_key="", vault_path=root, **kwargs)


def link_tree(path):
    return {"if": [{"==": [{"var": "path"}, path]}, [None, None, None], False]}


@pytest.mark.asyncio
async def test_local_vault_handles_missing_configured_root_and_changed_root(tmp_path: Path):
    with pytest.raises(ValueError, match="path is required"):
        LocalVault(Settings(api_url="", api_key=""))

    root = tmp_path / "vault"
    root.mkdir()
    vault = LocalVault(settings(root))
    moved = tmp_path / "moved"
    root.rename(moved)
    root.mkdir()
    with pytest.raises(PermissionError, match="root changed"):
        await vault.list_files()


@pytest.mark.asyncio
async def test_local_vault_rejects_symlinked_directories_and_non_regular_files(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret", encoding="utf-8")
    (tmp_path / "linked-dir").symlink_to(outside, target_is_directory=True)
    (tmp_path / "folder").mkdir()
    vault = LocalVault(settings(tmp_path))

    with pytest.raises(PermissionError):
        await vault.get_note("linked-dir/secret.md")
    with pytest.raises(ValueError, match="regular file"):
        await vault.get_note("folder")


@pytest.mark.asyncio
async def test_local_vault_rejects_invalid_utf8_and_reports_missing_files(tmp_path: Path):
    (tmp_path / "bad.md").write_bytes(b"\xff")
    vault = LocalVault(settings(tmp_path))
    with pytest.raises(ValueError, match="UTF-8"):
        await vault.get_note("bad.md")
    with pytest.raises(FileNotFoundError):
        await vault.get_note("missing.md")


@pytest.mark.asyncio
async def test_local_vault_search_context_bounds_and_no_match(tmp_path: Path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "K.md").write_text("x" * 40 + "needle" + "y" * 40, encoding="utf-8")
    (tmp_path / "readme.txt").write_text("not markdown", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))
    hits = await vault.search_notes("needle", context_length=20)
    assert hits == [{"filename": "nested/K.md", "matches": ["x" * 10 + "needle" + "y" * 10]}]
    assert await vault.search_notes("absent") == []


def test_local_vault_rejects_root_that_is_not_a_directory(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(local_vault_module.stat, "S_ISDIR", lambda _mode: False)
    with pytest.raises(ValueError, match="Vault root must be a directory"):
        LocalVault(settings(tmp_path))


@pytest.mark.asyncio
async def test_local_vault_tag_scan_skips_invalid_yaml_and_accepts_scalar_tags(tmp_path: Path):
    (tmp_path / "bad.md").write_text("---\ntags: [broken\n---\n", encoding="utf-8")
    (tmp_path / "scalar.md").write_text("---\ntags: solo\n---\n", encoding="utf-8")
    (tmp_path / "wrong.md").write_text("---\ntags: 7\n---\n", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))
    assert await vault.list_tags() == [{"name": "solo", "count": 1}]


@pytest.mark.asyncio
async def test_local_vault_link_lookup_reports_outgoing_backlinks_and_unresolved(tmp_path: Path):
    (tmp_path / "Target.md").write_text("[[Known]] [[Missing]] [[#section]]", encoding="utf-8")
    (tmp_path / "Known.md").write_text("known", encoding="utf-8")
    (tmp_path / "Ref.md").write_text("[[Target|alias]]", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))

    result = await vault.search_jsonlogic(link_tree("Target.md"))
    assert result == [
        {
            "filename": "Target.md",
            "result": [["Known", "Missing"], ["Ref.md"], ["Missing"]],
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tree",
    [
        {},
        {"if": []},
        {"if": ["bad", [], False]},
        {"if": [{"==": []}, [], False]},
        {"if": [{"==": [{"var": "other"}, "A.md"]}, [], False]},
    ],
)
async def test_local_vault_rejects_unsupported_link_query_shapes(tmp_path: Path, tree):
    vault = LocalVault(settings(tmp_path))
    with pytest.raises(ValueError, match="Only note-link"):
        await vault.search_jsonlogic(tree)


@pytest.mark.asyncio
async def test_local_vault_target_resolution_empty_extension_and_invalid_path(tmp_path: Path):
    (tmp_path / "Present.md").write_text("present", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))
    assert vault._target_exists("") is True
    assert vault._target_exists("Present") is True
    assert vault._target_exists("Present.md") is True
    assert vault._target_exists("../outside") is False
    assert LocalVault._resolve_link("", "", []) is None


@pytest.mark.asyncio
async def test_local_vault_resolves_qualified_and_folder_local_wikilinks(tmp_path: Path):
    (tmp_path / "Area").mkdir()
    (tmp_path / "Area" / "Target.md").write_text(
        "[[Known]] [[area/known|alias]] [[Missing]] [[../RootNote]]", encoding="utf-8"
    )
    (tmp_path / "Area" / "Known.md").write_text("known", encoding="utf-8")
    (tmp_path / "Area" / "Ref.md").write_text("[[area/TARGET]]", encoding="utf-8")
    (tmp_path / "RootNote.md").write_text("root", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))

    assert await vault.search_jsonlogic(link_tree("Area/Target.md")) == [
        {
            "filename": "Area/Target.md",
            "result": [
                ["Known", "area/known", "Missing", "../RootNote"],
                ["Area/Ref.md"],
                ["Missing", "../RootNote"],
            ],
        }
    ]
    case_insensitive_result = await vault.search_jsonlogic(link_tree("area/target.md"))
    assert isinstance(case_insensitive_result[0], dict)
    assert case_insensitive_result[0]["filename"] == "Area/Target.md"


@pytest.mark.asyncio
async def test_local_vault_resolves_only_unique_global_basenames(tmp_path: Path):
    (tmp_path / "Area").mkdir()
    (tmp_path / "Area" / "Target.md").write_text("[[Unique]] [[Duplicate]]", encoding="utf-8")
    for folder, filename in (
        ("One", "Unique.md"),
        ("Two", "Duplicate.md"),
        ("Three", "Duplicate.md"),
    ):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / filename).write_text("note", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))

    assert await vault.search_jsonlogic(link_tree("Area/Target.md")) == [
        {
            "filename": "Area/Target.md",
            "result": [["Unique", "Duplicate"], [], ["Duplicate"]],
        }
    ]


@pytest.mark.asyncio
async def test_local_vault_resolves_unique_space_underscore_aliases(tmp_path: Path):
    (tmp_path / "Guides").mkdir()
    (tmp_path / "Guides" / "Link_Name.md").write_text("one", encoding="utf-8")
    (tmp_path / "Guides" / "Other Name.md").write_text("two", encoding="utf-8")
    (tmp_path / "Guides" / "Source.md").write_text(
        "[[Link Name]] [[Other_Name]] [[Ambiguous Name]]", encoding="utf-8"
    )
    for folder in ("One", "Two"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Ambiguous_Name.md").write_text(folder, encoding="utf-8")
    vault = LocalVault(settings(tmp_path))

    assert await vault.search_jsonlogic(link_tree("Guides/Source.md")) == [
        {
            "filename": "Guides/Source.md",
            "result": [
                ["Link Name", "Other_Name", "Ambiguous Name"],
                [],
                ["Ambiguous Name"],
            ],
        }
    ]


@pytest.mark.asyncio
async def test_local_vault_directory_listing_skips_raced_entries(tmp_path: Path, monkeypatch):
    (tmp_path / "gone.md").write_text("gone", encoding="utf-8")
    vault = LocalVault(settings(tmp_path))
    original_stat = os.stat

    def missing_stat(path, *args, **kwargs):
        if path == "gone.md":
            raise FileNotFoundError
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", missing_stat)
    assert await vault.list_files() == []


@pytest.mark.asyncio
async def test_local_vault_sanitizes_unexpected_directory_os_errors(tmp_path: Path, monkeypatch):
    vault = LocalVault(settings(tmp_path))
    original_open = os.open

    def denied_open(path, flags, *args, **kwargs):
        if path == vault._root:
            raise OSError(errno.EACCES, "private path")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", denied_open)
    with pytest.raises(RuntimeError, match="Unable to access"):
        await vault.list_files()


def test_settings_rejects_existing_non_directory_vault_path(tmp_path: Path):
    file_path = tmp_path / "not-a-vault"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="must point to a directory"):
        Settings.from_env({"OBSIDIAN_VAULT_PATH": str(file_path)})


@pytest.mark.asyncio
async def test_local_vault_covers_root_missing_and_symlink_errno_paths(tmp_path: Path, monkeypatch):
    vault = LocalVault(settings(tmp_path))
    original_open = os.open
    calls = []

    def root_missing(path, flags, *args, **kwargs):
        if path == vault._root:
            raise FileNotFoundError(errno.ENOENT, "missing")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", root_missing)
    with pytest.raises(FileNotFoundError):
        await vault.list_files()

    monkeypatch.setattr(os, "open", original_open)
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "note.md").write_text("note", encoding="utf-8")

    def loop_error(path, flags, *args, **kwargs):
        if path == "child":
            calls.append(path)
            raise OSError(errno.ELOOP, "symlink")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", loop_error)
    with pytest.raises(PermissionError, match="Symbolic links"):
        await vault.get_note("child/note.md")
    assert calls == ["child"]


@pytest.mark.asyncio
async def test_local_vault_sanitizes_nested_directory_errors_and_empty_walk(
    tmp_path: Path, monkeypatch
):
    (tmp_path / "child").mkdir()
    vault = LocalVault(settings(tmp_path))
    original_open = os.open

    def io_error(path, flags, *args, **kwargs):
        if path == "child":
            raise OSError(errno.EIO, "private detail")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", io_error)
    with pytest.raises(RuntimeError, match="Unable to access"):
        await vault.list_files("child")
    monkeypatch.setattr(os, "open", original_open)
    assert await vault.search_notes("none") == []


@pytest.mark.asyncio
async def test_local_vault_read_only_guards_and_periodic_ui_unsupported(tmp_path: Path):
    vault = LocalVault(settings(tmp_path))
    with pytest.raises(PermissionError, match="read-only"):
        await vault.write_note("Note.md", "x")
    with pytest.raises(RuntimeError, match="configured local path template"):
        await vault.append_periodic_note("daily", date(2026, 1, 1), "x")
    with pytest.raises(RuntimeError, match="configured local path template"):
        await vault.replace_periodic_note("daily", date(2026, 1, 1), "x")
    with pytest.raises(RuntimeError, match="Periodic notes"):
        await vault.get_periodic_note("daily", date(2026, 1, 1))
    with pytest.raises(RuntimeError, match="Obsidian UI"):
        await vault.open_in_ui("Note.md")
