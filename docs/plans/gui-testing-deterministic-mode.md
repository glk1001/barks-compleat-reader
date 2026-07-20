# Plan: GUI testing via remote driving + a deterministic dev mode

> Status: **discussion only** — nothing built, no commitment. Saved 2026-07-20
> so the idea and its design constraints survive across sessions/machines.

## Context

Claude sessions have repeatedly driven the running Barks Reader end-to-end on
this machine: ydotool key injection (kernel uinput), per-window XWayland
screenshots, the saved-node boot trick (`AAA_Settings.last_selected_node`),
and loguru DEBUG lines as assertable signals. The full recipe lives in
`.claude/skills/verify/SKILL.md`.

Question discussed: can this become a repeatable GUI testing tool?

Conclusion: yes, as a **Claude-in-the-loop acceptance/smoke layer** — scripted
scenarios producing screenshot + log artifacts, with Claude (or a human) as
the visual oracle. It sees the bug class the unit suite structurally cannot:
pixel-space rendering, focus behavior, kv wiring. Exhibit: on 2026-07-20 two
wiki table bugs (a scrollbar overlaying the last table row; link markup
leaking underline/color across wrapped rows) existed while all unit tests
passed — both are obvious in a screenshot. The app's 10-foot remote UX
(Esc/Enter/arrows reach nearly every state) is what makes blind keyboard
driving viable at all.

## The ladder (if/when built)

1. **Scenario runner** — formalize the verify-skill recipe: seed a scratch
   config → launch → replay a key script → capture screenshots/logs at
   checkpoints → restore. Scenarios as data files; artifacts reviewed by
   Claude.
2. **Deterministic dev mode in the app** ← the highest-leverage piece; see
   below. Turns "Claude eyeballs one run" into "runs comparable over time",
   and enables coarse pixel-diff as a cheap first-pass filter (judge only the
   frames that changed).
3. **In-process autopilot** — a debug flag where the app itself replays key
   events through Kivy's event loop and captures via `Window.screenshot()`;
   no OS injection, deterministic, potentially CI-able under Xvfb + llvmpipe.

## Deterministic dev mode: the four sources of run-to-run variation

### 1. Random art selection (the big one)

`ImageSelector` picks random panel images for every decorative surface —
main-screen backgrounds, fun images, and wiki page backgrounds via
`BarksPanelsImageProvider.background_for` (`core/wiki_integration.py`).
Its recently-used no-repeat tracking makes selection **path-dependent**:
what page N shows depends on the pages visited before it.

**Pin:** inject the RNG — a `random.Random(seed)` threaded into
`ImageSelector`, seed from an env var, defaulting to today's behavior when
unset. Constructor injection is already the house pattern (platform-services
refactor), so this is small plumbing. Seeded beats "fixed image" because it
still exercises the real pipeline (zip decrypt, PNG re-encode, tinting).
`FixedColorSource` in the background machinery shows the fixed-background
seam already half-exists if ever wanted.

### 2. Window geometry

Wrapping (wiki tree rows, table overflow, scroll landings) is a function of
window width. Size today = saved config filtered through the
monitor-adaptive logic in `AppWindowGeometryHelper` plus Mutter/Wayland
clamping quirks (see `docs/` + memory: resizable=1, position=custom). A
different monitor or a WM nudge silently invalidates both screenshots and
key-nav scripts.

**Pin:** env override for exact width x height + position that bypasses
adaptive sizing and aspect corrections. The suppression hooks already exist
(cf. `test_resize_skipped_when_suppression_active`).

### 3. Mutable state files

The app rewrites `barks-reader.json` and reading history every run — hence
the verify skill's fragile backup/restore dance, and the no-repeat image
memory lives here too.

**Pin:** free already — `BARKS_READER_CONFIG_DIR` pointed at a scratch dir
with canned config (including the saved-node entry point) and canned
history. Hermetic, disposable, never touches the real profile. No app
change needed.

### 4. Timing

Screenshots race lazy tree expansion, texture creation, and scrim/band
animations; sleeps are the flakiest part of the current approach.

**Pin:** not an animation kill-switch (invasive, changes what is tested) —
instead one "page settled" DEBUG log line when a page finishes layout (the
wiki viewer's settle-poll already detects this moment internally). The
runner screenshots on signal, not on sleep.

## Design principles

- **Same binary.** Env-gated (`BARKS_READER_RNG_SEED`,
  `BARKS_READER_FIXED_GEOMETRY`, existing `BARKS_READER_CONFIG_DIR`) — never
  a special test build; what is tested is what ships.
- **Graceful degradation.** Every pin unset → exactly current behavior.
- With pins 1–3, a scenario is a pure function:
  seed + geometry + config dir + key script → frames.

## Known limits (unchanged by the dev mode)

- Fixes *reproducibility*, not *coverage*: mouse-only flows and
  search-result activation stay undrivable (portal-mediated clicks,
  focused-TextInput key swallowing) — those need unit tests regardless.
- Machine-bound (real display, ydotool setup) unless rung 3 is built.
- Slow (~12s launch + settle waits); cannot run while the machine is in use.
