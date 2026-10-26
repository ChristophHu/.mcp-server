from datetime import UTC, datetime

import pytest

from obsidian_mcp_server.frontmatter import (
    _normalize_existing_timestamp,
    apply_frontmatter_contract,
    split_frontmatter,
)


@pytest.mark.parametrize(
    "value",
    [
        "not-a-timestamp",
        123,
        datetime(2026, 1, 1),
    ],
)
def test_existing_timestamps_must_be_timezone_aware_iso_values(value):
    with pytest.raises(ValueError, match="must"):
        _normalize_existing_timestamp(value, "createdAt")


def test_existing_timestamp_datetime_is_normalized_to_utc_z():
    value = datetime(2026, 1, 1, tzinfo=UTC)
    assert _normalize_existing_timestamp(value, "createdAt") == "2026-01-01T00:00:00Z"


def test_naive_current_time_is_rejected():
    with pytest.raises(ValueError, match="include a timezone"):
        apply_frontmatter_contract("Note.md", "Body", now=datetime(2026, 1, 1))


def test_split_frontmatter_returns_body_unchanged_when_metadata_is_absent():
    assert split_frontmatter("# Note\nBody\n") == (None, "# Note\nBody\n")


@pytest.mark.parametrize(
    "content",
    [
        "---\ntitle: Missing closer\nBody\n",
        "---\n- a sequence\n---\nBody\n",
    ],
)
def test_split_frontmatter_rejects_missing_closer_and_non_mapping_yaml(content):
    with pytest.raises(ValueError, match="Frontmatter"):
        split_frontmatter(content)


def test_split_frontmatter_rejects_non_mapping_yaml():
    with pytest.raises(ValueError, match="mapping"):
        split_frontmatter("---\n- sequence\n---\nBody\n")


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ("tags: work", "tags must be a list"),
        ("status: unknown", "status must be"),
        ("title: ''", "title must be a non-empty"),
    ],
)
def test_frontmatter_contract_rejects_invalid_field_values(metadata, message):
    content = f"---\n{metadata}\n---\nBody\n"
    with pytest.raises(ValueError, match=message):
        apply_frontmatter_contract("Note.md", content)


def test_frontmatter_contract_accepts_null_historical_created_at():
    content = (
        "---\ntitle: Old\ntags: []\ncreatedAt: null\n"
        "updatedAt: '2025-01-01T00:00:00Z'\nstatus: active\n---\nBody\n"
    )
    result = apply_frontmatter_contract(
        "Old.md",
        content.replace("Body", "Updated"),
        previous_content=content,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert "createdAt: null" in result
