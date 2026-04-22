"""Migration v1 -> v2: add an `ai` block to .vit/config.json.

Before:  {"schema_version": 1, "vit_version": "0.1.1", "nle": "resolve"}
After:   {"schema_version": 1, "vit_version": "0.1.1", "nle": "resolve",
          "ai": {"provider": null}}

schema_version itself is bumped by migrate_if_needed after all
migrations in the chain succeed, not by the migration body.

Idempotent: if `ai` is already present and contains a `provider` key,
the migration does nothing. That keeps it safe to re-run (e.g. after a
partial failure on an adjacent migration).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .migrations import Migration, register


def _apply(project_dir: str) -> None:
    path = os.path.join(project_dir, ".vit", "config.json")
    cfg: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except (OSError, json.JSONDecodeError):
            # A corrupt config file is a pre-existing problem; leaving
            # the migration a no-op here means we don't compound it.
            return

    ai = cfg.get("ai")
    if not isinstance(ai, dict):
        ai = {}
    ai.setdefault("provider", None)
    cfg["ai"] = ai

    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
        f.write("\n")


register(
    Migration(
        from_version=1,
        to_version=2,
        name="v2_add_ai_block",
        apply=_apply,
    )
)
