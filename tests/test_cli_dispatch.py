"""End-to-end CLI dispatch tests.

Everything else in the suite calls `vit.cli.cmd_*` functions directly.
These tests drive the real argparse tree via `python -m vit.cli` as a
subprocess so we catch subparser typos, misregistered callbacks, and
import-order bugs that don't show up at the function level.

We stay zero-network, zero-Resolve: the tests only exercise commands
that don't need an NLE.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys



VIT_MODULE = ["-m", "vit.cli"]


def _run_vit(*args, cwd=None, env_extra=None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, *VIT_MODULE, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=30,
    )


# ---------- help / version ----------


def test_help_lists_all_registered_commands():
    r = _run_vit("--help")
    assert r.returncode == 0
    expected = {
        "init",
        "add",
        "commit",
        "branch",
        "checkout",
        "merge",
        "diff",
        "log",
        "status",
        "revert",
        "push",
        "pull",
        "validate",
        "doctor",
        "matrix",
        "panel",
        "clone",
        "remote",
        "collab",
        "install-resolve",
        "uninstall-resolve",
    }
    for cmd in expected:
        assert cmd in r.stdout, f"{cmd} missing from --help output"


def test_version_prints_single_line():
    r = _run_vit("--version")
    assert r.returncode == 0
    assert "vit" in r.stdout.lower()


# ---------- doctor ----------


def test_doctor_runs_without_project_and_exits_deterministically():
    r = _run_vit("doctor")
    # doctor may exit 0 or 1 depending on env, but must never crash.
    assert r.returncode in (0, 1)
    assert "vit doctor" in r.stdout


# ---------- init + status + branch + log ----------


def test_init_produces_v2_schema_project(tmp_path):
    target = tmp_path / "proj"
    r = _run_vit("init", str(target))
    assert r.returncode == 0
    assert (target / ".vit" / "config.json").exists()
    with open(target / ".vit" / "config.json") as f:
        cfg = json.load(f)
    assert cfg["schema_version"] >= 2
    # v2+ contract: ai.provider is present.
    assert "ai" in cfg
    assert "provider" in cfg["ai"]


def test_status_inside_project_returns_zero(tmp_path):
    target = tmp_path / "proj"
    _run_vit("init", str(target))
    r = _run_vit("status", cwd=str(target))
    assert r.returncode == 0
    assert "Branch" in r.stdout


def test_status_outside_project_returns_one(tmp_path):
    r = _run_vit("status", cwd=str(tmp_path))
    assert r.returncode == 1
    assert "Not a vit project" in r.stdout + r.stderr


def test_branch_command_on_fresh_project(tmp_path):
    target = tmp_path / "proj"
    _run_vit("init", str(target))
    r = _run_vit("branch", "--list", cwd=str(target))
    assert r.returncode == 0
    assert "main" in r.stdout


# ---------- migration auto-upgrade via _require_project ----------


def test_status_auto_upgrades_a_legacy_v1_project(tmp_path):
    """Hand-craft a v1 config, run `vit status`, and verify the
    auto-migration kicks in (schema_version bumps + message printed).
    """
    target = tmp_path / "legacy"
    target.mkdir()
    (target / ".vit").mkdir()
    (target / ".vit" / "config.json").write_text(
        json.dumps({"schema_version": 1, "vit_version": "0.1.0", "nle": "resolve"})
    )
    # Bare-minimum git repo so git_status doesn't blow up.
    subprocess.run(["git", "init", "-b", "main"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=target, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=target, check=True)
    (target / "README").write_text("x")
    subprocess.run(["git", "add", "README"], cwd=target, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=target, check=True)

    r = _run_vit("status", cwd=str(target))
    assert r.returncode == 0
    # Migration banner must fire.
    assert "Upgraded project schema" in r.stdout or "v2_add_ai_block" in r.stdout

    # Config on disk should now be v2 shape with ai block.
    with open(target / ".vit" / "config.json") as f:
        cfg = json.load(f)
    assert cfg["schema_version"] >= 2
    assert cfg["ai"]["provider"] is None


# ---------- panel + matrix subparsers ----------


def test_panel_status_without_state_returns_one(tmp_path):
    # Redirect HOME so we don't see a real panel.state from a live run.
    r = _run_vit(
        "panel",
        "status",
        env_extra={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )
    assert r.returncode == 1
    assert "No panel state" in r.stdout


def test_matrix_without_init_is_graceful(tmp_path):
    target = tmp_path / "proj"
    _run_vit("init", str(target))
    r = _run_vit("matrix", "status", cwd=str(target))
    assert r.returncode == 0
    assert "No variants registered" in r.stdout


# ---------- unknown commands fail cleanly ----------


def test_unknown_top_level_command_fails():
    r = _run_vit("nonsensecommand")
    assert r.returncode != 0
