from datetime import UTC, datetime

import pytest

from obsidian_mcp_server.frontmatter import apply_frontmatter_contract

FIXED_NOW = datetime(2026, 10, 26, 12, 30, tzinfo=UTC)


def test_new_note_gets_required_frontmatter_and_keeps_body() -> None:
    result = apply_frontmatter_contract("Projects/Idea.md", "# Idea\n\nBody\n", now=FIXED_NOW)

    assert result.startswith("---\n")
    assert "title: Idea" in result
    assert "tags: []" in result
    assert "createdAt: '2026-10-26T12:30:00Z'" in result
    assert "updatedAt: '2026-10-26T12:30:00Z'" in result
    assert "status: active" in result
    assert result.endswith("# Idea\n\nBody\n")


def test_update_preserves_created_at_unknown_fields_and_updates_only_updated_at() -> None:
    current = (
        "---\ntitle: Existing\ntags: [work]\ncreatedAt: null\n"
        "updatedAt: '2024-01-01T00:00:00Z'\nstatus: done\ncustom: keep\n---\nOld body\n"
    )

    result = apply_frontmatter_contract(
        "Existing.md",
        current.replace("Old body", "New body"),
        now=FIXED_NOW,
        previous_content=current,
    )

    assert "createdAt: null" in result
    assert "updatedAt: '2026-10-26T12:30:00Z'" in result
    assert "status: done" in result
    assert "custom: keep" in result
    assert result.endswith("New body\n")


def test_unchanged_note_keeps_existing_timestamp() -> None:
    current = (
        "---\ntitle: Keep\ntags: []\ncreatedAt: null\nupdatedAt: old\nstatus: active\n---\nBody\n"
    )

    result = apply_frontmatter_contract("Keep.md", current, now=FIXED_NOW, previous_content=current)
    assert result == current


def test_invalid_frontmatter_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid YAML"):
        apply_frontmatter_contract("Bad.md", "---\ntitle: [broken\n---\nBody\n", now=FIXED_NOW)


def test_unquoted_utc_timestamps_are_serialized_back_with_z_suffix() -> None:
    current = (
        "---\ntitle: Keep\ntags: []\ncreatedAt: 2025-02-03T10:20:30Z\n"
        "updatedAt: 2025-02-04T10:20:30Z\nstatus: active\n---\nBody\n"
    )

    result = apply_frontmatter_contract(
        "Keep.md", current.replace("Body", "Changed"), now=FIXED_NOW, previous_content=current
    )

    assert "createdAt: '2025-02-03T10:20:30Z'" in result
    assert "updatedAt: '2026-10-26T12:30:00Z'" in result


def test_replacement_without_frontmatter_inherits_existing_metadata() -> None:
    current = (
        "---\ntitle: Monday\ntags: [work]\ncreatedAt: '2026-10-26T08:00:00Z'\n"
        "updatedAt: '2026-10-26T08:00:00Z'\nstatus: done\ncustom: keep\n---\nOld body\n"
    )

    result = apply_frontmatter_contract(
        "Daily.md", "New body\n", now=FIXED_NOW, previous_content=current
    )

    assert "title: Monday" in result
    assert "tags:\n- work" in result
    assert "createdAt: '2026-10-26T08:00:00Z'" in result
    assert "updatedAt: '2026-10-26T12:30:00Z'" in result
    assert "status: done" in result
    assert "custom: keep" in result
    assert result.endswith("New body\n")
