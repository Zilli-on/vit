"""Unit tests for vit.panel_control — state parsing, pid-alive, socket probe."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading

import pytest

from vit import panel_control
from vit.panel_control import (
    PanelState,
    _pid_alive,
    cmd_log,
    cmd_status,
    cmd_stop,
    read_state,
)


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect ~/.vit to a temp dir so tests can write real files."""
    fake_home = tmp_path
    (fake_home / ".vit").mkdir()
    if sys.platform == "win32":
        monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))
    # Rebind module-level paths to the new home.
    monkeypatch.setattr(
        panel_control,
        "_STATE_PATH",
        str(fake_home / ".vit" / "panel.state"),
    )
    monkeypatch.setattr(
        panel_control,
        "_LOG_PATH",
        str(fake_home / ".vit" / "panel.log"),
    )
    yield fake_home


def _write_state(home, port=55555, pid=None, project="C:/proj", started=0.0):
    payload = {
        "port": port,
        "pid": pid if pid is not None else os.getpid(),
        "project_dir": project,
        "started_at": started,
    }
    (home / ".vit" / "panel.state").write_text(json.dumps(payload))


# ---------- PanelState parsing ----------


def test_read_state_returns_none_when_missing(tmp_home):
    assert read_state() is None


def test_read_state_parses_valid_file(tmp_home):
    _write_state(tmp_home, port=12345, pid=4242, project="X:/y", started=17.0)
    s = read_state()
    assert isinstance(s, PanelState)
    assert s.port == 12345
    assert s.pid == 4242
    assert s.project_dir == "X:/y"
    assert s.started_at == 17.0


def test_read_state_tolerates_garbage(tmp_home):
    (tmp_home / ".vit" / "panel.state").write_text("not json {{{")
    assert read_state() is None


# ---------- pid-alive probe ----------


def test_pid_alive_true_for_own_pid():
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_false_for_nonexistent_pid():
    # 2^31 - 1 won't be a real pid on either platform
    assert _pid_alive(2147483647) is False


def test_pid_alive_false_for_zero_and_negative():
    assert _pid_alive(0) is False
    assert _pid_alive(-1) is False


# ---------- cmd_status ----------


def test_cmd_status_reports_no_state(tmp_home, capsys):
    rc = cmd_status()
    assert rc == 1
    assert "No panel state" in capsys.readouterr().out


def test_cmd_status_reports_stale_pid(tmp_home, capsys):
    _write_state(tmp_home, pid=2147483647)  # dead pid
    rc = cmd_status()
    assert rc == 1
    out = capsys.readouterr().out
    assert "dead" in out
    assert "no response" in out


def test_cmd_status_reports_alive_with_socket(tmp_home, capsys):
    # Spin up a one-shot socket server that answers a ping.
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    srv.settimeout(5)

    def serve():
        try:
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(3)
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                conn.sendall(
                    (json.dumps({"ok": True, "pid": os.getpid()}) + "\n").encode(
                        "utf-8"
                    )
                )
        except Exception:
            pass
        finally:
            srv.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    _write_state(tmp_home, port=port, pid=os.getpid())
    rc = cmd_status()
    out = capsys.readouterr().out

    t.join(timeout=3)

    assert rc == 0
    assert "alive" in out
    assert "OK" in out


# ---------- cmd_log ----------


def test_cmd_log_without_file(tmp_home, capsys):
    rc = cmd_log(tail=10)
    assert rc == 1
    assert "No panel log" in capsys.readouterr().out


def test_cmd_log_prints_tail(tmp_home, capsys):
    lines = [f"line{i}" for i in range(10)]
    (tmp_home / ".vit" / "panel.log").write_text("\n".join(lines) + "\n")
    rc = cmd_log(tail=3)
    out = capsys.readouterr().out
    assert rc == 0
    # Last 3 lines must be present, older must not.
    assert "line9" in out
    assert "line8" in out
    assert "line7" in out
    assert "line0" not in out


# ---------- cmd_stop ----------


def test_cmd_stop_without_state(tmp_home, capsys):
    rc = cmd_stop()
    assert rc == 1
    assert "Nothing to stop" in capsys.readouterr().out


def test_cmd_stop_cleans_stale_state(tmp_home, capsys):
    _write_state(tmp_home, pid=2147483647)  # dead pid
    rc = cmd_stop()
    assert rc == 1
    assert not (tmp_home / ".vit" / "panel.state").exists()


# ---------- dispatcher ----------


def test_run_cli_defaults_to_status(tmp_home):
    rc = panel_control.run_cli(None, object())
    assert rc == 1  # no state -> status returns 1


def test_run_cli_unknown_subcmd(tmp_home, capsys):
    rc = panel_control.run_cli("nonsense", object())
    assert rc == 1
    assert "Unknown" in capsys.readouterr().out
