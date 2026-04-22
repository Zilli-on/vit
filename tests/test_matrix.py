"""Unit tests for vit.matrix.

Uses a real temp git repo (not a mock) because the module is a thin
layer over git commands — mocking would lie about the behavior.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from vit import matrix
from vit.core import git_init


@pytest.fixture
def project_dir():
    """Fresh vit project with an initial commit on main."""
    with tempfile.TemporaryDirectory() as tmp:
        git_init(tmp)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
        # Initial commit so branches are rooted.
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp, check=True)
        yield tmp


def _args(**kwargs):
    """Build a simple argparse-style args object."""
    return SimpleNamespace(**kwargs)


def test_load_config_returns_empty_when_absent(project_dir):
    cfg = matrix.load_config(project_dir)
    assert cfg.variants == {}


def test_save_and_load_config_roundtrip(project_dir):
    cfg = matrix.MatrixConfig()
    cfg.variants["v1"] = matrix.Variant(name="v1", format="9x16-30s")
    matrix.save_config(project_dir, cfg)

    loaded = matrix.load_config(project_dir)
    assert "v1" in loaded.variants
    assert loaded.variants["v1"].format == "9x16-30s"
    assert loaded.variants["v1"].parent == "main"


def test_load_config_tolerates_garbage(project_dir):
    path = os.path.join(project_dir, ".vit", "variants.json")
    with open(path, "w") as f:
        f.write("not json {{{")
    cfg = matrix.load_config(project_dir)
    assert cfg.variants == {}


def test_cmd_init_creates_file(project_dir, capsys):
    matrix.cmd_init(project_dir)
    assert os.path.exists(os.path.join(project_dir, ".vit", "variants.json"))
    out = capsys.readouterr().out
    assert "Initialized" in out


def test_cmd_init_is_idempotent(project_dir, capsys):
    matrix.cmd_init(project_dir)
    matrix.cmd_init(project_dir)
    out = capsys.readouterr().out
    assert "already initialized" in out.lower()


def test_cmd_add_creates_branch_and_registers(project_dir):
    matrix.cmd_add(project_dir, "9x16", format_label="9x16-30s")
    cfg = matrix.load_config(project_dir)
    assert "9x16" in cfg.variants
    assert cfg.variants["9x16"].format == "9x16-30s"

    result = subprocess.run(
        ["git", "branch", "--list", "9x16"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert "9x16" in result.stdout


def test_cmd_add_no_branch_skips_branch_creation(project_dir):
    matrix.cmd_add(project_dir, "ghost", create_branch=False)
    cfg = matrix.load_config(project_dir)
    assert "ghost" in cfg.variants
    result = subprocess.run(
        ["git", "branch", "--list", "ghost"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert "ghost" not in result.stdout


def test_cmd_add_rejects_duplicate(project_dir, capsys):
    matrix.cmd_add(project_dir, "v1")
    matrix.cmd_add(project_dir, "v1")
    out = capsys.readouterr().out
    assert "already registered" in out


def test_cmd_remove_drops_registration_but_keeps_branch(project_dir):
    matrix.cmd_add(project_dir, "v1")
    matrix.cmd_remove(project_dir, "v1")
    cfg = matrix.load_config(project_dir)
    assert "v1" not in cfg.variants
    # Branch must still exist
    result = subprocess.run(
        ["git", "branch", "--list", "v1"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert "v1" in result.stdout


def test_commits_behind_zero_on_sync(project_dir):
    matrix.cmd_add(project_dir, "v1")
    behind = matrix._commits_behind(project_dir, "v1", "main")
    assert behind == 0


def test_commits_behind_counts_new_parent_commits(project_dir):
    matrix.cmd_add(project_dir, "v1")

    # Add a commit to main
    path = os.path.join(project_dir, "README.md")
    with open(path, "w") as f:
        f.write("hero v2")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main: v2"], cwd=project_dir, check=True)

    behind = matrix._commits_behind(project_dir, "v1", "main")
    assert behind == 1


def test_rederive_replays_parent_commit(project_dir):
    matrix.cmd_add(project_dir, "v1")

    path = os.path.join(project_dir, "README.md")
    with open(path, "w") as f:
        f.write("hero v2")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main: v2"], cwd=project_dir, check=True)

    matrix.cmd_rederive(project_dir, "v1")

    behind = matrix._commits_behind(project_dir, "v1", "main")
    assert behind == 0

    cfg = matrix.load_config(project_dir)
    assert cfg.variants["v1"].last_rederive_at > 0
    assert cfg.variants["v1"].last_rederive_hash  # non-empty


def test_commits_behind_counts_zero_after_rederive_despite_hash_change(project_dir):
    """After cherry-pick onto a diverged branch, the replayed commit gets
    a new hash. Plain rev-list still reports 'behind'; git cherry pairs
    by patch-id so the semantic behind count must reach zero.

    We force divergence by committing variant-only work before rederive.
    Without divergence, git's content-addressing can collapse the
    cherry-pick into the same hash as the source commit, which would
    defeat the test's intent.
    """
    matrix.cmd_add(project_dir, "v1")

    # Diverge v1 so the cherry-pick is guaranteed to produce a new hash.
    subprocess.run(["git", "checkout", "v1"], cwd=project_dir, check=True)
    with open(os.path.join(project_dir, "variant_only.txt"), "w") as f:
        f.write("variant work")
    subprocess.run(["git", "add", "variant_only.txt"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "variant: work"],
        cwd=project_dir,
        check=True,
    )
    subprocess.run(["git", "checkout", "main"], cwd=project_dir, check=True)

    with open(os.path.join(project_dir, "README.md"), "w") as f:
        f.write("hero v2")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main: v2"], cwd=project_dir, check=True)
    matrix.cmd_rederive(project_dir, "v1")

    # After divergent rederive: rev-list reports 1 (original main: v2
    # commit still not on v1 by hash); git cherry reports 0 because the
    # patch is already applied.
    rev_list = subprocess.run(
        ["git", "rev-list", "--count", "v1..main"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert int(rev_list.stdout.strip()) == 1
    assert matrix._commits_behind(project_dir, "v1", "main") == 0


def test_commits_behind_falls_back_on_bogus_parent(project_dir):
    """If git cherry errors (e.g. parent branch doesn't exist) the
    helper must not crash; it falls back to rev-list or returns 0."""
    matrix.cmd_add(project_dir, "v1")
    # 'not-a-branch' doesn't exist; both cherry and rev-list will fail.
    n = matrix._commits_behind(project_dir, "v1", "not-a-branch")
    assert n == 0


def test_rederive_dry_run_does_not_move_branch(project_dir):
    matrix.cmd_add(project_dir, "v1")

    path = os.path.join(project_dir, "README.md")
    with open(path, "w") as f:
        f.write("hero v2")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main: v2"], cwd=project_dir, check=True)

    matrix.cmd_rederive(project_dir, "v1", dry_run=True)

    behind = matrix._commits_behind(project_dir, "v1", "main")
    assert behind == 1  # unchanged
    cfg = matrix.load_config(project_dir)
    assert cfg.variants["v1"].last_rederive_at == 0


def test_rederive_no_op_when_already_synced(project_dir, capsys):
    matrix.cmd_add(project_dir, "v1")
    matrix.cmd_rederive(project_dir, "v1")
    out = capsys.readouterr().out
    assert "already at parent" in out.lower()


def test_cmd_status_shows_no_variants_hint(project_dir, capsys):
    matrix.cmd_status(project_dir)
    out = capsys.readouterr().out
    assert "no variants registered" in out.lower()


def test_cmd_status_shows_variant_grid(project_dir, capsys):
    matrix.cmd_add(project_dir, "9x16", format_label="9x16-30s")
    capsys.readouterr()  # clear add output
    matrix.cmd_status(project_dir)
    out = capsys.readouterr().out
    assert "9x16" in out
    assert "9x16-30s" in out
    assert "behind" in out


def test_humanize_handles_never():
    assert matrix._humanize(0) == "never"


def test_humanize_handles_recent():
    import time

    assert matrix._humanize(time.time()) == "just now"


def test_promote_merges_variant_into_parent(project_dir):
    matrix.cmd_add(project_dir, "v1")
    # Put a commit on v1 only.
    subprocess.run(["git", "checkout", "v1"], cwd=project_dir, check=True)
    path = os.path.join(project_dir, "feature.txt")
    with open(path, "w") as f:
        f.write("from-variant")
    subprocess.run(["git", "add", "feature.txt"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "variant: new feature"],
        cwd=project_dir,
        check=True,
    )
    subprocess.run(["git", "checkout", "main"], cwd=project_dir, check=True)

    matrix.cmd_promote(project_dir, "v1")

    # Parent should now have the variant's feature file.
    assert os.path.exists(os.path.join(project_dir, "feature.txt"))
    # main should have a merge commit (no-ff).
    log = subprocess.run(
        ["git", "log", "main", "--oneline", "--first-parent"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert "promote 'v1'" in log.stdout


def test_promote_noop_when_already_merged(project_dir, capsys):
    matrix.cmd_add(project_dir, "v1")
    matrix.cmd_promote(project_dir, "v1")
    out = capsys.readouterr().out
    assert "already contains" in out.lower() or "nothing to promote" in out.lower()


def test_promote_dry_run_leaves_parent_untouched(project_dir, capsys):
    matrix.cmd_add(project_dir, "v1")
    subprocess.run(["git", "checkout", "v1"], cwd=project_dir, check=True)
    with open(os.path.join(project_dir, "feature.txt"), "w") as f:
        f.write("x")
    subprocess.run(["git", "add", "feature.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "variant: new"], cwd=project_dir, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=project_dir, check=True)

    head_before = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    ).stdout.strip()

    matrix.cmd_promote(project_dir, "v1", dry_run=True)

    head_after = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_before == head_after  # main unchanged


def test_promote_aborts_on_conflict(project_dir, capsys):
    """Divergent content on the same file in both branches must result
    in an aborted merge with parent left clean."""
    matrix.cmd_add(project_dir, "v1")

    # Variant side
    subprocess.run(["git", "checkout", "v1"], cwd=project_dir, check=True)
    with open(os.path.join(project_dir, "contested.txt"), "w") as f:
        f.write("from variant\n")
    subprocess.run(["git", "add", "contested.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "variant"], cwd=project_dir, check=True)

    # Main side diverges on the same file
    subprocess.run(["git", "checkout", "main"], cwd=project_dir, check=True)
    with open(os.path.join(project_dir, "contested.txt"), "w") as f:
        f.write("from main\n")
    subprocess.run(["git", "add", "contested.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=project_dir, check=True)

    head_before = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    ).stdout.strip()

    matrix.cmd_promote(project_dir, "v1")

    head_after = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    ).stdout.strip()
    # Merge aborted → main unchanged, no MERGE_HEAD stays around.
    assert head_before == head_after
    assert not os.path.exists(os.path.join(project_dir, ".git", "MERGE_HEAD"))
    out = capsys.readouterr().out
    assert "conflict" in out.lower()


def test_promote_rejects_unregistered_variant(project_dir, capsys):
    matrix.cmd_promote(project_dir, "ghost")
    out = capsys.readouterr().out
    assert "not registered" in out.lower()
