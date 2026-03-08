"""Core sync engine for project-local skills and agents."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import frontmatter  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from meridian.lib.sync.cache import SourceResolution, resolve_source
from meridian.lib.sync.config import SyncSourceConfig
from meridian.lib.sync.hash import compute_item_hash
from meridian.lib.sync.lock import SyncLockEntry, SyncLockFile, read_lock_file, write_lock_file

ItemKind = Literal["skill", "agent"]
SyncAction = Literal[
    "installed",
    "updated",
    "skipped",
    "reinstalled",
    "conflict",
    "removed",
    "orphan_warned",
]
_FRONTMATTER_PATTERN = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n)?", re.DOTALL)


class SyncItemAction(BaseModel):
    """One item's sync result."""

    model_config = ConfigDict(frozen=True)

    item_key: str
    item_kind: ItemKind
    source_name: str
    action: SyncAction
    reason: str
    dest_path: str


class SyncResult(BaseModel):
    """Aggregate sync result."""

    model_config = ConfigDict(frozen=True)

    actions: tuple[SyncItemAction, ...]
    errors: tuple[str, ...]


def discover_items(source: SyncSourceConfig, source_dir: Path) -> list[tuple[str, str, str]]:
    """Discover configured skill and agent items for one resolved source."""

    discovered: list[tuple[str, str, str]] = []
    discovered.extend(
        _discover_kind_items(
            source=source,
            source_dir=source_dir,
            item_kind="skill",
            include=source.skills,
            exclude=source.exclude_skills,
        )
    )
    discovered.extend(
        _discover_kind_items(
            source=source,
            source_dir=source_dir,
            item_kind="agent",
            include=source.agents,
            exclude=source.exclude_agents,
        )
    )
    return discovered


def check_cross_source_collisions(all_items: list[tuple[str, str, str, str]]) -> None:
    """Reject items whose destination name would collide across sources."""

    seen: dict[tuple[str, str], tuple[str, str]] = {}
    for item_kind, local_name, source_name_label, source_value in all_items:
        key = (item_kind, local_name)
        previous = seen.get(key)
        if previous is None:
            seen[key] = (source_name_label, source_value)
            continue

        previous_label, previous_value = previous
        raise ValueError(
            f"Name collision for {item_kind} '{local_name}': "
            f"source '{previous_label}' ({previous_value}) and "
            f"source '{source_name_label}' ({source_value})."
        )


