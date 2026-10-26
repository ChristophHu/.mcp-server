from __future__ import annotations

import errno
import os
import secrets
import stat
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from obsidian_mcp_server.config import Settings
from obsidian_mcp_server.frontmatter import split_frontmatter
from obsidian_mcp_server.links import extract_wikilinks
from obsidian_mcp_server.paths import normalize_vault_path
from obsidian_mcp_server.tags import extract_inline_tags


class LocalVault:
    """Obsidian vault adapter rooted at a local directory; writes are opt-in."""

    def __init__(self, settings: Settings) -> None:
        if settings.vault_path is None:
            raise ValueError("A local vault path is required")
        self.settings = settings
        self._root = settings.vault_path.resolve(strict=True)
        root_fd = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            root_stat = os.fstat(root_fd)
            if not stat.S_ISDIR(root_stat.st_mode):
                raise ValueError("Vault root must be a directory")
            self._root_identity = (root_stat.st_dev, root_stat.st_ino)
        finally:
            os.close(root_fd)

    @contextmanager
    def _directory(self, path: str | None):
        try:
            root_fd = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as exc:
            if isinstance(exc, FileNotFoundError):
                raise
            raise RuntimeError("Unable to access the configured vault") from exc
        descriptors = [root_fd]
        try:
            root_stat = os.fstat(root_fd)
            if (root_stat.st_dev, root_stat.st_ino) != self._root_identity:
                raise PermissionError("Configured vault root changed")
            if path:
                safe_path = normalize_vault_path(path)
                try:
                    for part in safe_path.split("/"):
                        fd = os.open(
                            part,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptors[-1],
                        )
                        descriptors.append(fd)
                except OSError as exc:
                    if isinstance(exc, (FileNotFoundError, PermissionError, ValueError)):
                        raise
                    if exc.errno == errno.ELOOP:
                        raise PermissionError(
                            "Symbolic links are not accessible in the vault"
                        ) from None
                    if exc.errno == errno.ENOTDIR:
                        raise PermissionError("Vault path component is not a directory") from None
                    raise RuntimeError("Unable to access the configured vault") from exc
            yield descriptors[-1]
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def _read(self, path: str) -> str:
        safe_path = normalize_vault_path(path)
        parts = safe_path.split("/")
        with self._directory("/".join(parts[:-1]) or None) as parent_fd:
            try:
                fd = os.open(
                    parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd
                )
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise PermissionError(
                        "Symbolic links are not accessible in the vault"
                    ) from None
                raise
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("Vault entry is not a regular file")
                data = bytearray()
                while True:
                    chunk = os.read(fd, min(65536, self.settings.max_content_bytes + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > self.settings.max_content_bytes:
                        raise ValueError("Note exceeds the configured content limit")
            finally:
                os.close(fd)
        try:
            return bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Vault note is not valid UTF-8 text") from exc

    def _entries(self, directory: str | None) -> list[str]:
        with self._directory(directory) as dir_fd:
            result: list[str] = []
            for name in os.listdir(dir_fd):
                if name.startswith("."):
                    continue
                try:
                    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    result.append(f"{name}/")
                elif stat.S_ISREG(info.st_mode):
                    result.append(name)
            return sorted(result)

    def _markdown_paths(self) -> list[str]:
        pending: list[str | None] = [None]
        notes: list[str] = []
        while pending:
            directory = pending.pop()
            prefix = f"{directory}/" if directory else ""
            for entry in self._entries(directory):
                if entry.endswith("/"):
                    pending.append(f"{directory}/{entry[:-1]}" if directory else entry[:-1])
                elif entry.lower().endswith(".md"):
                    notes.append(f"{prefix}{entry}")
        return sorted(notes)

    def _bounded_markdown_paths(self, limit: int) -> tuple[list[str], bool, list[dict[str, str]]]:
        pending: list[tuple[str | None, int]] = [(None, 0)]
        visited: set[str] = set()
        notes: list[str] = []
        errors: list[dict[str, str]] = []
        truncated = False
        while pending:
            if len(visited) >= 200:
                truncated = True
                break
            directory, depth = pending.pop(0)
            key = directory or ""
            if key in visited:
                continue
            visited.add(key)
            try:
                entries = self._entries(directory)
            except (OSError, RuntimeError, ValueError):
                errors.append({"path": key, "issue": "directory_unavailable"})
                continue
            for entry in entries:
                name = entry.rstrip("/")
                full_path = f"{directory}/{name}" if directory else name
                if entry.endswith("/"):
                    if depth >= 19:
                        truncated = True
                    else:
                        pending.append((full_path, depth + 1))
                elif entry.lower().endswith(".md"):
                    if len(notes) >= limit:
                        truncated = True
                        break
                    notes.append(full_path)
            if truncated:
                break
        return sorted(notes), truncated, errors

    async def check_consistency(self, limit: int = 50) -> dict[str, object]:
        if not 1 <= limit <= self.settings.max_limit:
            raise ValueError(f"limit must be between 1 and {self.settings.max_limit}")
        paths, truncated, errors = self._bounded_markdown_paths(limit)
        broken_links: list[dict[str, str]] = []
        notes_without_links: list[str] = []
        links_checked = 0
        link_targets_complete = not truncated and not any(
            error["issue"] == "directory_unavailable" for error in errors
        )
        for path in paths:
            try:
                links = extract_wikilinks(self._read(path))
            except (OSError, RuntimeError, ValueError):
                errors.append({"path": path, "issue": "note_unreadable"})
                continue
            if not links:
                notes_without_links.append(path)
            for link in links:
                links_checked += 1
                if link_targets_complete and self._resolve_link(link, path, paths) is None:
                    broken_links.append({"source": path, "target": link})
        return {
            "complete": not truncated and not errors,
            "truncated": truncated,
            "link_targets_complete": link_targets_complete,
            "scanned_count": len(paths),
            "links_checked": links_checked,
            "broken_links": broken_links,
            "notes_without_outgoing_links": notes_without_links,
            "errors": errors,
        }

    async def check_file_consistency(self, path: str) -> dict[str, object]:
        safe_path = normalize_vault_path(path)
        if not safe_path.lower().endswith(".md"):
            raise ValueError("Only Markdown notes can be checked")
        content = self._read(safe_path)
        outgoing = extract_wikilinks(content)
        paths, truncated, errors = self._bounded_markdown_paths(self.settings.max_limit)
        if safe_path not in paths:
            paths.append(safe_path)
            paths.sort()
        link_targets_complete = not truncated and not any(
            error["issue"] == "directory_unavailable" for error in errors
        )
        broken = (
            [link for link in outgoing if self._resolve_link(link, safe_path, paths) is None]
            if link_targets_complete
            else []
        )
        linked_notes = {safe_path}
        pending_notes = [safe_path]
        note_contents = {safe_path: content}
        recursive_broken_links: list[dict[str, str]] = []
        recursive_complete = link_targets_complete
        while pending_notes:
            source = pending_notes.pop(0)
            for link in extract_wikilinks(note_contents[source]):
                target = self._resolve_link(link, source, paths)
                if target is None:
                    if link_targets_complete:
                        recursive_broken_links.append({"source": source, "target": link})
                    continue
                if target in linked_notes:
                    continue
                if len(linked_notes) >= self.settings.max_limit:
                    recursive_complete = False
                    continue
                linked_notes.add(target)
                try:
                    note_contents[target] = self._read(target)
                except (OSError, RuntimeError, ValueError):
                    errors.append({"path": target, "issue": "note_unreadable"})
                    recursive_complete = False
                    continue
                pending_notes.append(target)
        backlinks: list[str] = []
        for source in paths:
            if source == safe_path:
                continue
            try:
                source_links = extract_wikilinks(self._read(source))
            except (OSError, RuntimeError, ValueError):
                errors.append({"path": source, "issue": "note_unreadable"})
                continue
            if any(self._resolve_link(link, source, paths) == safe_path for link in source_links):
                backlinks.append(source)
        backlinks.sort()
        errors = list({(error["path"], error["issue"]): error for error in errors}.values())
        backlinks_complete = not truncated and not errors
        return {
            "path": safe_path,
            "complete": backlinks_complete,
            "outgoing_links": outgoing,
            "link_targets_complete": link_targets_complete,
            "broken_links": broken,
            "backlinks": backlinks,
            "backlinks_complete": backlinks_complete,
            "errors": errors,
            "linked_notes": sorted(linked_notes),
            "recursive_broken_links": recursive_broken_links,
            "recursive_complete": recursive_complete and not errors,
        }

    async def get_status(self) -> dict[str, object]:
        return {
            "backend": "filesystem",
            "vault_available": True,
            "read_only": not self.settings.enable_writes,
        }

    async def get_note(self, path: str) -> str:
        return self._read(path)

    async def list_files(self, path: str | None = None) -> list[str]:
        return self._entries(path)

    async def get_note_json(self, path: str) -> dict[str, object]:
        content = self._read(path)
        metadata, body = split_frontmatter(content)
        return {"path": normalize_vault_path(path), "frontmatter": metadata or {}, "content": body}

    async def search_notes(self, query: str, *, context_length: int = 80) -> list[object]:
        lowered = query.casefold()
        hits: list[object] = []
        for path in self._markdown_paths():
            content = self._read(path)
            offset = content.casefold().find(lowered)
            if offset < 0:
                continue
            start = max(0, offset - context_length // 2)
            end = min(len(content), offset + len(query) + context_length // 2)
            hits.append({"filename": path, "matches": [content[start:end]]})
        return hits

    async def list_tags(self) -> list[object]:
        counts: Counter[str] = Counter()
        for path in self._markdown_paths():
            try:
                metadata, body = split_frontmatter(self._read(path))
            except ValueError:
                continue
            tags = (metadata or {}).get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            if isinstance(tags, list):
                note_tags = {tag for tag in tags if isinstance(tag, str)}
                counts.update(note_tags | extract_inline_tags(body))
        return [{"name": name, "count": count} for name, count in sorted(counts.items())]

    async def search_jsonlogic(self, tree: Mapping[str, object]) -> list[object]:
        clauses = tree.get("if")
        if not isinstance(clauses, list) or len(clauses) != 3:
            raise ValueError("Only note-link lookups are supported by the filesystem backend")
        condition = clauses[0]
        if not isinstance(condition, dict) or not isinstance(condition.get("=="), list):
            raise ValueError("Only note-link lookups are supported by the filesystem backend")
        comparison = condition["=="]
        if len(comparison) != 2 or comparison[0] != {"var": "path"}:
            raise ValueError("Only note-link lookups are supported by the filesystem backend")
        requested_target = normalize_vault_path(comparison[1])
        markdown_paths = self._markdown_paths()
        target = next(
            (path for path in markdown_paths if path.casefold() == requested_target.casefold()),
            requested_target,
        )
        outgoing = extract_wikilinks(self._read(target))
        backlinks: list[str] = []
        unresolved = [
            link for link in outgoing if self._resolve_link(link, target, markdown_paths) is None
        ]
        for path in markdown_paths:
            if path == target:
                continue
            if any(
                self._resolve_link(link, path, markdown_paths) == target
                for link in extract_wikilinks(self._read(path))
            ):
                backlinks.append(path)
        return [{"filename": target, "result": [outgoing, backlinks, unresolved]}]

    def _target_exists(self, link: str) -> bool:
        return link == "" or self._resolve_link(link, "", self._markdown_paths()) is not None

    @classmethod
    def _resolve_link(cls, link: str, source_path: str, markdown_paths: list[str]) -> str | None:
        candidate = link.split("#", 1)[0].split("^", 1)[0].strip()
        if not candidate:
            return None
        candidate = candidate.lstrip("/")
        candidates = [candidate]
        if "/" not in candidate and "/" in source_path:
            candidates.insert(0, f"{source_path.rsplit('/', 1)[0]}/{candidate}")
        for possible in candidates:
            try:
                safe = normalize_vault_path(possible)
            except ValueError:
                continue
            if not safe.lower().endswith(".md"):
                safe += ".md"
            resolved = next(
                (path for path in markdown_paths if path.casefold() == safe.casefold()),
                None,
            )
            if resolved is not None:
                return resolved
            normalized = cls._link_key(safe)
            matches = [path for path in markdown_paths if cls._link_key(path) == normalized]
            if len(matches) == 1:
                return matches[0]
        if "/" not in candidate:
            stem = cls._link_key(Path(candidate).stem)
            matches = [path for path in markdown_paths if cls._link_key(Path(path).stem) == stem]
            if len(matches) == 1:
                return matches[0]
        return None

    @staticmethod
    def _link_key(value: str) -> str:
        return "/".join(
            " ".join(part.replace("_", " ").casefold().split()) for part in value.split("/")
        )

    async def write_note(
        self,
        path: str,
        content: str,
        *,
        overwrite: bool = False,
        frontmatter_migration: bool = False,
    ) -> None:
        safe_path = normalize_vault_path(path)
        if frontmatter_migration:
            migration_root = self.settings.frontmatter_migration_root
            allowed = self.settings.enable_frontmatter_migration and migration_root is not None
            if allowed and migration_root is not None:
                safe_root = normalize_vault_path(migration_root)
                allowed = safe_path == safe_root or safe_path.startswith(f"{safe_root}/")
            if not allowed:
                raise PermissionError("Migration writes are outside the configured scope")
        elif not self.settings.enable_writes:
            raise PermissionError("Local filesystem backend is read-only")
        elif overwrite:
            raise PermissionError(
                "Overwriting notes requires trusted target-bound approval; no approval "
                "provider is configured"
            )
        encoded = content.encode("utf-8")
        if len(encoded) > self.settings.max_content_bytes:
            raise ValueError("Note content exceeds the configured content limit")
        parts = safe_path.split("/")
        with self._directory("/".join(parts[:-1]) or None) as parent_fd:
            temporary_name: str | None = None
            temporary_fd: int | None = None
            try:
                for _attempt in range(10):
                    candidate = f".{parts[-1]}.{secrets.token_hex(8)}.tmp"
                    try:
                        temporary_fd = os.open(
                            candidate,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600,
                            dir_fd=parent_fd,
                        )
                    except FileExistsError:
                        continue
                    temporary_name = candidate
                    break
                else:
                    raise RuntimeError("Unable to allocate a temporary vault file")

                view = memoryview(encoded)
                while view:
                    written = os.write(temporary_fd, view)
                    if written <= 0:
                        raise OSError("Unable to write the complete note")
                    view = view[written:]
                os.fsync(temporary_fd)
                os.close(temporary_fd)
                temporary_fd = None

                if overwrite:
                    try:
                        target_fd = os.open(
                            parts[-1],
                            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                            dir_fd=parent_fd,
                        )
                    except FileNotFoundError:
                        pass
                    except OSError as exc:
                        if exc.errno == errno.ELOOP:
                            raise PermissionError(
                                "Symbolic links are not accessible in the vault"
                            ) from None
                        raise
                    else:
                        try:
                            if not stat.S_ISREG(os.fstat(target_fd).st_mode):
                                raise ValueError("Vault entry is not a regular file")
                        finally:
                            os.close(target_fd)
                    os.replace(
                        temporary_name,
                        parts[-1],
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                    )
                else:
                    os.link(
                        temporary_name,
                        parts[-1],
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                    os.unlink(temporary_name, dir_fd=parent_fd)
                temporary_name = None
                os.fsync(parent_fd)
            finally:
                if temporary_fd is not None:
                    os.close(temporary_fd)
                if temporary_name is not None:
                    try:
                        os.unlink(temporary_name, dir_fd=parent_fd)
                    except FileNotFoundError:
                        pass

    def _daily_note_path(self, period: str, note_date: date) -> str:
        if period != "daily":
            raise ValueError("Only daily periodic notes are supported by the filesystem backend")
        template = self.settings.daily_note_path_template
        if template is None:
            raise RuntimeError("Periodic notes require a configured local path template")
        if template.count("{date}") != 1:
            raise ValueError("Daily note path template must contain exactly one {date}")
        path = normalize_vault_path(template.replace("{date}", note_date.isoformat()))
        if not path.lower().endswith(".md"):
            raise ValueError("Daily note path template must point to a Markdown note")
        return path

    async def append_periodic_note(self, period: str, note_date: date, content: str) -> None:
        await self.write_note(self._daily_note_path(period, note_date), content, overwrite=False)

    async def replace_periodic_note(self, period: str, note_date: date, content: str) -> None:
        await self.write_note(self._daily_note_path(period, note_date), content, overwrite=True)

    async def get_periodic_note(self, period: str, note_date: date) -> str:
        return self._read(self._daily_note_path(period, note_date))

    async def open_in_ui(self, *_: Any, **__: Any) -> None:
        raise RuntimeError("Opening notes in the Obsidian UI requires the Local REST API backend")
