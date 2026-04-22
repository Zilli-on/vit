"""Diagnostic probe for Vit — `vit doctor`.

Runs a fixed list of environment checks and prints a structured report.
Goal: when a user's install misbehaves, one command tells them exactly
what is wrong. Designed to be read by support, not by the user alone.

All probes are read-only and must complete in well under 5 seconds.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class Check:
    name: str
    status: str  # "OK", "WARN", "FAIL"
    detail: str
    fix: str = ""


def _resolve_scripts_dir() -> str:
    if sys.platform == "win32":
        return os.path.join(
            os.environ.get("APPDATA", ""),
            "Blackmagic Design",
            "DaVinci Resolve",
            "Fusion",
            "Scripts",
            "Edit",
        )
    if sys.platform == "darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
            "Fusion/Scripts/Edit"
        )
    return os.path.expanduser("~/.local/share/DaVinciResolve/Fusion/Scripts/Edit")


def _resolve_install_dir() -> Optional[str]:
    """Return the first DaVinci Resolve install path that exists, or None."""
    candidates = []
    if sys.platform == "win32":
        candidates += [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve",
            r"C:\Program Files (x86)\Blackmagic Design\DaVinci Resolve",
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/DaVinci Resolve/DaVinci Resolve.app",
            "/Applications/DaVinci Resolve.app",
        ]
    else:
        candidates += [
            "/opt/resolve",
            "/usr/bin/resolve",
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _probe_python() -> Check:
    v = sys.version_info
    if v >= (3, 8):
        return Check(
            "Python version", "OK", f"{sys.version.split()[0]} at {sys.executable}"
        )
    return Check(
        "Python version",
        "FAIL",
        f"{sys.version.split()[0]} — vit needs 3.8+",
        fix="Install Python 3.8 or later.",
    )


def _probe_git() -> Check:
    git = shutil.which("git")
    if not git:
        return Check(
            "git",
            "FAIL",
            "git not found in PATH",
            fix="Install git and re-open your terminal.",
        )
    try:
        out = subprocess.run(
            [git, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception as e:
        return Check("git", "WARN", f"git present but --version failed: {e}")
    return Check("git", "OK", out)


def _probe_resolve_install() -> Check:
    path = _resolve_install_dir()
    if path:
        return Check("DaVinci Resolve installed", "OK", path)
    return Check(
        "DaVinci Resolve installed",
        "WARN",
        "Resolve not detected at known paths",
        fix="Install Resolve or ignore if you only use the CLI.",
    )


def _probe_resolve_scripts_dir() -> Check:
    scripts = _resolve_scripts_dir()
    if os.path.isdir(scripts):
        items = [name for name in os.listdir(scripts) if name.lower().startswith("vit")]
        detail = scripts + (f"  (installed: {', '.join(items)})" if items else "")
        return Check("Resolve Edit scripts dir", "OK", detail)
    return Check(
        "Resolve Edit scripts dir",
        "WARN",
        f"missing: {scripts}",
        fix="Open Resolve once to create it, then run `vit install-resolve`.",
    )


def _probe_package_path() -> Check:
    pf = os.path.expanduser(os.path.join("~", ".vit", "package_path"))
    if not os.path.exists(pf):
        return Check(
            "package_path file",
            "WARN",
            f"{pf} not found",
            fix="Run `vit install-resolve` once so the panel can find vit.",
        )
    try:
        with open(pf) as f:
            root = f.read().strip()
    except Exception as e:
        return Check("package_path file", "FAIL", f"cannot read {pf}: {e}")
    if not os.path.isdir(os.path.join(root, "vit")):
        return Check(
            "package_path file",
            "FAIL",
            f"{pf} points to {root} but no vit/ package there",
            fix="Re-run `vit install-resolve` from the installed vit.",
        )
    return Check("package_path file", "OK", f"{pf} -> {root}")


def _probe_import(name: str, purpose: str, fix: str) -> Check:
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "unknown")
        return Check(f"import {name}", "OK", f"{name} {ver} ({purpose})")
    except Exception as e:
        return Check(
            f"import {name}", "WARN", f"{name} not importable ({purpose}): {e}", fix=fix
        )


def _probe_gemini_key() -> Check:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return Check(
            "GEMINI_API_KEY",
            "WARN",
            "not set — AI features fall back to heuristics or other providers",
            fix="Set GEMINI_API_KEY, or use --ai-provider ollama|claude-cli.",
        )
    masked = key[:4] + "…" + key[-4:] if len(key) > 10 else "set"
    return Check("GEMINI_API_KEY", "OK", f"set ({masked})")


def _probe_ollama() -> Check:
    """Heuristic: check if ollama is reachable on the default port."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            pass
        return Check("Ollama reachable", "OK", "http://127.0.0.1:11434")
    except OSError:
        return Check(
            "Ollama reachable",
            "WARN",
            "not listening on 127.0.0.1:11434",
            fix="`ollama serve` if you want local AI merge, else ignore.",
        )


