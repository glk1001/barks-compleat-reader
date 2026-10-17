# ruff: noqa: T201 - a console check script prints its report by design.
"""Check that the docs name things that exist.

A doc rots in a few mechanical ways, and this check catches each of them:

- ``line-number``: a ``path.py:123`` reference in an evergreen doc (README,
  CLAUDE.md, the walkthrough, the how-to, ...). Line numbers drift within weeks,
  while symbol names hold, so those docs name paths and symbols only.
- ``path``: a back-ticked repo path, script name or directory that no longer
  exists. Resolved against the repo root, the doc's own folder, any tracked file
  with that suffix, the workspace packages' source trees and the sibling
  checkouts; a path git ignores (a generated module, ``.benchmarks/``) is fine.
- ``module``: a dotted ``barks_reader.core.something`` module that does not
  resolve in the workspace, or whose last component names nothing in it.
- ``flag``: ``script.sh --flag`` where the script's text has no ``--flag``.
  Only a flag written beside its script, in one backtick span or one line of a
  code block, is checked.
- ``link``: a relative markdown link or ``<img src>`` whose target is missing.
- ``env``: a ``BARKS_*`` variable that no script, source or config file mentions.

The dated working notes (``docs/plans/``, the backlog, the design review, the
debt ledgers) are records of what was proposed and seen, so they keep their line
numbers, flags and variable names, and only their links, modules and paths from
a repo top folder (``scripts/``, ``src/``, ``docs/``, ...) are judged.

A line that carries ``<!-- docs-refs: ok -->`` is skipped, and a doc holding
``<!-- docs-refs: skip -->`` is skipped whole. Every finding is a warning: the
check exits 1 when there are any, and ``full-lint.sh`` and the overnight run
report it without failing on it; the pre-commit hook gates only ``line-number``.

Run directly (``uv run scripts/check_docs_refs.py [--quiet] [--only RULE]... [DOC]...``).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent

RULES: tuple[str, ...] = ("line-number", "path", "module", "flag", "link", "env")
# A dated note is a record of what was proposed and seen, so only what it claims
# about this tree is judged: a path from a repo top folder, a module, a link.
DATED_NOTE_RULES: frozenset[str] = frozenset({"path", "module", "link"})

# Docs that are dated records rather than evergreen descriptions.
DATED_NOTES: tuple[str, ...] = (
    "docs/plans/",
    "docs/BACKLOG.md",
    "docs/design-review-2026-07.md",
    "docs/pyrefly-annotation-debt.md",
    "docs/mutation-testing.md",
    "docs/wiki-story-order-handover.md",
    "experiments/",
)
# Third-party docs vendored into the tree, not ours to keep current.
SKIPPED_DOCS: tuple[str, ...] = (".claude/skills/graphify/",)

# The workspace packages a dotted module path may start with.
PACKAGES: frozenset[str] = frozenset(
    {
        "barks_reader",
        "barks_fantagraphics",
        "comic_utils",
        "okf_reader",
        "barks_kivy_ui",
        "barks_build_comic_images",
    }
)
# A bare file name (no slash) is checked only with one of these extensions: a
# `.json` or `.ini` on its own is usually a runtime file the app writes.
CODE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".sh", ".ps1", ".kv", ".toml", ".yaml", ".yml", ".cfg", ".md", ".css"}
)
PATH_EXTENSIONS: frozenset[str] = CODE_EXTENSIONS | frozenset(
    {".json", ".ini", ".txt", ".png", ".jpg", ".svg", ".html", ".csv", ".fodt", ".c", ".dylib"}
)
SCRIPT_EXTENSIONS: frozenset[str] = frozenset({".py", ".sh", ".ps1"})
# Files whose text defines the BARKS_* variables the docs may name.
ENV_SOURCE_EXTENSIONS: frozenset[str] = CODE_EXTENSIONS - {".md"} | {".ini", ".json", ".txt"}
UNCHECKED_FLAGS: frozenset[str] = frozenset({"--help"})

OK_MARK = "<!-- docs-refs: ok -->"
SKIP_MARK = "<!-- docs-refs: skip -->"

_BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"^\s*(```|~~~)")
_EN_DASH = chr(0x2013)
_LINE_REF = re.compile(
    rf"^(?P<path>[^\s:]+\.(?:py|kv|sh|toml|yaml|yml|cfg))(?P<lines>:\d+(?:[-{_EN_DASH}]\d+)?)$"
)
_MODULE = re.compile(r"^(?P<pkg>[a-z_]+)(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_FLAG = re.compile(r"(?<![\w-])(--[a-z][\w-]*)")
# A target is bare, or in angle brackets as CommonMark allows (groma writes its index so),
# where it may hold spaces and the brackets are no part of the path.
_MD_LINK = re.compile(
    r"!?\[[^\]]*\]\((?:<(?P<angled>[^<>\n]+)>|(?P<bare>[^)\s]+))(?:\s+\"[^\"]*\")?\)"
)
_IMG_SRC = re.compile(r"<img[^>]*\ssrc=\"([^\"]+)\"")
_ENV_VAR = re.compile(r"\bBARKS_[A-Z][A-Z0-9_]*\b")
_WORD = re.compile(r"[^\s`'\"(),;|&<>]+")
# Characters that make a token a placeholder, a glob or a shell expression, not a path.
_NOT_A_PATH = re.compile(r"[*?{}<>$|…@\\]|://|\.\.\.")
_DRIVE = re.compile(r"^[A-Za-z]:/")
# The repo's own top-level folders: a path starting here is checked even in a dated note.
ANCHORS: tuple[str, ...] = (
    "scripts/",
    "src/",
    "docs/",
    "assets/",
    "website/",
    "experiments/",
    ".github/",
    ".claude/",
)
# Sibling checkouts the docs may name paths in, relative to those repos' roots.
SIBLINGS: tuple[str, ...] = ("barks-wiki", "barks-comic-building", "barks-ocr")


@dataclass(frozen=True)
class Finding:
    """One thing a doc names that the repo does not have."""

    doc: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        """Format as ``doc:line: [rule] message``, the shape editors jump on."""
        return f"{self.doc}:{self.line}: [{self.rule}] {self.message}"


@dataclass
class Repo:
    """The repo as the check sees it: a root and the files under it."""

    root: Path
    tracked: frozenset[str]
    _ignored_cache: dict[str, bool] = field(default_factory=dict, repr=False)
    _env_names: frozenset[str] | None = field(default=None, repr=False)

    @classmethod
    def discover(cls, root: Path) -> Repo:
        """Build from ``git ls-files`` at ``root``, or from a walk where that is no git repo."""
        try:
            out = _git(root, "ls-files", "-z")
        except (subprocess.CalledProcessError, OSError):
            return cls(root, frozenset(_walk(root)))
        return cls(root, frozenset(p for p in out.split("\0") if p))

    def docs(self) -> list[Path]:
        """Every tracked markdown doc that is ours."""
        return sorted(
            self.root / p
            for p in self.tracked
            if p.endswith(".md") and not p.startswith(SKIPPED_DOCS)
        )

    def rel(self, path: Path) -> str:
        """``path`` relative to the root, as posix, for messages and the dated-notes test.

        A doc outside the root (a copy being checked by hand) keeps its own path.
        """
        resolved = path.resolve()
        root = self.root.resolve()
        if resolved.is_relative_to(root):
            return resolved.relative_to(root).as_posix()
        return path.as_posix()

    def exists(self, token: str, doc_dir: Path) -> bool:
        """Whether a doc's path token names something in the repo (or git ignores it)."""
        candidates = [self.root / token, doc_dir / token]
        if any(c.exists() for c in candidates):
            return True
        if token.startswith("../"):
            # A sibling repo: only judged where that sibling is checked out.
            sibling = token.split("/")[1]
            return not (self.root.parent / sibling).is_dir()
        suffix = "/" + token.rstrip("/")
        if any(p.endswith(suffix) or p == token for p in self.tracked):
            return True
        in_workspace = (f"src/*/src/{token}", f"src/*/src/*/{token}", f"src/*/{token}")
        if any(next(self.root.glob(pattern), None) is not None for pattern in in_workspace):
            return True
        if self.in_a_sibling(token):
            return True
        return self.is_ignored(token)

    def in_a_sibling(self, token: str) -> bool:
        """Whether a sibling checkout has the path, at its root, under ``scripts/`` or near it."""
        name = token.rstrip("/")
        for sibling in SIBLINGS:
            base = self.root.parent / sibling
            if not base.is_dir():
                continue
            if (base / name).exists() or (base / "scripts" / name).exists():
                return True
            if "/" not in name and any(
                next(base.glob(pattern), None) is not None
                for pattern in (f"*/{name}", f"*/*/{name}", f"*/*/*/{name}")
            ):
                return True
        return False

    def is_ignored(self, rel: str) -> bool:
        """Whether git would ignore ``rel`` (a generated or local-only file)."""
        if rel not in self._ignored_cache:
            if not (self.root / ".git").exists():
                self._ignored_cache[rel] = False
            else:
                done = subprocess.run(  # noqa: S603 (git on this repo, fixed arguments)
                    ["git", "-C", str(self.root), "check-ignore", "-q", rel],  # noqa: S607
                    check=False,
                    capture_output=True,
                )
                self._ignored_cache[rel] = done.returncode == 0
        return self._ignored_cache[rel]

    def package_dir(self, package: str) -> Path | None:
        """Return the source directory of a workspace package, if there is one."""
        return next(iter(self.root.glob(f"src/*/src/{package}")), None)

    def env_names(self) -> frozenset[str]:
        """Every ``BARKS_*`` name a non-doc tracked file mentions."""
        if self._env_names is None:
            names: set[str] = set()
            for rel in self.tracked:
                path = self.root / rel
                if path.suffix in ENV_SOURCE_EXTENSIONS or path.name.startswith(".env"):
                    names.update(_ENV_VAR.findall(_read(path)))
            self._env_names = frozenset(names)
        return self._env_names

    def script_text(self, token: str, doc_dir: Path) -> str | None:
        """Return the text of the script a doc names, found the way ``exists`` finds it."""
        name = token.rstrip("/")
        for candidate in (self.root / name, doc_dir / name, self.root / "scripts" / name):
            if candidate.is_file():
                return _read(candidate)
        suffix = "/" + name
        for rel in sorted(self.tracked):
            if rel.endswith(suffix):
                return _read(self.root / rel)
        return None


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 (git on this repo, fixed arguments)
        ["git", "-C", str(root), *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


_SKIPPED_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", "build"})


def _walk(root: Path) -> Iterator[str]:
    """Yield every file under ``root`` as a posix path relative to it, skipping the usual bulk."""
    for path in root.rglob("*"):
        if path.is_file() and not _SKIPPED_DIRS & set(path.relative_to(root).parts):
            yield path.relative_to(root).as_posix()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


@dataclass(frozen=True)
class Line:
    """One line of a doc, with whether it sits inside a fenced code block."""

    number: int
    text: str
    in_code: bool


def lines_of(text: str) -> Iterator[Line]:
    """Yield the doc's lines, each flagged when a code fence encloses it."""
    in_code = False
    for number, raw in enumerate(text.splitlines(), start=1):
        if _FENCE.match(raw):
            in_code = not in_code
            continue
        yield Line(number, raw, in_code)


def spans_of(line: Line) -> list[str]:
    """Return the spans to look at on one line: back-ticked in prose, the whole line in code."""
    if line.in_code:
        return [line.text]
    return _BACKTICK_SPAN.findall(line.text)


def looks_like_path(token: str) -> bool:
    """Whether a token is a path worth checking (not a placeholder, URL or option).

    A directory needs two segments (``scripts/tests/``: a bare ``core/`` is shorthand
    for a package folder), a file with a data extension needs one of the repo's own
    folders in front of it (``website/shot.png``: ``config/barks-reader.ini`` is a
    runtime file), and a bare name is checked only with a code extension.
    """
    if token.startswith("../"):
        return True
    if not token or _NOT_A_PATH.search(token) or token[0] in "-~/#." or _DRIVE.match(token):
        return False
    name = token.rstrip("/").rsplit("/", 1)[-1]
    ext = Path(name).suffix.lower()
    if token.endswith("/"):
        return token.count("/") >= 2  # noqa: PLR2004 (two segments)
    if "/" in token:
        return ext in CODE_EXTENSIONS or (ext in PATH_EXTENSIONS and is_anchored(token))
    return ext in CODE_EXTENSIONS and name != ext


def is_anchored(token: str) -> bool:
    """Whether a path starts at one of the repo's own top-level folders."""
    return token.startswith(ANCHORS)


def _strip_line_ref(token: str) -> tuple[str, bool]:
    """Split ``path.py:12`` into the path and whether it carried a line number."""
    match = _LINE_REF.match(token)
    if match:
        return match["path"], True
    return token, False


class DocChecker:
    """Runs the rules over one doc."""

    def __init__(self, repo: Repo, doc: Path, rules: Iterable[str] = RULES) -> None:
        self.repo = repo
        self.doc = doc
        self.rel = repo.rel(doc)
        self.evergreen = not self.rel.startswith(DATED_NOTES)
        self.rules = frozenset(rules) if self.evergreen else frozenset(rules) & DATED_NOTE_RULES
        self.findings: list[Finding] = []
        self.checked: Counter[str] = Counter()

    def run(self) -> list[Finding]:
        """Check the doc; return its findings in line order."""
        text = _read(self.doc)
        if SKIP_MARK in text:
            return []
        for line in lines_of(text):
            if OK_MARK in line.text:
                continue
            for span in spans_of(line):
                self._check_span(line, span)
            if not line.in_code:
                self._check_links(line)
            self._check_env(line)
        return sorted(self.findings, key=lambda f: f.line)

    def _add(self, rule: str, line: Line, message: str) -> None:
        if rule in self.rules:
            self.findings.append(Finding(self.rel, line.number, rule, message))

    def _count(self, rule: str) -> None:
        if rule in self.rules:
            self.checked[rule] += 1

    def _check_span(self, line: Line, span: str) -> None:
        words = _WORD.findall(span)
        script: str | None = None
        for word in words:
            token, had_line = _strip_line_ref(word)
            if had_line and self.evergreen:
                self._count("line-number")
                self._add("line-number", line, f"`{word}`: name the symbol, not the line")
            if looks_like_path(token):
                if Path(token).suffix in SCRIPT_EXTENSIONS:
                    script = token
                if self._path_is_judged(token):
                    self._count("path")
                    if not self.repo.exists(token, self.doc.parent):
                        self._add("path", line, f"`{token}` does not exist")
            elif (module := _MODULE.match(token)) and module["pkg"] in PACKAGES:
                self._check_module(line, token)
            elif script and (flag := _FLAG.fullmatch(word.split("=", 1)[0])):
                self._check_flag(line, script, flag[1])

    def _path_is_judged(self, token: str) -> bool:
        """Every path in an evergreen doc; in a dated note, only one from a repo top folder.

        A plan names the files it proposed and a backlog names files in other repos: those
        are its record, not a claim about this tree. A path from one of the repo's own top
        folders is a claim wherever it is written.
        """
        return self.evergreen or is_anchored(token)

    def _check_module(self, line: Line, dotted: str) -> None:
        parts = dotted.split(".")
        current = self.repo.package_dir(parts[0])
        if current is None:
            return  # a package not in this workspace: not ours to judge
        self._count("module")
        rest = parts[1:]
        while rest and (current / rest[0]).is_dir():
            current = current / rest.pop(0)
        if rest and (current / f"{rest[0]}.py").is_file():
            current = current / f"{rest.pop(0)}.py"
        if not rest:
            return
        if (
            current.is_file()
            and len(rest) == 1
            and re.search(rf"\b{re.escape(rest[0])}\b", _read(current))
        ):
            return
        self._add("module", line, f"`{dotted}` does not resolve (stopped at `{'.'.join(rest)}`)")

    def _check_flag(self, line: Line, script: str, flag: str) -> None:
        if flag in UNCHECKED_FLAGS:
            return
        text = self.repo.script_text(script, self.doc.parent)
        if text is None:
            return
        self._count("flag")
        if flag not in text:
            self._add("flag", line, f"`{script}` has no `{flag}`")

    def _check_links(self, line: Line) -> None:
        targets = [
            found["angled"] or found["bare"] for found in _MD_LINK.finditer(line.text)
        ] + _IMG_SRC.findall(line.text)
        for target in targets:
            if target.startswith(("http://", "https://", "mailto:", "#")) or "://" in target:
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            self._count("link")
            if not (self.doc.parent / path).exists():
                self._add("link", line, f"link target `{target}` is missing")

    def _check_env(self, line: Line) -> None:
        if "env" not in self.rules:
            return
        known = self.repo.env_names()
        for name in _ENV_VAR.findall(line.text):
            if name.endswith("_"):
                continue
            self._count("env")
            if name not in known:
                self._add("env", line, f"`{name}` is set or read nowhere in the repo")


@dataclass(frozen=True)
class Report:
    """What a run over some docs found, and how much it looked at."""

    findings: list[Finding]
    checked: Counter[str]
    docs: int


def check_docs(repo: Repo, docs: Iterable[Path], rules: Iterable[str] = RULES) -> Report:
    """Run the rules over the docs."""
    rules = tuple(rules)
    findings: list[Finding] = []
    checked: Counter[str] = Counter()
    count = 0
    for doc in docs:
        checker = DocChecker(repo, doc, rules)
        findings.extend(checker.run())
        checked.update(checker.checked)
        count += 1
    return Report(findings, checked, count)


def main(argv: list[str] | None = None) -> int:
    """Check the docs (all tracked ones, or those given); return a process exit code."""
    parser = argparse.ArgumentParser(description="Check that the docs name things that exist.")
    parser.add_argument(
        "docs", nargs="*", type=Path, help="docs to check (default: every tracked .md)"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="the repo root")
    parser.add_argument(
        "--only",
        action="append",
        choices=RULES,
        metavar="RULE",
        help=f"run only this rule ({', '.join(RULES)})",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="print only the verdict, unless something is wrong"
    )
    args = parser.parse_args(argv)

    repo = Repo.discover(args.root)
    docs = [d.resolve() for d in args.docs] if args.docs else repo.docs()
    docs = [d for d in docs if d.suffix == ".md" and not repo.rel(d).startswith(SKIPPED_DOCS)]
    rules = tuple(args.only) if args.only else RULES
    report = check_docs(repo, docs, rules)
    looked_at = ", ".join(f"{report.checked[rule]} {rule}" for rule in rules)

    if report.findings:
        count = len(report.findings)
        print(f"{count} doc reference(s) the repo does not have, in {report.docs} doc(s):\n")
        for finding in report.findings:
            print(f"  {finding}")
        print(f"\nChecked: {looked_at}. A line carrying {OK_MARK} is skipped.")
        return 1
    if not args.quiet:
        print(f"Every reference checked in {report.docs} doc(s) exists ({looked_at}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
