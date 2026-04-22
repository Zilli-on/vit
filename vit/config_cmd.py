"""`vit config <key> [value]` — read / write values in .vit/config.json.

Keys use dotted paths: `ai.provider`, `nle`, `vit_version`. Reading
returns the value (or prints `(unset)`); writing persists a change
through the usual json.dump pipeline so schema_version and sibling
keys are preserved.

Writes are restricted to a small whitelist so we don't accidentally
corrupt schema-level fields like `schema_version`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional, Tuple


_WRITABLE_KEYS = {
    "ai.provider": (None, "ollama", "gemini", "claude_cli", "heuristic"),
    "nle": ("resolve",),
}


def _config_path(project_dir: str) -> str:
    return os.path.join(project_dir, ".vit", "config.json")


def _load(project_dir: str) -> dict:
    path = _config_path(project_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(project_dir: str, cfg: dict) -> None:
    path = _config_path(project_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
        f.write("\n")


def _walk(cfg: dict, key: str) -> Tuple[dict, str]:
    """Return (parent_dict, leaf_name) for a dotted key.

    `ai.provider` -> (cfg["ai"], "provider")
    `nle`         -> (cfg,         "nle")

    Creates intermediate dicts only on write; on read we just reflect
    what's on disk.
    """
    parts = key.split(".")
    node: Any = cfg
    for segment in parts[:-1]:
        if not isinstance(node, dict) or segment not in node:
            return {}, parts[-1]
        node = node[segment]
    if not isinstance(node, dict):
        return {}, parts[-1]
    return node, parts[-1]


def _walk_or_create(cfg: dict, key: str) -> Tuple[dict, str]:
    parts = key.split(".")
    node = cfg
    for segment in parts[:-1]:
        nxt = node.get(segment)
        if not isinstance(nxt, dict):
            nxt = {}
            node[segment] = nxt
        node = nxt
    return node, parts[-1]


def _coerce(raw: str) -> Any:
    """Turn a CLI string into a JSON-friendly value.

    'null' -> None, 'true'/'false' -> bool, otherwise literal string.
    We deliberately don't try to parse numbers: we only ship string/
    bool/null values right now.
    """
    if raw == "null":
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    return raw


def cmd_get(project_dir: str, key: str) -> int:
    cfg = _load(project_dir)
    parent, leaf = _walk(cfg, key)
    if leaf not in parent:
        print(f"  {key}: (unset)")
        return 1
    value = parent[leaf]
    # Pretty-print booleans / None / scalars.
    if value is None:
        print(f"  {key}: null")
    elif isinstance(value, bool):
        print(f"  {key}: {'true' if value else 'false'}")
    elif isinstance(value, (int, float, str)):
        print(f"  {key}: {value}")
    else:
        print(f"  {key}: {json.dumps(value, sort_keys=True)}")
    return 0


def cmd_set(project_dir: str, key: str, value: str) -> int:
    if key not in _WRITABLE_KEYS:
        print(
            f"  Error: '{key}' is not writable from the CLI.\n"
            f"  Writable keys: {', '.join(sorted(_WRITABLE_KEYS))}"
        )
        return 1
    coerced = _coerce(value)
    allowed = _WRITABLE_KEYS[key]
    if coerced not in allowed:
        allowed_str = ", ".join(repr(a) for a in allowed)
        print(f"  Error: '{value}' is not a valid value for '{key}'.")
        print(f"  Allowed: {allowed_str}")
        return 1

    cfg = _load(project_dir)
    parent, leaf = _walk_or_create(cfg, key)
    parent[leaf] = coerced
    _save(project_dir, cfg)
    display = "null" if coerced is None else str(coerced)
    print(f"  Set {key} = {display}")
    return 0


def cmd_list(project_dir: str) -> int:
    cfg = _load(project_dir)
    if not cfg:
        print("  No config found.")
        return 1
    print()
    print("  vit config")
    print("  " + "-" * 40)

    def _walk_print(node: Any, prefix: str = "") -> None:
        if isinstance(node, dict):
            for k in sorted(node.keys()):
                _walk_print(node[k], prefix + (f".{k}" if prefix else k))
        else:
            display = "null" if node is None else node
            print(f"    {prefix} = {display}")

    _walk_print(cfg)
    print()
    return 0


def run_cli(subcmd: Optional[str], args) -> int:
    """Dispatcher called from vit.cli.cmd_config."""
    from .core import find_project_root

    project_dir = find_project_root()
    if project_dir is None:
        print("Error: Not a vit project. Run 'vit init' first.")
        return 1

    if subcmd in ("list", None):
        return cmd_list(project_dir)
    if subcmd == "get":
        return cmd_get(project_dir, args.key)
    if subcmd == "set":
        return cmd_set(project_dir, args.key, args.value)
    print(f"  Unknown config subcommand: {subcmd}")
    return 1
