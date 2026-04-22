# Vit Studio — fork additions over upstream

This fork tracks [LucasHJin/vit](https://github.com/LucasHJin/vit) plus
a small, self-contained set of additions. Upstream explicitly does not
accept external PRs, so changes land here; rebase monthly.

## Why fork

Upstream Vit is a strong prototype but has four load-bearing issues for
real use:

1. `pip install .` silently excludes `resolve_plugin/` because it has no
   `__init__.py` — `vit install-resolve` then fails.
2. `vit init` writes a state that immediately fails `vit validate`.
3. Tests hardcode `main`; break on any machine with `init.defaultBranch
   = master` (Windows git default).
4. AI merge is Gemini-only, so zero-cost / local-only operation is not
   possible.

All four are fixed here, plus two new features.

## What this fork adds

### 1. Install + init hardening (commit 431a02f)

- `resolve_plugin/__init__.py` + `resolve_plugin/graph_assets/__init__.py`
- `MANIFEST.in` + `include_package_data=True` so the wheel ships all
  `.py` and `.svg` files.
- `git_init` normalizes HEAD to `refs/heads/main` independent of global
  config.
- `TimelineMetadata` defaults `track_count` to 0/0 — `vit init` + `vit
  validate` now returns "no issues" on an empty project.
- PySide6 moved to `extras_require["qt"]`, google-generativeai to
  `extras_require["gemini"]`. Base install is ~5 MB; `pip install
  ".[all]"` restores the full setup.

### 2. `vit doctor` (commit ab38949)

One-shot read-only diagnostic. Probes Python, git, Resolve install path,
Resolve scripts dir, `~/.vit/package_path`, PySide6 importability,
google-generativeai, `GEMINI_API_KEY`, Ollama at localhost:11434,
`claude` CLI binary, `VIT_PROJECT_DIR`, last-opened project. Each line
returns `[ok] / [!!] / [xx]` with a "how to fix" suggestion. Designed
to replace `paste your error` with `paste your doctor output`.

### 3. Pluggable AI provider (commits d9356e3 + 9a02a95)

New `vit/ai/` package with a protocol-first design. Four backends:

- `ollama`    — local-first, stdlib `urllib`, default when reachable.
                Model via `VIT_OLLAMA_MODEL` (default `qwen2.5:3b`).
- `gemini`    — unchanged behavior from upstream; only active if
                `GEMINI_API_KEY` is set and the SDK is installed.
- `claude_cli`— shells to `claude --print`; zero extra cost for Claude
                Code users.
- `heuristic` — always-available stub that returns an empty envelope;
                signals "no AI, fall back to deterministic rules".

Selection order: `VIT_AI_PROVIDER` env → `.vit/config.json` `ai.provider`
→ ollama → gemini → claude_cli → heuristic.

Every Gemini call site in `ai_merge.py` (6 of them) routes through a
single `_ai_complete(system, user, json_mode)` helper backed by the
factory.

### 4. `vit matrix` — per-deliverable variant manager (commit d9356e3)

Targeted at high-output social / ad content. Scenario: one hero cut on
`main`, N derivative variants (9x16 Reel, 1x1 Feed, 16x9 YouTube,
30s/60s/90s, ...). Variants are plain git branches; `.vit/variants.json`
is a pure UX overlay.

```
vit matrix init
vit matrix add 9x16-short --format 9x16-30s
vit matrix add 1x1-feed   --format 1x1-60s
vit matrix status
vit matrix rederive 9x16-short        # cherry-pick main's new commits
```

`status` shows a grid with `commits behind` and `last rederive` per
variant. `rederive` replays via `git cherry-pick`; stops on conflict and
tells you to resolve with `git cherry-pick --continue`.

## Zero-cost compliance

With this fork:

- **Ollama running locally** → full merge / commit-message / log-summary
  / branch-comparison AI, entirely offline, zero API cost.
- **No Ollama, no GEMINI_API_KEY, no `claude` CLI** → heuristic
  fallback; vit works but gives no AI-assisted merge suggestions.
- **`claude` CLI installed** (Claude Code subscribers) → Claude handles
  AI tasks without needing an API key.

`pip install vit` (base) is ~5 MB and pulls only `rich` as a runtime
dep. Qt + Gemini SDK are opt-in via `vit[qt]`, `vit[gemini]`, or
`vit[all]`.

## Verification on this machine

- Python 3.12.10, git 2.46.2, DaVinci Resolve installed.
- `pytest tests/`: **100 / 100 pass** (was 97 / 100 upstream).
- `vit doctor`: 11 OK / 1 WARN (no GEMINI_API_KEY, expected).
- `vit init x` → branch `main`, `vit validate` → no issues.
- `vit install-resolve` → `Vit.py` copied to `%APPDATA%\Blackmagic
  Design\DaVinci Resolve\Fusion\Scripts\Edit\`.
- `vit matrix add/status/rederive` verified end-to-end with real
  cherry-pick.

## Not yet done

- Panel merge dialog (replaces CLI `input()` for non-technical users).
- Matrix-aware panel tab.
- Ollama provider tests that mock the HTTP layer (currently only smoke
  tested live).
- Tests for `vit matrix` and `vit doctor`.
