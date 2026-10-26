from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from obsidian_mcp_server.frontmatter import (
    ALLOWED_STATUSES,
    _normalize_existing_timestamp,
    apply_frontmatter_contract,
    split_frontmatter,
)

REQUIRED_FIELDS = ("title", "tags", "createdAt", "updatedAt", "status")


@dataclass(frozen=True)
class FrontmatterAudit:
    path: str
    status: str
    issues: tuple[str, ...]
    created_at_unknown: bool
    candidate_content: str | None


def inspect_note_frontmatter(
    path: str, content: str, *, now: datetime | None = None
) -> FrontmatterAudit:
    """Classify one note and, only when safe, prepare a contract-compliant candidate."""
    if content.startswith("\ufeff"):
        return FrontmatterAudit(path, "needs_review", ("unsupported_bom",), True, None)

    try:
        metadata, body = split_frontmatter(content)
    except ValueError:
        return FrontmatterAudit(path, "needs_review", ("invalid_frontmatter",), True, None)

    if body.startswith("---\n") or body.startswith("---\r\n"):
        return FrontmatterAudit(path, "needs_review", ("multiple_frontmatter_blocks",), True, None)

    fields: dict[str, Any] = dict(metadata or {})
    issues = [field for field in REQUIRED_FIELDS if field not in fields]

    if "title" in fields and (not isinstance(fields["title"], str) or not fields["title"].strip()):
        issues.append("invalid:title")
    if "tags" in fields and (
        not isinstance(fields["tags"], list)
        or not all(isinstance(tag, str) and tag.strip() for tag in fields["tags"])
    ):
        issues.append("invalid:tags")
    if "status" in fields and fields["status"] not in ALLOWED_STATUSES:
        issues.append("invalid:status")

    created_at_unknown = fields.get("createdAt") is None
    for field in ("createdAt", "updatedAt"):
        if field not in fields:
            continue
        if field == "createdAt" and fields[field] is None:
            continue
        try:
            normalized = _normalize_existing_timestamp(fields[field], field)
        except ValueError:
            issues.append(f"invalid:{field}")
        else:
            if normalized != fields[field]:
                issues.append(f"normalize:{field}")

    if any(issue.startswith("invalid:") for issue in issues):
        return FrontmatterAudit(path, "needs_review", tuple(issues), created_at_unknown, None)

    change_issues = [issue for issue in issues if not issue.startswith("invalid:")]
    if not change_issues:
        return FrontmatterAudit(path, "compliant", (), created_at_unknown, None)

    try:
        candidate = apply_frontmatter_contract(
            path,
            content,
            now=now or datetime.now(UTC),
            previous_content=f"\0audit-existing:{path}",
        )
    except ValueError:
        return FrontmatterAudit(
            path, "needs_review", tuple([*issues, "unsafe_to_migrate"]), created_at_unknown, None
        )
    return FrontmatterAudit(path, "needs_update", tuple(issues), created_at_unknown, candidate)
