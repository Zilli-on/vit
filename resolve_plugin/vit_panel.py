"""Vit: Panel — Redirects to PySide6 panel launcher.

Falls back to tkinter panel if PySide6 is not available.
Run from Workspace > Scripts > Vit - Panel.

Logs every invocation to ~/.vit/panel.log so the user can see what
happened when the Resolve console isn't visible.
"""

import os
import sys
import time
import traceback

# --- File-based log so the user can debug even without Resolve's console ---
_LOG_PATH = os.path.expanduser("~/.vit/panel.log")


def _flog(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


_flog("--- Vit.py invoked from Resolve ---")
_flog(f"sys.executable = {sys.executable}")
_flog(f"sys.version    = {sys.version.split()[0]}")

# Bootstrap — put the vit package root on sys.path
try:
    _real = os.path.realpath(__file__)
except NameError:
    _real = None
if _real:
    _root = os.path.dirname(os.path.dirname(_real))
    _flog(f"__file__ realpath root = {_root}")
    if os.path.isdir(os.path.join(_root, "vit")) and _root not in sys.path:
        sys.path.insert(0, _root)
else:
    _pf = os.path.expanduser("~/.vit/package_path")
    _flog(f"no __file__, checking {_pf}")
    if os.path.exists(_pf):
        with open(_pf) as _f:
            _root = _f.read().strip()
        _flog(f"package_path points to {_root}")
        if (
            _root
            and os.path.isdir(os.path.join(_root, "vit"))
            and _root not in sys.path
        ):
            sys.path.insert(0, _root)

# Resolve may inject 'resolve' into the script's globals when run from
# Workspace > Scripts. Imported modules don't see it — inject into
# builtins so launcher/tkinter can access it. Fallback: get it via
# DaVinciResolveScript.
try:
    import builtins

    try:
        builtins.resolve = resolve  # noqa: F821
        _flog("builtins.resolve set from script globals")
    except NameError:
        _flog("`resolve` not in globals; trying DaVinciResolveScript.scriptapp()")
        import DaVinciResolveScript as _dvr

        builtins.resolve = _dvr.scriptapp("Resolve")
        _flog("builtins.resolve set via scriptapp")
except Exception:
    _flog(f"resolve injection failed:\n{traceback.format_exc()}")

try:
    _flog("attempting PySide6 launcher")
    from resolve_plugin.vit_panel_launcher import main

    main()
    _flog("launcher main() returned without exception")
except Exception:
    _flog(f"launcher failed:\n{traceback.format_exc()}")
    # Fallback to tkinter panel
    try:
        _flog("attempting tkinter fallback")
        from resolve_plugin.vit_panel_tkinter import main as tkinter_main

        tkinter_main()
        _flog("tkinter fallback returned without exception")
    except Exception:
        _flog(f"tkinter fallback failed:\n{traceback.format_exc()}")
        print(f"[vit] PANEL ERROR:\n{traceback.format_exc()}")