def sync_items(
    *,
    repo_root: Path,
    sources: tuple[SyncSourceConfig, ...] | list[SyncSourceConfig],
    sync_cache_dir: Path,
    sync_lock_path: Path,
    locked_commits: dict[str, str | None] | None = None,
    upgrade: bool = False,
    force: bool = False,
    dry_run: bool = False,
    prune: bool = False,
    source_filter: str | None = None,
) -> SyncResult:
    """Resolve, diff, and sync configured items into `.agents/`."""

    selected_sources = list(sources)
    if source_filter is not None:
        selected_sources = [source for source in selected_sources if source.name == source_filter]
        if not selected_sources:
            raise ValueError(f"Sync source '{source_filter}' not found.")

    actions: list[SyncItemAction] = []
    errors: list[str] = []
    resolved_sources: list[tuple[SyncSourceConfig, SourceResolution, list[tuple[str, str, str]]]] = []

    for source in selected_sources:
        try:
            resolution = resolve_source(
                source,
                sync_cache_dir=sync_cache_dir,
                repo_root=repo_root,
                locked_commit=None if locked_commits is None else locked_commits.get(source.name),
                upgrade=upgrade,
            )
        except Exception as exc:
            errors.append(f"Source '{source.name}' could not be resolved: {exc}")
            continue

        items = discover_items(source, resolution.source_dir)
        resolved_sources.append((source, resolution, items))

    collision_inputs = [
        (cast("ItemKind", item_kind), local_name, source.name, resolution.source_value)
        for source, resolution, items in resolved_sources
        for item_kind, _, local_name in items
    ]
    check_cross_source_collisions(collision_inputs)

    blocked_item_keys: set[str] = set()
    for source, _, items in resolved_sources:
        for item_kind, _, local_name in items:
            normalized_kind = cast("ItemKind", item_kind)
            item_key = _item_key(normalized_kind, local_name)
            claude_path = _claude_path_for_item(repo_root, normalized_kind, local_name)
            agents_dest = _dest_path_for_item(repo_root, normalized_kind, local_name)
            if not _path_exists(claude_path):
                continue
            if _is_sync_managed_symlink(claude_path, agents_dest):
                continue
            if force:
                continue

            blocked_item_keys.add(item_key)
            actions.append(
                SyncItemAction(
                    item_key=item_key,
                    item_kind=normalized_kind,
                    source_name=source.name,
                    action="conflict",
                    reason=(
                        f"Unmanaged Claude path exists at {claude_path.relative_to(repo_root).as_posix()}."
                    ),
                    dest_path=_dest_path_string(repo_root, agents_dest),
                )
            )

    lock = read_lock_file(sync_lock_path)

    desired_items = {
        _item_key(cast("ItemKind", item_kind), local_name)
        for _, _, items in resolved_sources
        for item_kind, _, local_name in items
    }

    for source, resolution, items in resolved_sources:
        for item_kind, source_item_name, local_name in items:
            normalized_kind = cast("ItemKind", item_kind)
            item_key = _item_key(normalized_kind, local_name)
            if item_key in blocked_item_keys:
                continue

            try:
                if dry_run:
                    actions.append(
                        _preview_item_action(
                            item_kind=normalized_kind,
                            source_name=source.name,
                            source_item_name=source_item_name,
                            local_name=local_name,
                            source_dir=resolution.source_dir,
                            repo_root=repo_root,
                            lock=lock,
                            force=force,
                        )
                    )
                else:
                    action = _apply_item(
                        item_kind=normalized_kind,
                        source_name=source.name,
                        source_item_name=source_item_name,
                        local_name=local_name,
                        source_dir=resolution.source_dir,
                        repo_root=repo_root,
                        resolution=resolution,
                        lock=lock,
                        force=force,
                    )
                    if action.action not in {"skipped", "conflict"}:
                        entry = lock.items[action.item_key]
                        lock.items[action.item_key] = entry.model_copy(
                            update={"requested_ref": source.ref}
                        )
                    actions.append(action)
            except Exception as exc:
                errors.append(
                    f"Item '{item_key}' from source '{source.name}' could not be synced: {exc}"
                )

    orphan_actions: list[SyncItemAction] = []
    if prune:
        if not dry_run:
            orphan_actions = _prune_orphans(
                repo_root=repo_root,
                lock=lock,
                desired_items=desired_items,
                force=force,
            )
        else:
            orphan_actions = _preview_orphans(
                repo_root=repo_root,
                lock=lock,
                desired_items=desired_items,
                force=force,
            )
    else:
        orphan_actions = _warn_orphans(repo_root=repo_root, lock=lock, desired_items=desired_items)
    actions.extend(orphan_actions)

    if not dry_run:
        write_lock_file(sync_lock_path, lock)

    return SyncResult(actions=tuple(actions), errors=tuple(errors))


