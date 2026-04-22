"""vit matrix — per-deliverable variant manager.

Scenario: one hero cut on `main`. From it you derive N deliverable
variants (9x16 Reel, 1x1 Feed, 16x9 YouTube, 30s/60s/90s lengths, ...).
Each variant lives on its own git branch. When `main` moves forward,
every variant is "behind" until re-derived.

This module provides:
  - init:     write .vit/variants.json listing the known variant branches
  - add:      register a new variant
  - remove:   forget a variant (branch stays, registration dropped)
  - status:   table of variants with commits-behind + last-rederive-at
  - rederive: replay main's new commits onto a variant via git cherry-pick

Variants are plain git branches — no new data format. Registration is
purely a UX layer so `vit matrix status` can show the grid at a glance.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .core import (
    GitError,
    _run,
    find_project_root,
    git_checkout,
    git_current_branch,
    git_list_branches,
)


VARIANTS_FILE = os.path.join(".vit", "variants.json")


@dataclass
class Variant:
    name: str
    parent: str = "main"
    format: str = ""  # freeform label: "9x16", "1x1-30s", etc.
    last_rederive_at: float = 0.0  # unix timestamp; 0 = never
    last_rederive_hash: str = ""  # parent hash at last successful rederive

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Variant":
        return cls(
            name=d.get("name", ""),
            parent=d.get("parent", "main"),
            format=d.get("format", ""),
            last_rederive_at=float(d.get("last_rederive_at", 0.0)),
            last_rederive_hash=d.get("last_rederive_hash", ""),
        )


@dataclass
class MatrixConfig:
    variants: Dict[str, Variant] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"variants": {k: v.to_dict() for k, v in self.variants.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "MatrixConfig":
        raw = d.get("variants", {}) or {}
        return cls(variants={k: Variant.from_dict(v) for k, v in raw.items()})


def _config_path(project_dir: str) -> str:
    return os.path.join(project_dir, VARIANTS_FILE)


def load_config(project_dir: str) -> MatrixConfig:
    path = _config_path(project_dir)
    if not os.path.exists(path):
        return MatrixConfig()
    try:
        with open(path) as f:
            return MatrixConfig.from_dict(json.load(f))
    except (OSError, json.JSONDecodeError):
        return MatrixConfig()


def save_config(project_dir: str, cfg: MatrixConfig) -> None:
    path = _config_path(project_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg.to_dict(), f, indent=2, sort_keys=True)


def _rev_parse(project_dir: str, ref: str) -> Optional[str]:
    result = _run(["rev-parse", ref], cwd=project_dir, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _commits_behind(project_dir: str, branch: str, parent: str) -> int:
    """How many commits on parent are not yet on branch."""
    result = _run(
        ["rev-list", "--count", f"{branch}..{parent}"],
        cwd=project_dir,
        check=False,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def cmd_init(project_dir: str) -> None:
    """Create an empty variants.json if none exists."""
    if os.path.exists(_config_path(project_dir)):
        print("  Matrix already initialized.")
        return
    save_config(project_dir, MatrixConfig())
    print(f"  Initialized matrix config at {VARIANTS_FILE}")


def cmd_add(
    project_dir: str,
    name: str,
    *,
    parent: str = "main",
    format_label: str = "",
    create_branch: bool = True,
) -> None:
    """Register a variant and optionally create its branch off `parent`."""
    cfg = load_config(project_dir)
    if name in cfg.variants:
        print(f"  Variant '{name}' already registered.")
        return

    branches = set(git_list_branches(project_dir))
    if create_branch and name not in branches:
        if parent not in branches:
            print(f"  Parent branch '{parent}' not found.")
            return
        current = git_current_branch(project_dir)
        try:
            git_checkout(project_dir, parent)
            _run(["checkout", "-b", name], cwd=project_dir)
        finally:
            try:
                git_checkout(project_dir, current)
            except GitError:
                pass
        print(f"  Created branch '{name}' from '{parent}'.")

    cfg.variants[name] = Variant(
        name=name,
        parent=parent,
        format=format_label,
    )
    save_config(project_dir, cfg)
    print(
        f"  Registered variant '{name}' (parent={parent}, format={format_label or '-'})."
    )


def cmd_remove(project_dir: str, name: str) -> None:
    cfg = load_config(project_dir)
    if name not in cfg.variants:
        print(f"  Variant '{name}' not registered.")
        return
    del cfg.variants[name]
    save_config(project_dir, cfg)
    print(f"  Removed registration for '{name}'. (git branch not touched)")


def _humanize(ts: float) -> str:
    if ts <= 0:
        return "never"
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"


def cmd_status(project_dir: str) -> None:
    """Tabular view of all registered variants."""
    cfg = load_config(project_dir)
    if not cfg.variants:
        print("  No variants registered. Use `vit matrix add <name>`.")
        return

    branches = set(git_list_branches(project_dir))
    rows: List[List[str]] = [["variant", "parent", "format", "behind", "last rederive"]]
    for name, v in sorted(cfg.variants.items()):
        exists = name in branches
        if not exists:
            rows.append(
                [
                    name,
                    v.parent,
                    v.format or "-",
                    "branch missing",
                    _humanize(v.last_rederive_at),
                ]
            )
            continue
        behind = _commits_behind(project_dir, name, v.parent)
        rows.append(
            [
                name,
                v.parent,
                v.format or "-",
                str(behind),
                _humanize(v.last_rederive_at),
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    print()
    print("  matrix status")
    for i, row in enumerate(rows):
        cells = "  ".join(c.ljust(widths[j]) for j, c in enumerate(row))
        print(f"    {cells}")
        if i == 0:
            print(f"    {'  '.join('-' * w for w in widths)}")
    print()


def cmd_rederive(project_dir: str, name: str, *, dry_run: bool = False) -> None:
    """Cherry-pick parent's new commits onto the variant branch."""
    cfg = load_config(project_dir)
    if name not in cfg.variants:
        print(f"  Variant '{name}' not registered. Use `vit matrix add` first.")
        return

    variant = cfg.variants[name]
    branches = set(git_list_branches(project_dir))
    if name not in branches:
        print(f"  Branch '{name}' does not exist.")
        return
    if variant.parent not in branches:
        print(f"  Parent branch '{variant.parent}' does not exist.")
        return

    # Determine commits to replay: those on parent but not on variant.
    log = _run(
        ["log", f"{name}..{variant.parent}", "--reverse", "--pretty=format:%H %s"],
        cwd=project_dir,
        check=False,
    )
    if log.returncode != 0 or not log.stdout.strip():
        print(f"  '{name}' already at parent.")
        return

    commits = [
        line.strip().split(" ", 1)
        for line in log.stdout.strip().split("\n")
        if line.strip()
    ]
    print(f"  {len(commits)} commit(s) to replay onto '{name}':")
    for sha, msg in commits:
        print(f"    {sha[:7]}  {msg}")

    if dry_run:
        print("  (dry run, no action taken)")
        return

    current = git_current_branch(project_dir)
    try:
        git_checkout(project_dir, name)
        for sha, msg in commits:
            result = _run(["cherry-pick", sha], cwd=project_dir, check=False)
            if result.returncode != 0:
                print(
                    f"  Conflict on {sha[:7]} — resolve manually, then run `git cherry-pick --continue`."
                )
                return
            print(f"    picked {sha[:7]}")
        parent_hash = _rev_parse(project_dir, variant.parent) or ""
        variant.last_rederive_at = time.time()
        variant.last_rederive_hash = parent_hash
        cfg.variants[name] = variant
        save_config(project_dir, cfg)
        print(
            f"  Rederived '{name}' up to {parent_hash[:7] if parent_hash else variant.parent}."
        )
    finally:
        try:
            git_checkout(project_dir, current)
        except GitError:
            pass


def run_cli(subcmd: str, args) -> int:
    """Entry point called by vit/cli.py. Returns shell exit code."""
    project_dir = find_project_root()
    if project_dir is None:
        print("Error: Not a vit project. Run 'vit init' first.")
        return 1

    if subcmd == "init":
        cmd_init(project_dir)
        return 0
    if subcmd == "add":
        cmd_add(
            project_dir,
            name=args.name,
            parent=args.parent,
            format_label=args.format,
            create_branch=not args.no_branch,
        )
        return 0
    if subcmd == "remove":
        cmd_remove(project_dir, args.name)
        return 0
    if subcmd in ("status", None):
        cmd_status(project_dir)
        return 0
    if subcmd == "rederive":
        cmd_rederive(project_dir, args.name, dry_run=args.dry_run)
        return 0
    print(f"Unknown matrix subcommand: {subcmd}")
    return 1
