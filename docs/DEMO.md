# Live verification in DaVinci Resolve

Everything in `tests/` is CI-grade. The only path that **can't** be
unit-tested is the live Resolve round-trip: Resolve's scripting API,
the Qt panel subprocess, and the serialize → commit → checkout →
deserialize flow on a real timeline. This doc walks you through
verifying that path in under 10 minutes.

Run these steps once after any serializer / deserializer change, or
after upgrading Resolve.

Prerequisites:

- `vit doctor` reports 10+ OK, at most 2 WARN (GEMINI_API_KEY + LFS
  are both optional).
- Resolve is restarted **after** the last `vit install-resolve`.
- `~/.vit/last_project` points at a real vit project, **or**
  `VIT_PROJECT_DIR` is set in your shell before launching Resolve.
  A freshly-initialized throwaway project is fine:
  `vit init ~/.vit-test/demo-$(date +%s)`.

## Step 0 — Panel opens

1. Open DaVinci Resolve, load any project with at least one media clip.
2. `Workspace → Scripts → Vit` (or `Workspace → Scripts → Utility → Vit`
   depending on the page you're on).
3. A Qt window titled **"Vit Panel"** should appear within ~3 seconds.
   Branch name visible in the header.

If nothing opens: `vit panel log -n 40` — the last lines will say why.

**Signal:** panel visible.

## Step 1 — `panel status` reports alive

In a terminal (outside Resolve):

```
vit panel status
```

Expect:

```
  vit panel status
  ------------------------------------------------
    pid           <some pid>  (alive)
    port          127.0.0.1:<5-digit port>
    project       <your project dir>
    uptime        <seconds>s
    socket ping   OK
```

**Signal:** exit code 0, `alive` + `OK` lines both present.

## Step 2 — Save Version roundtrip

1. In Resolve, make one small edit to the timeline — trim a clip by
   a few frames, or add a marker.
2. In the panel, click **Save Version**. Enter a message like
   `demo: trim interview A`.
3. Wait for the green confirmation.

In the terminal:

```
vit log -n 3
```

Expect the new commit at the top with a `[V]` (video) badge.
`vit diff HEAD~1` should show the exact change in human-readable
form, e.g. `~ Trimmed 'Interview_A' end: 00:00:30:00 → 00:00:28:12`.

**Signal:** commit present in `vit log`, diff reflects the actual edit.

## Step 3 — Branch + switch roundtrip

1. In the panel, click **New Branch**, name it `experiment`.
2. Make a second edit on the timeline (different clip, different
   change).
3. **Save Version** on the `experiment` branch.
4. Click **Switch Branch** and pick `main`.
5. Wait for the timeline to refresh.

The timeline should now show the state from step 2 — **not** the
edits from step 3.

```
vit log -n 5
vit branch --list
```

Expect:
- Two commits on `experiment`, one on `main` (plus initial).
- `main` and `experiment` both in the list, `* main` marked current.

**Signal:** timeline content changes back when switching to `main`,
and forward when switching to `experiment`.

## Step 4 — AI provider wires through

In the terminal, from inside the project dir:

```
vit status
```

Expect an `AI:` line showing which provider won the factory's
availability race — usually `ollama` (if you have Ollama running) or
`heuristic` (if nothing reachable).

```
vit config set ai.provider claude_cli
vit status
```

Expect `AI:  claude_cli (config: claude_cli)`.

Reset:

```
vit config set ai.provider null
```

**Signal:** provider choice persists in `.vit/config.json` and is
reflected in the next `vit status`.

## Step 5 — Matrix variant

```
vit matrix init
vit matrix add 9x16-short --format 9x16-30s
vit matrix status
```

Expect a grid with one variant, 0 commits behind. Make a commit on
`main` (any edit + Save Version), run `vit matrix status` — the
variant should now show `1` behind. Then:

```
vit matrix rederive 9x16-short
vit matrix status
```

Expect behind = 0 again, `last rederive` = "just now".

**Signal:** behind counter moves 0 → 1 → 0, cherry-pick is silent.

## Step 6 — Clean shutdown

```
vit panel stop
```

Expect:

```
  Panel accepted quit. Resolve will drop the subprocess.
```

And the Qt panel window closes within ~2 seconds.

```
vit panel status
```

Should now report `No panel state recorded.` — exit code 1.

**Signal:** clean socket-initiated shutdown, no stale state file.

## Report template

When filing a bug, paste:

```
$ vit doctor
...

$ vit --version
...

$ vit panel log -n 30
...

$ vit log -n 5
...
```

Plus what step failed and what the panel / terminal showed.