def _apply_item(
    *,
    item_kind: str,
    source_name: str,
    source_item_name: str,
    local_name: str,
    source_dir: Path,
    repo_root: Path,
    resolution: SourceResolution,
    lock: SyncLockFile,
    force: bool,
) -> SyncItemAction:
    """Apply one item from a resolved source."""

    normalized_kind = cast("ItemKind", item_kind)
    item_key = _item_key(normalized_kind, local_name)
    dest_path = _dest_path_for_item(repo_root, normalized_kind, local_name)
    source_path = _source_path_for_item(source_dir, normalized_kind, source_item_name)
    staged_path = _stage_source_item(
        source_path=source_path,
        item_kind=normalized_kind,
        dest_path=dest_path,
    )

    try:
        source_hash = compute_item_hash(staged_path, normalized_kind)
        lock_entry = lock.items.get(item_key)
        local_hash = (
            compute_item_hash(dest_path, normalized_kind) if _path_exists(dest_path) else None
        )
        action_name, reason = _decide_action(
            dest_exists=_path_exists(dest_path),
            lock_entry=lock_entry,
            local_hash=local_hash,
            source_hash=source_hash,
            force=force,
        )

        if action_name == "skipped":
            return SyncItemAction(
                item_key=item_key,
                item_kind=normalized_kind,
                source_name=source_name,
                action="skipped",
                reason=reason,
                dest_path=_dest_path_string(repo_root, dest_path),
            )

        if action_name == "conflict":
            return SyncItemAction(
                item_key=item_key,
                item_kind=normalized_kind,
                source_name=source_name,
                action="conflict",
                reason=reason,
                dest_path=_dest_path_string(repo_root, dest_path),
            )

        if action_name == "updated":
            _prepare_updated_stage(
                item_kind=normalized_kind,
                staged_path=staged_path,
                dest_path=dest_path,
            )
            source_hash = compute_item_hash(staged_path, normalized_kind)

        _prepare_claude_destination(
            repo_root=repo_root,
            item_kind=normalized_kind,
            local_name=local_name,
            force=force,
        )
        _atomic_swap(staged_path=staged_path, dest_path=dest_path)
        _create_claude_symlink(repo_root, normalized_kind, local_name)
        _update_lock_entry(
            lock=lock,
            item_key=item_key,
            source_name=source_name,
            source_item_name=source_item_name,
            local_name=local_name,
            resolution=resolution,
            item_kind=normalized_kind,
            repo_root=repo_root,
            tree_hash=source_hash,
        )

        return SyncItemAction(
            item_key=item_key,
            item_kind=normalized_kind,
            source_name=source_name,
            action=cast("SyncAction", action_name),
            reason=reason,
            dest_path=_dest_path_string(repo_root, dest_path),
        )
    finally:
        if _path_exists(staged_path):
            _remove_path(staged_path)


def _prune_orphans(
    *,
    repo_root: Path,
    lock: SyncLockFile,
    desired_items: set[str],
    force: bool,
) -> list[SyncItemAction]:
    """Remove or warn about lock entries that are no longer desired."""

    actions: list[SyncItemAction] = []
    for item_key, entry in list(lock.items.items()):
        if item_key in desired_items:
            continue

        local_name = _local_name_from_item_key(item_key)
        dest_path = repo_root / entry.dest_path
        current_hash = (
            compute_item_hash(dest_path, entry.item_kind) if _path_exists(dest_path) else None
        )
        matches_lock = current_hash == entry.tree_hash if current_hash is not None else True
        claude_path = _claude_path_for_item(repo_root, entry.item_kind, local_name)

        if matches_lock or force:
            if _path_exists(dest_path):
                _remove_path(dest_path)
            if _path_exists(claude_path) and (
                force or _is_sync_managed_symlink(claude_path, _dest_path_for_item(repo_root, entry.item_kind, local_name))
            ):
                _remove_path(claude_path)
            actions.append(
                SyncItemAction(
                    item_key=item_key,
                    item_kind=entry.item_kind,
                    source_name=entry.source_name,
                    action="removed",
                    reason=(
                        "Removed orphaned managed item."
                        if matches_lock
                        else "Force removed orphaned managed item with local edits."
                    ),
                    dest_path=entry.dest_path,
                )
            )
        else:
            actions.append(
                SyncItemAction(
                    item_key=item_key,
                    item_kind=entry.item_kind,
                    source_name=entry.source_name,
                    action="orphan_warned",
                    reason="Orphaned managed item kept because local content was edited.",
                    dest_path=entry.dest_path,
                )
            )

        del lock.items[item_key]

    return actions


def _source_path_for_item(source_dir: Path, item_kind: str, source_item_name: str) -> Path:
    """Return the on-source path for a discovered item."""

    if item_kind == "skill":
        return source_dir / "skills" / source_item_name
    if item_kind == "agent":
        return source_dir / "agents" / f"{source_item_name}.md"
    raise ValueError(f"Unsupported item kind: {item_kind}")


def _dest_path_for_item(repo_root: Path, item_kind: str, local_name: str) -> Path:
    """Return the canonical `.agents/` destination path for an item."""

    if item_kind == "skill":
        return repo_root / ".agents" / "skills" / local_name
    if item_kind == "agent":
        return repo_root / ".agents" / "agents" / f"{local_name}.md"
    raise ValueError(f"Unsupported item kind: {item_kind}")


