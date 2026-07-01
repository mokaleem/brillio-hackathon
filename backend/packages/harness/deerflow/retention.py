from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from deerflow.config.paths import Paths
from deerflow.config.runtime_paths import runtime_home
from deerflow.runtime.events.store.base import RunEventStore


@dataclass(frozen=True)
class RetentionSweepResult:
    run_events_deleted: int = 0
    artifact_files_deleted: int = 0
    artifact_bytes_deleted: int = 0


def cutoff_for_days(days: int, *, now: datetime | None = None) -> datetime:
    if days < 1:
        raise ValueError("retention days must be at least 1")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)
    return current - timedelta(days=days)


async def sweep_run_events(store: RunEventStore, *, retention_days: int) -> int:
    return await store.delete_older_than(cutoff_for_days(retention_days))


async def sweep_generated_artifacts(
    *,
    retention_days: int,
    paths: Paths | None = None,
    extra_roots: list[Path] | None = None,
) -> tuple[int, int]:
    roots = _artifact_roots(paths or Paths(), extra_roots or [])
    cutoff = cutoff_for_days(retention_days)
    return await asyncio.to_thread(_delete_files_older_than, roots, cutoff)


async def sweep_retention_policy(
    *,
    store: RunEventStore,
    run_event_retention_days: int | None,
    artifact_retention_days: int | None,
    paths: Paths | None = None,
) -> RetentionSweepResult:
    events_deleted = 0
    files_deleted = 0
    bytes_deleted = 0
    if run_event_retention_days is not None:
        events_deleted = await sweep_run_events(store, retention_days=run_event_retention_days)
    if artifact_retention_days is not None:
        files_deleted, bytes_deleted = await sweep_generated_artifacts(retention_days=artifact_retention_days, paths=paths)
    return RetentionSweepResult(
        run_events_deleted=events_deleted,
        artifact_files_deleted=files_deleted,
        artifact_bytes_deleted=bytes_deleted,
    )


def _artifact_roots(paths: Paths, extra_roots: list[Path]) -> list[Path]:
    base_dir = paths.base_dir
    roots = [
        runtime_home() / "artifacts",
        base_dir / "artifacts",
        base_dir / "threads",
        base_dir / "users",
        *extra_roots,
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve(strict=False)
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _delete_files_older_than(roots: list[Path], cutoff: datetime) -> tuple[int, int]:
    files_deleted = 0
    bytes_deleted = 0
    for root in roots:
        if not root.exists():
            continue
        for file_path in sorted(root.rglob("*"), reverse=True):
            if not file_path.is_file() or not _is_generated_artifact_path(file_path):
                continue
            try:
                stat = file_path.stat()
            except OSError:
                continue
            modified_at = datetime.fromtimestamp(stat.st_mtime, UTC)
            if modified_at >= cutoff:
                continue
            try:
                size = stat.st_size
                file_path.unlink()
            except OSError:
                continue
            files_deleted += 1
            bytes_deleted += size
    return files_deleted, bytes_deleted


def _is_generated_artifact_path(path: Path) -> bool:
    parts = path.parts
    return "outputs" in parts or "artifacts" in parts
