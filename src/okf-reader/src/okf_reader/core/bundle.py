"""Kivy-free OKF bundle model — the directory tree and link resolution.

Walks a bundle directory into a `BundleDir`/`ConceptNode` tree and resolves the
links between its pages:

  * `resolve_link()` resolves both OKF link forms (SPEC §5): relative links
    against the page's dir, absolute `/…` links against the bundle root, both
    percent-decoded, bounds-checked under the bundle, and restricted to ``.md``
    concept documents;
  * `list_children()` / `load_bundle_tree()` enumerate a bundle one level at a
    time (lazy) or fully (eager), skipping reserved and hidden entries; children
    listed in a directory's reserved ``index.md`` keep that curated order.

Pages themselves are rendered by the sibling `okf_reader.core.render`, whose
frontmatter and markdown parsers this module shares.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING

from okf_reader.core.render import parse_frontmatter, parse_markdown

if TYPE_CHECKING:
    from pathlib import Path


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class ConceptNode:
    """A leaf in the bundle tree: one concept document and its display title."""

    path: Path
    title: str


@dataclass(frozen=True)
class BundleDir:
    """A directory node: its child directories and concept documents, in listing order."""

    path: Path
    name: str
    children: tuple[BundleDir | ConceptNode, ...] = ()
    # Human display title (see dir_title). Default "" keeps hand-built instances valid;
    # the model builders (list_children/load_bundle_tree) always fill it in.
    title: str = ""


# --------------------------------------------------------------------------- link resolution


def resolve_link(page_path: Path, href: str, bundle: Path) -> Path | None:
    """Resolve a markdown href to a navigable OKF concept, bounded to the bundle.

    Handles both OKF link forms (SPEC §5): an **absolute** bundle-relative href
    (``/concept/x.md``) resolves against the bundle root, a **relative** href
    against the page's directory. Link targets are URLs, so the path is **percent-decoded**
    (``%20`` → space, ``%23`` → ``#``); the heading fragment is split off the still-
    encoded href first, so an in-path ``#`` written ``%23`` survives while a real
    ``#anchor`` is dropped. Only ``.md`` concept documents are navigable — links to
    other assets (``.html``, images) or directories return None, as do external
    (scheme-bearing) links and anything outside the bundle.
    """
    if "://" in href:  # external link (carries a scheme)
        return None
    path_part = urllib.parse.unquote(href.split("#", 1)[0])  # fragment off, then decode
    if not path_part:
        return None
    base = bundle if path_part.startswith("/") else page_path.parent
    target = (base / path_part.lstrip("/")).resolve()
    if target.suffix != ".md":  # only OKF concept documents are rendered as pages
        # KNOWN LIMITATION (intentional): the bundle's source/web tier — notably the
        # inducks mirror — links to raw scraped .html assets, not OKF concepts, so
        # those links deliberately do not navigate. The sibling "<page>_files/index.md"
        # is only an auto-generated asset manifest, not readable content. Making inducks
        # useful is bundle curation (barks-wiki), not a reader fix. Revisit if/when we
        # add "open external/asset links in the system browser".
        return None
    try:
        target.relative_to(bundle.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


# --------------------------------------------------------------------------- bundle tree

RESERVED_FILES = ("index.md", "log.md")  # SPEC §3.1 — reserved, never concept documents


def concept_title(path: Path) -> str:
    """Display title for a concept file: its frontmatter ``title``, else the filename stem.

    An unreadable file also falls back to the stem (tolerant consumption, SPEC §9).
    """
    try:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return path.stem
    title = fm.get("title")
    return title if isinstance(title, str) and title else path.stem


def dir_title(path: Path) -> str:
    """Human title for a bundle directory.

    The reserved ``index.md`` (SPEC §3.1) is the directory's curated listing, and its
    first ``#`` heading names the directory — use that when present. The scan skips
    the frontmatter block (where a ``# …`` line is a YAML comment, not a heading) and
    fenced code blocks. Otherwise — no index.md, no heading, or an unreadable file —
    fall back to the directory name in Title Case ("comics-and-stories" → "Comics
    And Stories").
    """
    index = path / "index.md"
    if index.is_file():
        try:
            _, body = parse_frontmatter(index.read_text(encoding="utf-8"))
        except OSError:
            body = ""
        in_fence = False
        for line in body.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            elif not in_fence and line.startswith("# "):
                return line[2:].strip()
    return path.name.replace("-", " ").replace("_", " ").title()


def has_children(directory: Path) -> bool:
    """Whether a bundle directory has anything `list_children` would list.

    A cheap existence scan — no frontmatter reads — so a lazy consumer can decide
    whether a directory needs an expansion affordance without paying
    `list_children`'s per-concept file reads.
    """
    if not directory.is_dir():
        return False
    return any(
        not child.name.startswith(".")
        and (child.is_dir() or (child.suffix == ".md" and child.name not in RESERVED_FILES))
        for child in directory.iterdir()
    )


def _listed_child(href: str) -> str | None:
    """Return the immediate child an ``index.md`` listing link enters, or None.

    The child is the href's first path segment (``stories/x/index.md`` → ``stories``;
    ``good-deeds.md`` → itself). External (scheme-bearing), absolute ``/…`` (they
    name bundle-root children, not necessarily ours), and parent ``..`` links enter
    no child.
    """
    if "://" in href or href.startswith("/"):
        return None
    path_part = urllib.parse.unquote(href.split("#", 1)[0])
    first_segment = path_part.split("/", 1)[0]
    return None if first_segment in ("", ".", "..") else first_segment


def _index_link_order(directory: Path) -> dict[str, int]:
    """Rank each immediate child by its first mention in the directory's ``index.md``.

    The reserved ``index.md`` (SPEC §3.1) is the directory's *curated* listing, so
    the order of its listed links is the author's intended child order. Only links
    inside list items count — a link in surrounding prose is a mention, not a
    listing entry. Each qualifying href is charged to the immediate child it enters
    (`_listed_child`). A missing or unreadable index.md yields ``{}`` (tolerant
    consumption, SPEC §9).
    """
    index = directory / "index.md"
    if not index.is_file():
        return {}
    try:
        _, body = parse_frontmatter(index.read_text(encoding="utf-8"))
    except OSError:
        return {}
    order: dict[str, int] = {}
    list_depth = 0
    for token in parse_markdown(body):
        if token.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif token.type == "inline" and list_depth > 0:
            for child in token.children or []:
                if child.type == "link_open":
                    name = _listed_child(str(child.attrGet("href") or ""))
                    if name is not None:
                        order.setdefault(name, len(order))
    return order


def list_children(directory: Path) -> list[BundleDir | ConceptNode]:
    """Immediate children of a bundle directory, in curated order — one level only.

    Children linked from the directory's reserved ``index.md`` listing come first,
    in link order (`_index_link_order`); the rest follow in name order. A directory
    with no index.md (or one that lists nothing) is plain name order.

    Subdirectories come back as `BundleDir`s **unexpanded** (empty ``children``);
    call `list_children` again on a subdir's ``path`` to descend. Non-reserved
    ``.md`` files become `ConceptNode` leaves (``index.md``/``log.md`` are reserved
    — SPEC §3.1 — and skipped). Frontmatter is read only for the concepts directly
    in ``directory``, so a consumer can populate a tree lazily one level at a time.
    A ``directory`` that is not a directory yields an empty list (SPEC §9).
    """
    children: list[BundleDir | ConceptNode] = []
    if directory.is_dir():
        for child in sorted(directory.iterdir()):
            if child.name.startswith("."):
                continue  # skip hidden entries (e.g. .obsidian) — not OKF content
            if child.is_dir():
                children.append(BundleDir(child, child.name, title=dir_title(child)))
            elif child.suffix == ".md" and child.name not in RESERVED_FILES:
                children.append(ConceptNode(child, concept_title(child)))
        rank = _index_link_order(directory)
        # Stable sort over the name-ordered base: listed children first in listing
        # order, unlisted ones after, still alphabetical among themselves.
        children.sort(key=lambda child: rank.get(child.path.name, len(rank)))
    return children


def load_bundle_tree(root: Path) -> BundleDir:
    """Eagerly walk ``root`` into a fully-expanded Kivy-free tree.

    Like `list_children` but recursive: every subdirectory is descended and its
    `BundleDir.children` populated. A ``root`` that is not a directory yields an
    empty `BundleDir` (tolerant consumption, SPEC §9). Prefer `list_children` for
    interactive/lazy consumers; use this for a whole-bundle walk (e.g. search).
    """
    children = tuple(
        load_bundle_tree(child.path) if isinstance(child, BundleDir) else child
        for child in list_children(root)
    )
    return BundleDir(root, root.name, children, title=dir_title(root))