def _claude_path_for_item(repo_root: Path, item_kind: str, local_name: str) -> Path:
    """Return the Claude discoverability symlink path for an item."""

    if item_kind == "skill":
        return repo_root / ".claude" / "skills" / local_name
    if item_kind == "agent":
        return repo_root / ".claude" / "agents" / f"{local_name}.md"
    raise ValueError(f"Unsupported item kind: {item_kind}")


def _create_claude_symlink(repo_root: Path, item_kind: str, local_name: str) -> None:
    """Create the per-item relative symlink into `.agents/` for Claude Code."""

    normalized_kind = cast("ItemKind", item_kind)
    claude_path = _claude_path_for_item(repo_root, normalized_kind, local_name)
    agents_dest = _dest_path_for_item(repo_root, normalized_kind, local_name)
    claude_path.parent.mkdir(parents=True, exist_ok=True)
    if _is_sync_managed_symlink(claude_path, agents_dest):
        return
    if _path_exists(claude_path):
        raise ValueError(f"Unmanaged Claude path exists: {claude_path}")

    relative_target = os.path.relpath(agents_dest, start=claude_path.parent)
    claude_path.symlink_to(relative_target)


def _is_sync_managed_symlink(claude_path: Path, agents_dest: Path) -> bool:
    """Return whether a Claude path is the expected sync-managed symlink."""

    return claude_path.is_symlink() and claude_path.resolve(strict=False) == agents_dest.resolve(
        strict=False
    )


def _splice_frontmatter(local_text: str, source_text: str) -> str:
    """Preserve local frontmatter while replacing the body with source content."""

    frontmatter.loads(local_text)
    frontmatter.loads(source_text)
    local_frontmatter = _frontmatter_block(local_text)
    if local_frontmatter is None:
        return _frontmatter_body(source_text)
    return local_frontmatter + _frontmatter_body(source_text)


def _discover_kind_items(
    *,
    source: SyncSourceConfig,
    source_dir: Path,
    item_kind: ItemKind,
    include: tuple[str, ...] | None,
    exclude: tuple[str, ...],
) -> list[tuple[str, str, str]]:
    if include == ():
        return []

    discovered_names = _scan_source_names(source_dir, item_kind)
    if include is None:
        filtered_names = discovered_names
    else:
        include_set = set(include)
        filtered_names = [name for name in discovered_names if name in include_set]

    exclude_set = set(exclude)
    items = [
        (
            item_kind,
            source_name,
            source.rename.get(source_name, source_name),
        )
        for source_name in filtered_names
        if source_name not in exclude_set
    ]
    return items


def _scan_source_names(source_dir: Path, item_kind: ItemKind) -> list[str]:
    if item_kind == "skill":
        skills_dir = source_dir / "skills"
        if not skills_dir.is_dir():
            return []
        return sorted(
            child.name
            for child in skills_dir.iterdir()
            if child.is_dir() and (child / "SKILL.md").is_file()
        )

    agents_dir = source_dir / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(path.stem for path in agents_dir.glob("*.md") if path.is_file())


def _preview_item_action(
    *,
    item_kind: ItemKind,
    source_name: str,
    source_item_name: str,
    local_name: str,
    source_dir: Path,
    repo_root: Path,
    lock: SyncLockFile,
    force: bool,
) -> SyncItemAction:
    item_key = _item_key(item_kind, local_name)
    dest_path = _dest_path_for_item(repo_root, item_kind, local_name)
    source_path = _source_path_for_item(source_dir, item_kind, source_item_name)
    action_name, reason = _decide_action(
        dest_exists=_path_exists(dest_path),
        lock_entry=lock.items.get(item_key),
        local_hash=compute_item_hash(dest_path, item_kind) if _path_exists(dest_path) else None,
        source_hash=compute_item_hash(source_path, item_kind),
        force=force,
    )
    return SyncItemAction(
        item_key=item_key,
        item_kind=item_kind,
        source_name=source_name,
        action=cast("SyncAction", action_name),
        reason=reason,
        dest_path=_dest_path_string(repo_root, dest_path),
    )


