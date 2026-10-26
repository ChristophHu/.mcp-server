from datetime import UTC, datetime

import pytest

from obsidian_mcp_server.audit import inspect_note_frontmatter

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("content", "issue"),
    [
        ("\ufeff# BOM\n", "unsupported_bom"),
        ("---\ntitle: A\n---\n---\ntags: []\n---\nBody", "multiple_frontmatter_blocks"),
        ("---\ntitle: [broken\n---\nBody", "invalid_frontmatter"),
    ],
)
def test_audit_marks_unsafe_frontmatter_for_review(content, issue):
    result = inspect_note_frontmatter("Note.md", content, now=NOW)
    assert result.status == "needs_review"
    assert result.issues == (issue,)
    assert result.candidate_content is None
    assert result.created_at_unknown is True


@pytest.mark.parametrize(
    ("metadata", "issue"),
    [
        ("title: 4", "invalid:title"),
        ("tags: [work, 4]", "invalid:tags"),
        ("status: missing", "invalid:status"),
        ("createdAt: not-a-date", "invalid:createdAt"),
    ],
)
def test_audit_marks_invalid_metadata_for_review(metadata, issue):
    content = f"---\n{metadata}\n---\nBody\n"
    result = inspect_note_frontmatter("Note.md", content, now=NOW)
    assert result.status == "needs_review"
    assert issue in result.issues
    assert result.candidate_content is None


def test_audit_proposes_normalizing_valid_noncanonical_timestamp():
    content = (
        "---\ntitle: Note\ntags: []\ncreatedAt: '2025-01-01T00:00:00+00:00'\n"
        "updatedAt: '2025-01-01T00:00:00Z'\nstatus: active\n---\nBody\n"
    )
    result = inspect_note_frontmatter("Note.md", content, now=NOW)
    assert result.status == "needs_update"
    assert "normalize:createdAt" in result.issues
    assert result.candidate_content is not None
    assert "createdAt: '2025-01-01T00:00:00Z'" in result.candidate_content


def test_audit_reports_unmigratable_generated_title_for_empty_path():
    result = inspect_note_frontmatter("", "# Body\n", now=NOW)
    assert result.status == "needs_review"
    assert result.issues[-1] == "unsafe_to_migrate"
    assert result.candidate_content is None


def test_audit_preserves_created_at_null_as_known_unknown_history():
    content = "---\ncreatedAt: null\n---\nBody\n"
    result = inspect_note_frontmatter("Note.md", content, now=NOW)
    assert result.created_at_unknown is True
    assert result.status == "needs_update"
    assert "createdAt" not in result.issues
