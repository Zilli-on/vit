"""Unit tests for vit.schema — migration runner + legacy-config compat.

These tests register temporary migrations, run them, and assert the
config + on-disk state are transformed correctly. The module-level
registry is reset between tests so one test's migration can't leak into
another's.
"""

from __future__ import annotations

import json
import os
from typing import List

import pytest

from vit.schema import CURRENT_SCHEMA_VERSION
from vit.schema import migrations as mig_mod
from vit.schema.migrations import (
    Migration,
    migrate_if_needed,
    pending_migrations,
    read_schema_version,
    register,
    write_schema_version,
)


@pytest.fixture
def empty_registry(monkeypatch):
    """Isolate the module-level migration registry per test."""
    monkeypatch.setattr(mig_mod, "_MIGRATIONS", [])
    yield mig_mod


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".vit").mkdir()
    return str(tmp_path)


# ---------- read_schema_version ----------


def test_read_version_defaults_to_current_on_missing_config(project):
    assert read_schema_version(project) == CURRENT_SCHEMA_VERSION


def test_read_version_returns_1_for_legacy_string_only_config(project):
    # Pre-v0.1.1 format: only a string "version" field.
    with open(os.path.join(project, ".vit", "config.json"), "w") as f:
        json.dump({"version": "0.1.0", "nle": "resolve"}, f)
    assert read_schema_version(project) == 1


def test_read_version_returns_recorded_schema_version(project):
    with open(os.path.join(project, ".vit", "config.json"), "w") as f:
        json.dump({"schema_version": 3, "nle": "resolve"}, f)
    assert read_schema_version(project) == 3


def test_read_version_handles_corrupt_config(project):
    with open(os.path.join(project, ".vit", "config.json"), "w") as f:
        f.write("not json {{")
    assert read_schema_version(project) == 1


# ---------- write_schema_version ----------


def test_write_schema_version_creates_config_with_required_fields(project):
    write_schema_version(project, 2, vit_version="0.9.9")
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert cfg["schema_version"] == 2
    assert cfg["vit_version"] == "0.9.9"
    assert cfg["nle"] == "resolve"
    # Legacy `version` must be gone.
    assert "version" not in cfg


def test_write_schema_version_strips_legacy_version_on_upgrade(project):
    with open(os.path.join(project, ".vit", "config.json"), "w") as f:
        json.dump({"version": "0.1.0", "nle": "resolve"}, f)
    write_schema_version(project, 2)
    with open(os.path.join(project, ".vit", "config.json")) as f:
        cfg = json.load(f)
    assert "version" not in cfg
    assert cfg["schema_version"] == 2


# ---------- pending_migrations ----------


def test_pending_migrations_empty_when_current_equals_target(empty_registry):
    assert pending_migrations(1, 1) == []


def test_pending_migrations_returns_full_chain(empty_registry):
    called: List[str] = []
    register(Migration(1, 2, "one_to_two", lambda p: called.append("1->2")))
    register(Migration(2, 3, "two_to_three", lambda p: called.append("2->3")))
    chain = pending_migrations(1, 3)
    assert [m.name for m in chain] == ["one_to_two", "two_to_three"]


def test_pending_migrations_raises_on_missing_link(empty_registry):
    register(Migration(1, 2, "a", lambda p: None))
    # No migration from 2 -> 3 registered.
    with pytest.raises(RuntimeError, match="no migration path"):
        pending_migrations(1, 3)


# ---------- migrate_if_needed ----------


def test_migrate_if_needed_no_op_when_current(project, empty_registry):
    write_schema_version(project, CURRENT_SCHEMA_VERSION)
    applied = migrate_if_needed(project)
    assert applied == []


def test_migrate_if_needed_runs_chain_in_order(project, empty_registry, monkeypatch):
    write_schema_version(project, 1)
    # Fake target = 3 so we can exercise a multi-step chain.
    monkeypatch.setattr("vit.schema.migrations.CURRENT_SCHEMA_VERSION", 3)

    called: List[str] = []

    def m1(p):
        called.append("1->2")
        with open(os.path.join(p, "touched_by_m1"), "w") as f:
            f.write("x")

    def m2(p):
        called.append("2->3")
        with open(os.path.join(p, "touched_by_m2"), "w") as f:
            f.write("x")

    register(Migration(1, 2, "m1", m1))
    register(Migration(2, 3, "m2", m2))

    applied = migrate_if_needed(project, vit_version="test")
    assert applied == ["m1", "m2"]
    assert called == ["1->2", "2->3"]
    # Both side effects should be present.
    assert os.path.exists(os.path.join(project, "touched_by_m1"))
    assert os.path.exists(os.path.join(project, "touched_by_m2"))
    # schema_version should now reflect the target.
    with open(os.path.join(project, ".vit", "config.json")) as f:
        assert json.load(f)["schema_version"] == 3


def test_migrate_if_needed_raises_on_newer_than_supported(project, empty_registry):
    # Write a future version on disk.
    write_schema_version(project, CURRENT_SCHEMA_VERSION + 5)
    with pytest.raises(RuntimeError, match="newer than this vit version"):
        migrate_if_needed(project)


def test_migrate_if_needed_aborts_chain_on_failure(
    project, empty_registry, monkeypatch
):
    write_schema_version(project, 1)
    monkeypatch.setattr("vit.schema.migrations.CURRENT_SCHEMA_VERSION", 3)

    def m1(p):
        raise ValueError("boom")

    register(Migration(1, 2, "m1", m1))
    register(Migration(2, 3, "m2", lambda p: None))

    with pytest.raises(ValueError, match="boom"):
        migrate_if_needed(project)
    # schema_version on disk must still be 1 — we never half-commit.
    with open(os.path.join(project, ".vit", "config.json")) as f:
        assert json.load(f)["schema_version"] == 1
