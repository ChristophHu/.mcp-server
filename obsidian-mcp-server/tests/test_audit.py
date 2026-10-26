from datetime import UTC, datetime

from obsidian_mcp_server.audit import inspect_note_frontmatter

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def test_legacy_note_proposes_null_created_at_without_fabricating_history() -> None:
    result = inspect_note_frontmatter("Archive/Old.md", "# Old\nBody\n", now=NOW)

    assert result.status == "needs_update"
    assert result.created_at_unknown is True
    assert "createdAt" in result.issues
    assert result.candidate_content is not None
    assert "createdAt: null" in result.candidate_content
    assert "updatedAt: '2026-10-25T12:00:00Z'" in result.candidate_content
    assert result.candidate_content.endswith("# Old\nBody\n")


def test_compliant_note_is_not_proposed_for_rewrite() -> None:
    content = (
        "---\ntitle: Ready\ntags: [work]\ncreatedAt: '2025-02-03T10:20:30Z'\n"
        "updatedAt: '2025-02-04T10:20:30Z'\nstatus: done\n---\nBody\n"
    )

    result = inspect_note_frontmatter("Ready.md", content, now=NOW)

    assert result.status == "compliant"
    assert result.candidate_content is None
    assert result.issues == ()


def test_malformed_yaml_is_reported_without_a_candidate() -> None:
    result = inspect_note_frontmatter("Bad.md", "---\ntitle: [broken\n---\nBody\n", now=NOW)

    assert result.status == "needs_review"
    assert result.candidate_content is None
    assert "invalid_frontmatter" in result.issues
