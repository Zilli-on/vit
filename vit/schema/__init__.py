"""Schema version tracking + migration registry.

Every vit project has a schema_version in .vit/config.json. When vit is
upgraded and the shape of the JSON domain files or config changes in a
breaking way, we bump CURRENT_SCHEMA_VERSION and add a migration that
transforms old data into the new shape.

Migrations run lazily when a project is loaded — not on import — so old
repos stay on disk unchanged until they're actually opened by a newer
vit. That lets two people on different vit versions coexist temporarily
without one corrupting the other's working copy.
"""

from __future__ import annotations

CURRENT_SCHEMA_VERSION = 2
"""Bumped on breaking changes to the on-disk JSON shape.

Change log:
  1 — initial schema: cuts/color/audio/effects/markers/metadata/manifest
      with .vit/config.json containing schema_version + vit_version + nle.
  2 — .vit/config.json gains an `ai` block: {"provider": null} by
      default (meaning: factory auto-discovery). An explicit value —
      "ollama", "gemini", "claude_cli", "heuristic" — pins this project
      to one provider regardless of host defaults.
"""


def _autoregister_migrations() -> None:
    """Import every migration module so each one self-registers.

    Called once at package import time so migrate_if_needed() can walk
    the full chain without callers having to import migrations by hand.
    Wrapped in try/except so an editor who drops a half-written
    migration file into the tree doesn't crash the whole package
    import — the missing migration will be reported by pending_migrations
    when someone actually runs vit against a project needing that step.
    """
    from importlib import import_module

    for mod_name in ("v2_add_ai_block",):
        try:
            import_module(f"{__name__}.{mod_name}")
        except Exception:
            # Log via stderr — don't kill the import of vit itself.
            import sys
            import traceback

            print(
                f"[vit.schema] failed to register {mod_name}: {traceback.format_exc()}",
                file=sys.stderr,
            )


_autoregister_migrations()
