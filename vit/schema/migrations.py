"""Migration runner.

Each migration is a pair (from_version, to_version, fn). `fn` takes the
project_dir and performs the upgrade (editing JSON files, renaming
things, etc.). Migrations are idempotent-on-success: running a migration
whose effects are already in place should not raise.

Errors abort the whole chain — we never half-migrate a repo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import CURRENT_SCHEMA_VERSION


@dataclass
class Migration:
    from_version: int
    to_version: int
    name: str
    apply: Callable[[str], None]


# Registry grows over time. Keep them small, pure, and testable.
_MIGRATIONS: List[Migration] = []


def register(migration: Migration) -> None:
    _MIGRATIONS.append(migration)


def _config_path(project_dir: str) -> str:
    return os.path.join(project_dir, ".vit", "config.json")


def read_schema_version(project_dir: str) -> int:
    """Return the recorded schema_version, or 1 for legacy projects.

    Pre-v0.1.1 configs only carried a string `version` field (the vit
    library version, not the schema version). We treat them as
    schema_version=1 since the on-disk shape didn't change yet.
    """
    path = _config_path(project_dir)
    if not os.path.exists(path):
        return CURRENT_SCHEMA_VERSION
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 1  # assume oldest; migrations will refresh the config
    sv = cfg.get("schema_version")
    if isinstance(sv, int) and sv > 0:
        return sv
    return 1


def write_schema_version(
    project_dir: str, version: int, vit_version: Optional[str] = None
) -> None:
    """Persist the post-migration schema_version (plus vit_version)."""
    path = _config_path(project_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cfg: dict = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except (OSError, json.JSONDecodeError):
            cfg = {}
    cfg["schema_version"] = int(version)
    if vit_version is not None:
        cfg["vit_version"] = vit_version
    cfg.setdefault("nle", "resolve")
    # Drop legacy top-level "version" — superseded by schema_version +
    # vit_version — so future readers don't get confused.
    cfg.pop("version", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
        f.write("\n")


def pending_migrations(current: int, target: int) -> List[Migration]:
    """Ordered chain of migrations from `current` to `target`."""
    chain: List[Migration] = []
    cursor = current
    while cursor < target:
        step = next((m for m in _MIGRATIONS if m.from_version == cursor), None)
        if step is None:
            raise RuntimeError(
                f"no migration path registered from schema v{cursor} "
                f"to v{target} (available: "
                f"{[(m.from_version, m.to_version) for m in _MIGRATIONS]})"
            )
        chain.append(step)
        cursor = step.to_version
    return chain


def migrate_if_needed(
    project_dir: str, *, vit_version: Optional[str] = None
) -> List[str]:
    """Bring a project up to CURRENT_SCHEMA_VERSION.

    Returns the list of migration names that were applied. Raises
    RuntimeError if the schema is newer than we support (a downgrade
    attempt) or if a migration can't be found.
    """
    current = read_schema_version(project_dir)
    target = CURRENT_SCHEMA_VERSION
    if current == target:
        return []
    if current > target:
        raise RuntimeError(
            f"project schema v{current} is newer than this vit version "
            f"supports (v{target}). Upgrade vit."
        )

    chain = pending_migrations(current, target)
    applied: List[str] = []
    for step in chain:
        step.apply(project_dir)
        applied.append(step.name)
    write_schema_version(project_dir, target, vit_version=vit_version)
    return applied