def _preview_orphans(
    *,
    repo_root: Path,
    lock: SyncLockFile,
    desired_items: set[str],
    force: bool,
) -> list[SyncItemAction]:
    actions: list[SyncItemAction] = []
    for item_key, entry in lock.items.items():
        if item_key in desired_items:
            continue
        dest_path = repo_root / entry.dest_path
        current_hash = (
            compute_item_hash(dest_path, entry.item_kind) if _path_exists(dest_path) else None
        )
        action = (
            "removed"
            if force or current_hash in {None, entry.tree_hash}
            else "orphan_warned"
        )
        reason = (
            "Would remove orphaned managed item."
            if action == "removed"
            else "Would keep orphaned managed item because local content was edited."
        )
        actions.append(
            SyncItemAction(
                item_key=item_key,
                item_kind=entry.item_kind,
                source_name=entry.source_name,
                action=action,
                reason=reason,
                dest_path=entry.dest_path,
            )
        )
    return actions


def _warn_orphans(
    *,
    repo_root: Path,
    lock: SyncLockFile,
    desired_items: set[str],
) -> list[SyncItemAction]:
    actions: list[SyncItemAction] = []
    for item_key, entry in lock.items.items():
        if item_key in desired_items:
            continue
        actions.append(
            SyncItemAction(
                item_key=item_key,
                item_kind=entry.item_kind,
                source_name=entry.source_name,
                action="orphan_warned",
                reason="Orphaned managed item remains; rerun with --prune to remove it.",
                dest_path=(repo_root / entry.dest_path).relative_to(repo_root).as_posix(),
            )
        )
    return actions


def _decide_action(
    *,
    dest_exists: bool,
    lock_entry: SyncLockEntry | None,
    local_hash: str | None,
    source_hash: str,
    force: bool,
) -> tuple[Literal["installed", "updated", "skipped", "reinstalled", "conflict"], str]:
    if not dest_exists and lock_entry is None:
        return "installed", "Installed new managed item."

    if dest_exists and lock_entry is None:
        if force:
            return "reinstalled", "Force overwrote unmanaged destination."
        return "conflict", "Destination exists but is not managed by sync."

    if lock_entry is None:
        raise ValueError("Sync decision is missing a lock entry for a managed item.")

    if not dest_exists:
        return "reinstalled", "Reinstalled missing managed item."

    if local_hash is None:
        raise ValueError("Local hash is required when destination exists.")

    local_matches = local_hash == lock_entry.tree_hash
    source_matches = source_hash == lock_entry.tree_hash

    if local_matches and source_matches:
        return "skipped", "Already in sync."
    if local_matches and not source_matches:
        return "updated", "Upstream body changed; preserved local frontmatter."
    if not local_matches and source_matches:
        return "skipped", "Local body changed; upstream content is unchanged."
    if force:
        return "reinstalled", "Force overwrote divergent local changes."
    return "conflict", "Local and upstream bodies both changed."


def _stage_source_item(*, source_path: Path, item_kind: ItemKind, dest_path: Path) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if item_kind == "skill":
        staged_dir = dest_path.parent / f".{dest_path.name}.tmp-{uuid.uuid4().hex}"
        _copy_skill_tree(source_path, staged_dir)
        return staged_dir

    if source_path.is_symlink():
        raise ValueError(f"Symlinks are not supported: {source_path}")
    file_descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{dest_path.stem}.tmp-",
        suffix=dest_path.suffix,
        dir=dest_path.parent,
    )
    os.close(file_descriptor)
    staged_file = Path(staged_name)
    shutil.copy2(source_path, staged_file)
    return staged_file