def _probe_claude_cli() -> Check:
    claude = shutil.which("claude")
    if not claude:
        return Check(
            "claude CLI",
            "WARN",
            "not found",
            fix="Install Claude Code CLI if you want Claude-based AI merge.",
        )
    return Check("claude CLI", "OK", claude)


def _probe_vit_project_dir_env() -> Check:
    env = os.environ.get("VIT_PROJECT_DIR")
    if not env:
        return Check("VIT_PROJECT_DIR env", "OK", "not set (optional)")
    if not os.path.isdir(os.path.join(env, ".vit")):
        return Check(
            "VIT_PROJECT_DIR env",
            "FAIL",
            f"set to {env} but no .vit/ directory there",
            fix="unset the var, or point it at a real vit project.",
        )
    return Check("VIT_PROJECT_DIR env", "OK", env)


def _probe_last_project() -> Check:
    last = os.path.expanduser(os.path.join("~", ".vit", "last_project"))
    if not os.path.exists(last):
        return Check("last-opened project", "OK", "no record yet (optional)")
    try:
        with open(last) as f:
            path = f.read().strip()
    except Exception as e:
        return Check("last-opened project", "WARN", f"cannot read {last}: {e}")
    if not os.path.isdir(os.path.join(path, ".vit")):
        return Check(
            "last-opened project",
            "WARN",
            f"{last} points to {path} which is no longer a vit project",
            fix="Open a fresh project via the panel to reset.",
        )
    return Check("last-opened project", "OK", path)


_PROBES: List[Callable[[], Check]] = [
    _probe_python,
    _probe_git,
    _probe_resolve_install,
    _probe_resolve_scripts_dir,
    _probe_package_path,
    lambda: _probe_import(
        "PySide6",
        "Qt panel UI",
        'pip install PySide6 (or `pip install "vit[qt]"`); Tkinter fallback otherwise.',
    ),
    lambda: _probe_import(
        "google.generativeai",
        "Gemini AI merge provider",
        'pip install google-generativeai (or `pip install "vit[gemini]"`).',
    ),
    _probe_gemini_key,
    _probe_ollama,
    _probe_claude_cli,
    _probe_vit_project_dir_env,
    _probe_last_project,
]


_ICON = {"OK": "[ok]", "WARN": "[!!]", "FAIL": "[xx]"}


def run_diagnostics() -> List[Check]:
    """Execute all probes and return the list of Check results."""
    results = []
    for probe in _PROBES:
        try:
            results.append(probe())
        except Exception as e:
            results.append(Check(probe.__name__, "FAIL", f"probe crashed: {e}"))
    return results


def format_report(checks: List[Check]) -> str:
    """Pretty-print the checks into a single string."""
    width = max(len(c.name) for c in checks)
    lines = ["", "  vit doctor", "  " + "-" * 58]
    for c in checks:
        icon = _ICON.get(c.status, c.status)
        lines.append(f"  {icon}  {c.name.ljust(width)}   {c.detail}")
        if c.fix and c.status != "OK":
            lines.append(f"        {' ' * width}   -> {c.fix}")
    ok = sum(1 for c in checks if c.status == "OK")
    warn = sum(1 for c in checks if c.status == "WARN")
    fail = sum(1 for c in checks if c.status == "FAIL")
    lines.append("  " + "-" * 58)
    lines.append(f"  summary: {ok} ok, {warn} warn, {fail} fail")
    lines.append("")
    return "\n".join(lines)


def any_fails(checks: List[Check]) -> bool:
    return any(c.status == "FAIL" for c in checks)
