from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

import yaml

ALLOWED_STATUSES = {"active", "in-progress", "done", "archived"}
_FRONTMATTER_START = re.compile(r"\A---\r?\n")


def _timestamp(now: datetime | None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_existing_timestamp(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Frontmatter {field} must be an ISO-8601 timestamp or null") from exc
    else:
        raise ValueError(f"Frontmatter {field} must be an ISO-8601 timestamp or null")
    if parsed.tzinfo is None:
        raise ValueError(f"Frontmatter {field} must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def split_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Return parsed YAML metadata and body; reject malformed YAML/frontmatter."""
    start = _FRONTMATTER_START.match(content)
    if not start:
        return None, content

    lines = content[start.end() :].splitlines(keepends=True)
    closing_index = next(
        (index for index, line in enumerate(lines) if line.rstrip("\r\n") == "---"), None
    )
    if closing_index is None:
        raise ValueError("Frontmatter must contain valid YAML and a closing delimiter")

    raw_yaml = "".join(lines[:closing_index])
    try:
        parsed = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError("Frontmatter must contain valid YAML") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    body = "".join(lines[closing_index + 1 :])
    return parsed, body


def apply_frontmatter_contract(
    path: str,
    content: str,
    *,
    now: datetime | None = None,
    previous_content: str | None = None,
    removed_fields: set[str] | None = None,
) -> str:
    """Add/maintain the server's required metadata without changing note body."""
    if previous_content is not None and content == previous_content:
        return content

    existing, body = split_frontmatter(content)
    metadata: dict[str, Any] = {}
    if previous_content is not None:
        previous_metadata, _ = split_frontmatter(previous_content)
        metadata.update(previous_metadata or {})
    metadata.update(existing or {})
    for field in removed_fields or ():
        metadata.pop(field, None)
    stamp = _timestamp(now)
    created = previous_content is None

    metadata.setdefault("title", PurePosixPath(path).stem)
    metadata.setdefault("tags", [])
    if not isinstance(metadata["tags"], list) or not all(
        isinstance(tag, str) for tag in metadata["tags"]
    ):
        raise ValueError("Frontmatter tags must be a list of strings")

    if "createdAt" not in metadata:
        metadata["createdAt"] = stamp if created else None
    else:
        metadata["createdAt"] = _normalize_existing_timestamp(metadata["createdAt"], "createdAt")
    metadata["updatedAt"] = stamp
    metadata.setdefault("status", "active")
    if metadata["status"] not in ALLOWED_STATUSES:
        raise ValueError("Frontmatter status must be active, in-progress, done, or archived")
    if not isinstance(metadata["title"], str) or not metadata["title"].strip():
        raise ValueError("Frontmatter title must be a non-empty string")

    serialized = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{serialized}---\n{body}"
