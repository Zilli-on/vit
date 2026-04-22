"""Unit tests for vit.config_cmd (`vit config` subcommands)."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from vit import config_cmd
from vit.config_cmd import cmd_get, cmd_list, cmd_set


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".vit").mkdir()
    (tmp_path / ".vit" / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "vit_version": "0.1.1",
                "nle": "resolve",
                "ai": {"provider": None},
            }
        )
    )
    return str(tmp_path)


# ---------- cmd_get ----------


def test_get_reads_nested_dotted_key(project, capsys):
    rc = cmd_get(project, "ai.provider")
    assert rc == 0
    assert "ai.provider: null" in capsys.readouterr().out


def test_get_reads_top_level_key(project, capsys):
    rc = cmd_get(project, "nle")
    assert rc == 0
    assert "nle: resolve" in capsys.readouterr().out


def test_get_reports_unset_and_returns_one(project, capsys):
    rc = cmd_get(project, "does.not.exist")
    assert rc == 1
    assert "(unset)" in capsys.readouterr().out


# ---------- cmd_set ----------


def test_set_writes_valid_value_to_disk(project, capsys):
    rc = cmd_set(project, "ai.provider", "ollama")
    assert rc == 0
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert cfg["ai"]["provider"] == "ollama"


def test_set_coerces_literal_null_to_none(project):
    cmd_set(project, "ai.provider", "gemini")
    cmd_set(project, "ai.provider", "null")
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert cfg["ai"]["provider"] is None


def test_set_rejects_unknown_key(project, capsys):
    rc = cmd_set(project, "schema_version", "99")
    assert rc == 1
    out = capsys.readouterr().out
    assert "not writable" in out


def test_set_rejects_unknown_value_for_known_key(project, capsys):
    rc = cmd_set(project, "ai.provider", "chatgpt")
    assert rc == 1
    out = capsys.readouterr().out
    assert "not a valid value" in out
    # Config on disk must not have been modified.
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert cfg["ai"]["provider"] is None


def test_set_preserves_siblings(project):
    """Writing ai.provider must not clobber schema_version or nle."""
    cmd_set(project, "ai.provider", "ollama")
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert cfg["schema_version"] == 2
    assert cfg["nle"] == "resolve"
    assert cfg["vit_version"] == "0.1.1"


# ---------- cmd_list ----------


def test_list_prints_every_key_path(project, capsys):
    rc = cmd_list(project)
    assert rc == 0
    out = capsys.readouterr().out
    for expected in ("schema_version", "nle", "ai.provider", "vit_version"):
        assert expected in out


def test_list_reports_empty_when_no_config(tmp_path, capsys):
    rc = cmd_list(str(tmp_path))  # no .vit/ dir
    assert rc == 1
    assert "No config found" in capsys.readouterr().out


# ---------- run_cli dispatcher ----------


def test_run_cli_requires_a_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # Also redirect HOME so ~/.vit (install state) isn't picked up as a
    # false project.
    monkeypatch.setenv("HOME", str(tmp_path / "empty"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "empty"))
    rc = config_cmd.run_cli("list", SimpleNamespace())
    assert rc == 1
    assert "Not a vit project" in capsys.readouterr().out


def test_run_cli_unknown_subcmd(project, monkeypatch, capsys):
    monkeypatch.chdir(project)
    rc = config_cmd.run_cli("invalid", SimpleNamespace())
    assert rc == 1
    assert "Unknown" in capsys.readouterr().out
