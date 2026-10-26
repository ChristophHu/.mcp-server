from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from obsidian_mcp_server.paths import normalize_vault_path


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Boolean environment values must be true or false")


@dataclass(frozen=True)
class Settings:
    api_url: str
    api_key: str
    enable_writes: bool = False
    enable_delete: bool = False
    verify_tls: bool = True
    timeout_seconds: float = 10.0
    max_content_bytes: int = 1_048_576
    default_limit: int = 50
    max_limit: int = 200
    enable_frontmatter_migration: bool = False
    frontmatter_migration_root: str | None = None
    backend: str = "api"
    vault_path: Path | None = None
    daily_note_path_template: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if environ is None else environ
        raw_vault_path = values.get("OBSIDIAN_VAULT_PATH", "").strip()
        if raw_vault_path:
            vault_path = Path(raw_vault_path).expanduser().resolve(strict=True)
            if not vault_path.is_dir():
                raise ValueError("OBSIDIAN_VAULT_PATH must point to a directory")
            migration_enabled = _env_bool(
                values.get("OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION"), default=False
            )
            raw_migration_root = values.get("OBSIDIAN_FRONTMATTER_MIGRATION_ROOT", "").strip()
            migration_root = (
                normalize_vault_path(raw_migration_root) if raw_migration_root else None
            )
            if migration_enabled and migration_root is None:
                raise ValueError(
                    "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT is required when migration is enabled"
                )
            daily_template = values.get("OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE", "").strip() or None
            if daily_template is not None:
                if daily_template.count("{date}") != 1:
                    raise ValueError(
                        "OBSIDIAN_DAILY_NOTE_PATH_TEMPLATE must contain exactly one {date}"
                    )
                sample_path = normalize_vault_path(daily_template.replace("{date}", "2000-01-01"))
                if not sample_path.lower().endswith(".md"):
                    raise ValueError("Daily note path template must point to a Markdown note")
            return cls(
                api_url="",
                api_key="",
                enable_writes=_env_bool(values.get("OBSIDIAN_ENABLE_WRITES"), default=False),
                enable_frontmatter_migration=migration_enabled,
                frontmatter_migration_root=migration_root,
                backend="filesystem",
                vault_path=vault_path,
                daily_note_path_template=daily_template,
            )
        raw_url = values.get("OBSIDIAN_API_URL", "https://127.0.0.1:27124").strip()
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("OBSIDIAN_API_URL must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("OBSIDIAN_API_URL cannot contain a query or fragment")
        api_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
        migration_enabled = _env_bool(
            values.get("OBSIDIAN_ENABLE_FRONTMATTER_MIGRATION"), default=False
        )
        raw_migration_root = values.get("OBSIDIAN_FRONTMATTER_MIGRATION_ROOT", "").strip()
        migration_root = normalize_vault_path(raw_migration_root) if raw_migration_root else None
        if migration_enabled and migration_root is None:
            raise ValueError(
                "OBSIDIAN_FRONTMATTER_MIGRATION_ROOT is required when migration is enabled"
            )
        return cls(
            api_url=api_url,
            api_key=values.get("OBSIDIAN_API_KEY", ""),
            enable_writes=_env_bool(values.get("OBSIDIAN_ENABLE_WRITES"), default=False),
            enable_delete=_env_bool(values.get("OBSIDIAN_ENABLE_DELETE"), default=False),
            verify_tls=_env_bool(values.get("OBSIDIAN_VERIFY_TLS"), default=True),
            enable_frontmatter_migration=migration_enabled,
            frontmatter_migration_root=migration_root,
        )
