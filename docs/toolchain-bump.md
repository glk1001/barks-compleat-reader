# Toolchain bump runbook

Canonical for all three barks repos: `barks-compleat-reader`, `barks-comic-building`,
`barks-ocr`. Each has its own `scripts/bump-toolchain.sh`; this document explains why
it exists and how to triage what it finds.

## TL;DR

On the 1st of the month, in each repo:

```bash
bash scripts/bump-toolchain.sh
```

It refuses on a dirty tree, makes a `toolchain-bump-YYYY-MM-DD` branch, moves
`ruff`/`ty`/`pyrefly` to their latest PyPI releases, re-locks, re-syncs, and runs
`scripts/full-lint.sh`. **It never commits and never pushes.** You review the diff and
decide.

## Why the tools are pinned at all

`ruff` and `ty` are pinned with `==` in `pyproject.toml`. `pyrefly` is not. That
asymmetry is deliberate.

**ruff — pinned because of `select = ["ALL"]`.** With `ALL` in `.ruff-base.toml`, any
ruff release that stabilizes a rule out of preview is a change to *our lint policy*,
not just a version bump. Version 0.16.0 added 388 errors across CPY001/PLR0917 on its
own. That is not a tool-stability problem, it is the price of `ALL`: new rules arrive
opted-in-by-default. If we ever drop `ALL` for an explicit select list, rolling ruff
becomes genuinely safe and the pin can go.

**ty — pinned because it is a 0.0.x beta.** Versions 0.0.62 and 0.0.63 shipped a flaky
salsa panic (`assertion failed: provisional_status.is_provisional()`) that aborted up
to 39 files on roughly 1 in 3 full-project runs. It was found by bisecting over 6 runs
per version; 0.0.64 fixed it (17 consecutive clean runs). A *flaky* gate is the worst
failure mode available, because it does not present as "the tool broke", it presents
as "my code intermittently fails CI". Stay pinned until ty reaches 1.0 (targeted 2026).

**pyrefly — not pinned, because it is 1.x with real semver.** It still gates, so a
release that adds rules can fail the gate; the difference is that a 1.x project makes
a stability promise a 0.0.x project explicitly does not.

## Why a script rather than just unpinning

Unpinning would not actually give you rolling versions. `uv.lock` is committed and CI
runs plain `uv sync`, so the locked version is what runs regardless of whether the
constraint says `==0.16.0` or `>=0.16.0`. The real difference is one line of edit at
bump time. That is a very cheap tripwire in exchange for choosing *when* the 388-error
diff lands — on a branch you opened deliberately, rather than under an unrelated
commit on a day you needed to ship something else.

The value of a new lint rule arriving today rather than in three weeks is near zero.
The cost of a gate breaking at a moment you did not choose is not.

## Triaging a bump

The script prints a per-tool summary and the gate result, then leaves everything on
the branch.

**Gates passed.** Review and commit:

```bash
git diff pyproject.toml uv.lock
```

**ruff check now fails.** Almost always new rules stabilizing out of preview. For
each: fix it, or if the rule is wrong for this codebase, add it to the ignore list in
`.ruff-base.toml` with a comment saying why. Do not blanket-ignore a whole rule family
to get green.

**ruff format wants to reformat.** Formatter changes are usually small and mechanical.
Run `uv run ruff format .` and eyeball the diff; it lands as part of the bump commit.

**ty fails or panics.** First check whether it is deterministic — run it three or four
times. An intermittent failure is the 0.0.62 pattern repeating: do not bump, and note
the bad version. A deterministic new error is usually a genuine tightening; fix it.

**pyrefly fails.** In `barks-compleat-reader` the gate is 0 *new* findings against
`pyrefly-baseline.json`. If a release adds rules, refresh deliberately after reading
the new entries:

```bash
bash scripts/pyrefly.sh --update-baseline
```

In `barks-comic-building` and `barks-ocr` the gate is a plain 0 errors with no
baseline. Keep it that way: fix the finding, or suppress it at the line with a
`# pyrefly: ignore[<rule>]` comment saying why.

**Abandoning a bump.** The script prints the exact commands; in short:

```bash
git checkout main && git branch -D toolchain-bump-YYYY-MM-DD
uv sync   # restore the venv to the pinned versions
```

Note that `uv sync` matters — the failed bump will have left the venv on the new
versions even after the files are reverted.

## Per-repo differences

| | reader | comic-building | ocr |
|---|---|---|---|
| pyrefly gate | 0 new vs baseline | 0 errors, no baseline | 0 errors, no baseline |
| `full-lint.sh` extras | import-linter, deptry, vulture, kv-imports, benchmarks | deptry | — |
| CI | GitHub Actions | none | none |

Only the reader has CI, so in the other two `scripts/full-lint.sh` plus pre-commit
*are* the gate. That makes running this script there more important, not less.

## Flags

```bash
bash scripts/bump-toolchain.sh              # ruff, ty, pyrefly
bash scripts/bump-toolchain.sh ruff         # one tool only
bash scripts/bump-toolchain.sh --no-branch  # bump in place, no branch
```
