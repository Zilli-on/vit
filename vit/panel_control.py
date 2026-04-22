"""CLI-side health + control for the Resolve panel subprocess.

Backs `vit panel status | log | stop`. Reads the state file written by
`run_server` in vit_panel_launcher and probes its socket. Never starts
Resolve on its own — only inspects + requests clean shutdown.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from typing import Optional


_STATE_PATH = os.path.expanduser(os.path.join("~", ".vit", "panel.state"))
_LOG_PATH = os.path.expanduser(os.path.join("~", ".vit", "panel.log"))


@dataclass
class PanelState:
    port: int
    pid: int
    project_dir: str
    started_at: float

    @classmethod
    def from_dict(cls, d: dict) -> "PanelState":
        return cls(
            port=int(d.get("port", 0)),
            pid=int(d.get("pid", 0)),
            project_dir=d.get("project_dir", ""),
            started_at=float(d.get("started_at", 0.0)),
        )


def read_state() -> Optional[PanelState]:
    """Load the state file if present + parseable; else None."""
    if not os.path.exists(_STATE_PATH):
        return None
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            return PanelState.from_dict(json.load(f))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    """Portable liveness probe."""
    if pid <= 0:
        return False
    import sys

    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED = 0x1000
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong(0)
            if k32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0:
                return False
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _send_json(port: int, action: str, timeout: float = 2.0) -> Optional[dict]:
    """Send one newline-delimited JSON request, read one newline-delimited JSON response."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall((json.dumps({"action": action}) + "\n").encode("utf-8"))
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
            if b"\n" in buf:
                line, _ = buf.split(b"\n", 1)
                return json.loads(line.decode("utf-8"))
    except (OSError, json.JSONDecodeError, socket.timeout):
        return None
    return None


def _humanize_uptime(started_at: float) -> str:
    if started_at <= 0:
        return "?"
    secs = max(0, time.time() - started_at)
    if secs < 60:
        return f"{int(secs)}s"
    if secs < 3600:
        return f"{int(secs / 60)}m"
    if secs < 86400:
        return f"{int(secs / 3600)}h"
    return f"{int(secs / 86400)}d"


def cmd_status() -> int:
    """Report whether a panel is live. Exit 0 if yes, 1 otherwise."""
    state = read_state()
    if state is None:
        print("  No panel state recorded. (Resolve panel isn't running.)")
        return 1

    alive = _pid_alive(state.pid)
    pong = _send_json(state.port, "ping") if alive else None

    print()
    print("  vit panel status")
    print("  " + "-" * 48)
    print(f"    pid           {state.pid}  ({'alive' if alive else 'dead'})")
    print(f"    port          127.0.0.1:{state.port}")
    print(f"    project       {state.project_dir or '(none)'}")
    print(f"    uptime        {_humanize_uptime(state.started_at)}")
    if pong and pong.get("ok"):
        print("    socket ping   OK")
        rc = 0
    else:
        print("    socket ping   no response")
        rc = 1
    print()
    return rc


def cmd_log(tail: int = 40) -> int:
    """Print the last N lines of the panel log."""
    if not os.path.exists(_LOG_PATH):
        print("  No panel log yet (panel hasn't been invoked by Resolve).")
        return 1
    try:
        with open(_LOG_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"  Error reading {_LOG_PATH}: {e}")
        return 1
    tail = max(1, tail)
    for line in lines[-tail:]:
        print(line.rstrip())
    return 0


def cmd_stop() -> int:
    """Ask the running panel to shut down cleanly over its socket."""
    state = read_state()
    if state is None:
        print("  No panel state recorded. Nothing to stop.")
        return 1
    if not _pid_alive(state.pid):
        print(f"  Stale state file for pid {state.pid}. Cleaning up.")
        try:
            os.remove(_STATE_PATH)
        except OSError:
            pass
        return 1
    pong = _send_json(state.port, "quit", timeout=3.0)
    if pong and pong.get("ok"):
        print("  Panel accepted quit. Resolve will drop the subprocess.")
        return 0
    print("  Panel did not respond to quit over the socket.")
    return 1


def run_cli(subcmd: str, args) -> int:
    if subcmd == "status" or subcmd is None:
        return cmd_status()
    if subcmd == "log":
        return cmd_log(tail=getattr(args, "tail", 40))
    if subcmd == "stop":
        return cmd_stop()
    print(f"  Unknown panel subcommand: {subcmd}")
    return 1