def _copy_skill_tree(source_dir: Path, dest_dir: Path) -> None:
    source_root = source_dir.resolve()
    if source_dir.is_symlink():
        raise ValueError(f"Symlinks are not supported: {source_dir}")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Skill source directory not found: {source_dir}")

    dest_dir.mkdir(parents=True, exist_ok=False)
    for root, dirnames, filenames in os.walk(source_dir, topdown=True, followlinks=False):
        root_path = Path(root)
        _ensure_safe_source_path(source_dir, source_root, root_path)
        relative_root = root_path.relative_to(source_dir)
        target_root = dest_dir / relative_root
        target_root.mkdir(parents=True, exist_ok=True)

        retained_dirs: list[str] = []
        for dirname in sorted(dirnames):
            if dirname == ".git":
                continue
            child = root_path / dirname
            _ensure_safe_source_path(source_dir, source_root, child)
            retained_dirs.append(dirname)
            (dest_dir / child.relative_to(source_dir)).mkdir(parents=True, exist_ok=True)
        dirnames[:] = retained_dirs

        for filename in sorted(filenames):
            child = root_path / filename
            _ensure_safe_source_path(source_dir, source_root, child)
            target = dest_dir / child.relative_to(source_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def _ensure_safe_source_path(source_dir: Path, source_root: Path, candidate: Path) -> None:
    if candidate.is_symlink():
        relative_path = candidate.relative_to(source_dir).as_posix()
        raise ValueError(f"Symlinks are not supported: {relative_path}")
    relative_path = candidate.relative_to(source_dir)
    if any(part == ".." for part in relative_path.parts):
        raise ValueError(f"Path traversal is not supported: {relative_path.as_posix()}")
    if not candidate.resolve().is_relative_to(source_root):
        raise ValueError(f"Path traversal is not supported: {relative_path.as_posix()}")


def _prepare_updated_stage(*, item_kind: ItemKind, staged_path: Path, dest_path: Path) -> None:
    local_entry = _entry_point_path(dest_path, item_kind)
    source_entry = _entry_point_path(staged_path, item_kind)
    if not local_entry.is_file():
        return
    source_entry.write_text(
        _splice_frontmatter(
            local_entry.read_text(encoding="utf-8"),
            source_entry.read_text(encoding="utf-8"),
        ),
        encoding="utf-8",
    )


def _prepare_claude_destination(
    *,
    repo_root: Path,
    item_kind: ItemKind,
    local_name: str,
    force: bool,
) -> None:
    claude_path = _claude_path_for_item(repo_root, item_kind, local_name)
    agents_dest = _dest_path_for_item(repo_root, item_kind, local_name)
    if not _path_exists(claude_path):
        return
    if _is_sync_managed_symlink(claude_path, agents_dest):
        return
    if not force:
        raise ValueError(f"Unmanaged Claude path exists: {claude_path}")
    _remove_path(claude_path)


def _atomic_swap(*, staged_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = dest_path.parent / f".{dest_path.name}.bak-{uuid.uuid4().hex}"
    dest_existed = _path_exists(dest_path)

    try:
        if dest_existed:
            os.rename(dest_path, backup_path)
        os.rename(staged_path, dest_path)
    except Exception:
        if dest_existed and _path_exists(backup_path) and not _path_exists(dest_path):
            os.rename(backup_path, dest_path)
        raise
    else:
        if _path_exists(backup_path):
            _remove_path(backup_path)


def _update_lock_entry(
    *,
    lock: SyncLockFile,
    item_key: str,
    source_name: str,
    source_item_name: str,
    local_name: str,
    resolution: SourceResolution,
    item_kind: ItemKind,
    repo_root: Path,
    tree_hash: str,
) -> None:
    lock.items[item_key] = SyncLockEntry(
        source_name=source_name,
        source_type=resolution.source_type,
        source_value=resolution.source_value,
        source_item_name=source_item_name,
        requested_ref=None,
        locked_commit=resolution.resolved_commit,
        item_kind=item_kind,
        dest_path=_dest_path_string(repo_root, _dest_path_for_item(repo_root, item_kind, local_name)),
        tree_hash=tree_hash,
        synced_at=_utc_timestamp(),
    )


def _entry_point_path(item_path: Path, item_kind: ItemKind) -> Path:
    if item_kind == "skill":
        return item_path / "SKILL.md"
    return item_path


def _frontmatter_block(text: str) -> str | None:
    match = _FRONTMATTER_PATTERN.match(text)
    return None if match is None else match.group(0)


def _frontmatter_body(text: str) -> str:
    match = _FRONTMATTER_PATTERN.match(text)
    if match is None:
        return text
    return text[match.end() :]


def _item_key(item_kind: ItemKind, local_name: str) -> str:
    return f"{item_kind}s/{local_name}"


def _local_name_from_item_key(item_key: str) -> str:
    _, _, local_name = item_key.partition("/")
    return local_name


def _dest_path_string(repo_root: Path, dest_path: Path) -> str:
    return dest_path.relative_to(repo_root).as_posix()


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
