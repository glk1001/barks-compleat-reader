# Commands

The scripts a session reaches for only on a particular task. The everyday ones (first-time
hooks, the two gitignored modules, the lint gates, pyrefly's baseline) are in `CLAUDE.md`, and a
clean machine's whole setup, in order, is in `docs/setup.md`.

**What the hooks need** (after `uv run prek install`):
The hooks run on [prek](https://github.com/j178/prek), as in the two sibling repos; it comes from
the `dev` dependency group (`uv sync`) and reads `.pre-commit-config.yaml`. The cspell hooks also
need [bun](https://bun.sh) on the PATH (on Windows it also needs a `bunx.cmd`: `docs/setup.md`).
The pre-commit stage also runs [gitleaks](https://github.com/gitleaks/gitleaks) (secrets in what is
staged), the one hook not from the uv venv: prek builds its pinned release once per machine, about
30 s on the first commit, fetching Go itself.

**Run benchmarks** (excluded from the default test run; `--quiet` for just the tables):
```bash
bash scripts/run_benchmark.sh
```

**Run the whole repo overnight** (results in `build/overnight/<stamp>/summary.txt`; on Windows
or macOS, `uv run python scripts/run_overnight_desktop.py`). Setting up another machine, the
desktop runner, the nightly schedule, macOS permissions and cross-platform coverage: the
`overnight-runs` skill (`.claude/skills/overnight-runs/SKILL.md`).
```bash
bash scripts/run_overnight.sh
```

**Run every GUI test overnight** (stages and options: the `overnight-runs` skill):
```bash
bash scripts/run_gui_overnight.sh
```
Ctrl-C or `kill` of any GUI runner stops everything it started. After a `kill -9`
the next run clears the leftovers, or `bash scripts/gui-probe.sh cleanup` does (`--all`
also stops a display started by hand).

**Look over every popup** (PNGs and contact sheets in `build/popup-gallery/<stamp>/`; `--live`
steps through them in the real app; plan: `docs/plans/popup-consistency.md`):
```bash
uv run scripts/popup_gallery.py
```

**Run the GUI path tests** (excluded from the default test run; boots the real app on
the nested Xephyr display via `scripts/gui-probe.sh`, driven by `scripts/gui_driver.py`):
```bash
bash scripts/run_gui_tests.sh
```

**Spell-check (cspell):**
```bash
bunx cspell
```

**Check whether a new data pack is due** (this PC's Reader Files folders, but for the wiki
copy, against the published pack's version file, `scripts/data-pack-manifest.json`; the overnight `data`
stage asks the same on the main PC; `--write-pack-manifest` is how `build-data-zips.sh`
stamps the packs):
```bash
uv run scripts/data_manifest.py --pack
```

**Render the app's icons from their SVG sources** (`assets/reader-icon-sources`, with
Inkscape, into Reader Files and, in black, into `docs/` for the how-to; `--list` says where
each goes; then `--record icons` below and regenerate the how-to's pages):
```bash
uv run scripts/render_reader_icons.py
```

**Check the generated files are current** (the how-to's pages, the introduction's page,
the app's icons and the Statistics screen's word table and clouds, each held to the hashes of its sources
and of its files in `scripts/generated-files.json`; `validate` runs the same check;
`--list`; after regenerating a set, `--record NAME` or `--record all`, then commit the record;
the how-to's backgrounds are in the Fantagraphics fixes directories, so a machine without
them leaves those out of the check and cannot record the how-to):
```bash
uv run scripts/generated_files.py
uv run scripts/generated_files.py --record how-to
```

**Check the docs name things that exist** (paths, modules, script flags, links, `BARKS_*`
variables; no line numbers in the evergreen docs; `--only RULE`, `--quiet`):
```bash
uv run scripts/check_docs_refs.py
```

**Bump the pinned toolchain (monthly):**
`ruff` and `ty` are `==`-pinned in `pyproject.toml` (a `select = ["ALL"]` ruff release
changes our lint policy; ty is a 0.0.x beta that has shipped a flaky panic). This moves
them forward on a branch, re-locks, and runs every gate — it never commits or pushes.
Full rationale and triage steps in `docs/toolchain-bump.md`.
```bash
bash scripts/bump-toolchain.sh
```

**Build standalone executable:**
```bash
bash scripts/build.sh
```
