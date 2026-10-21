"""Unit tests for the OKF reader's bundle model (``okf_reader.core.bundle``).

These pin the kivy-free bundle contract — bundle-bounded link resolution, concept
and directory titles, and the lazy and eager bundle tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from okf_reader.core import bundle as okf

if TYPE_CHECKING:
    from pathlib import Path


class TestResolveLink:
    @staticmethod
    def _bundle(tmp_path: Path) -> Path:
        """Build a tiny bundle: concept/a.md and concept/sub/b.md."""
        (tmp_path / "concept" / "sub").mkdir(parents=True)
        (tmp_path / "concept" / "a.md").write_text("---\ntype: x\n---\nA", encoding="utf-8")
        (tmp_path / "concept" / "sub" / "b.md").write_text("---\ntype: x\n---\nB", encoding="utf-8")
        return tmp_path

    def test_relative_link_against_page_dir(self, tmp_path: Path) -> None:
        """A relative href resolves against the linking page's directory."""
        bundle = self._bundle(tmp_path)
        target = okf.resolve_link(bundle / "concept" / "a.md", "sub/b.md", bundle)
        assert target == (bundle / "concept" / "sub" / "b.md")

    def test_absolute_link_against_bundle_root(self, tmp_path: Path) -> None:
        """An absolute '/…' href resolves against the bundle root (SPEC §5.1)."""
        bundle = self._bundle(tmp_path)
        target = okf.resolve_link(bundle / "concept" / "a.md", "/concept/sub/b.md", bundle)
        assert target == (bundle / "concept" / "sub" / "b.md")

    def test_trailing_anchor_stripped(self, tmp_path: Path) -> None:
        """A heading anchor on the href is dropped before resolving the file."""
        bundle = self._bundle(tmp_path)
        target = okf.resolve_link(bundle / "concept" / "a.md", "sub/b.md#section", bundle)
        assert target == (bundle / "concept" / "sub" / "b.md")

    def test_external_link_is_none(self, tmp_path: Path) -> None:
        """Links with a scheme are external and do not resolve to a file."""
        bundle = self._bundle(tmp_path)
        page = bundle / "concept" / "a.md"
        assert okf.resolve_link(page, "https://example.com", bundle) is None
        assert okf.resolve_link(page, "http://example.com/x", bundle) is None

    def test_anchor_only_is_none(self, tmp_path: Path) -> None:
        """A pure '#anchor' href has no file target."""
        bundle = self._bundle(tmp_path)
        assert okf.resolve_link(bundle / "concept" / "a.md", "#section", bundle) is None

    def test_escape_outside_bundle_rejected(self, tmp_path: Path) -> None:
        """A .md traversal that escapes the bundle root is rejected by the bounds check."""
        bundle = self._bundle(tmp_path)
        target = okf.resolve_link(bundle / "concept" / "a.md", "../../../../etc/secret.md", bundle)
        assert target is None

    def test_missing_file_is_none(self, tmp_path: Path) -> None:
        """A path inside the bundle that does not exist resolves to None."""
        bundle = self._bundle(tmp_path)
        assert okf.resolve_link(bundle / "concept" / "a.md", "sub/missing.md", bundle) is None

    def test_percent_encoded_path_decoded(self, tmp_path: Path) -> None:
        """A percent-encoded href (spaces, '#', parens) decodes to the real filename."""
        bundle = self._bundle(tmp_path)
        weird = bundle / "concept" / "My Note # 4 (draft).md"
        weird.write_text("---\ntype: x\n---\nW", encoding="utf-8")
        href = "My%20Note%20%23%204%20%28draft%29.md"  # in-path '#' is %23, not a fragment
        assert okf.resolve_link(bundle / "concept" / "a.md", href, bundle) == weird

    def test_non_markdown_target_is_none(self, tmp_path: Path) -> None:
        """A link to a non-.md asset (e.g. scraped .html) is not a navigable concept."""
        bundle = self._bundle(tmp_path)
        (bundle / "concept" / "page.html").write_text("<html></html>", encoding="utf-8")
        assert okf.resolve_link(bundle / "concept" / "a.md", "page.html", bundle) is None

    def test_directory_link_is_none(self, tmp_path: Path) -> None:
        """A link to a directory (trailing slash) is not a navigable concept."""
        bundle = self._bundle(tmp_path)
        assert okf.resolve_link(bundle / "concept" / "a.md", "sub/", bundle) is None


class TestConceptTitle:
    def test_frontmatter_title_used(self, tmp_path: Path) -> None:
        """A concept's frontmatter ``title`` is its display title."""
        p = tmp_path / "c.md"
        p.write_text("---\ntype: concept\ntitle: Real Title\n---\nBody", encoding="utf-8")
        assert okf.concept_title(p) == "Real Title"

    def test_missing_title_falls_back_to_stem(self, tmp_path: Path) -> None:
        """With no ``title`` key, the filename stem is used."""
        p = tmp_path / "my-concept.md"
        p.write_text("---\ntype: concept\n---\nBody", encoding="utf-8")
        assert okf.concept_title(p) == "my-concept"

    def test_empty_or_null_title_falls_back_to_stem(self, tmp_path: Path) -> None:
        """An empty or null ``title`` is ignored in favour of the stem."""
        empty = tmp_path / "e.md"
        empty.write_text('---\ntype: concept\ntitle: ""\n---\nBody', encoding="utf-8")
        null = tmp_path / "n.md"
        null.write_text("---\ntype: concept\ntitle:\n---\nBody", encoding="utf-8")
        assert okf.concept_title(empty) == "e"
        assert okf.concept_title(null) == "n"

    def test_unreadable_file_falls_back_to_stem(self, tmp_path: Path) -> None:
        """A path that cannot be read as text (here: a directory) falls back to the stem."""
        trap = tmp_path / "broken.md"
        trap.mkdir()  # read_text raises IsADirectoryError, an OSError
        assert okf.concept_title(trap) == "broken"


class TestDirTitle:
    def test_index_md_heading_used(self, tmp_path: Path) -> None:
        """A directory's index.md heading is its display title."""
        d = tmp_path / "comics-and-stories"
        d.mkdir()
        (d / "index.md").write_text("# Comics and Stories\n\nListing…\n", encoding="utf-8")
        assert okf.dir_title(d) == "Comics and Stories"

    def test_heading_found_after_frontmatter(self, tmp_path: Path) -> None:
        """The bundle-root index.md may carry frontmatter before its heading."""
        (tmp_path / "index.md").write_text(
            '---\nokf_version: "0.1"\n---\n\n# Knowledge Bundle Root\n', encoding="utf-8"
        )
        assert okf.dir_title(tmp_path) == "Knowledge Bundle Root"

    def test_missing_index_falls_back_to_title_case(self, tmp_path: Path) -> None:
        """Without index.md, the kebab/underscore name is Title Cased."""
        d = tmp_path / "blum-barksian_extreme"
        d.mkdir()
        assert okf.dir_title(d) == "Blum Barksian Extreme"

    def test_yaml_comment_in_frontmatter_not_a_heading(self, tmp_path: Path) -> None:
        """A '# …' line inside the frontmatter block is a YAML comment, not the title."""
        d = tmp_path / "real-name"
        d.mkdir()
        (d / "index.md").write_text(
            "---\n# generated file\ntype: index\n---\n\n# Real Heading\n", encoding="utf-8"
        )
        assert okf.dir_title(d) == "Real Heading"

    def test_heading_inside_code_fence_skipped(self, tmp_path: Path) -> None:
        """A '# …' line inside a fenced code block is code, not the title."""
        d = tmp_path / "some-dir"
        d.mkdir()
        (d / "index.md").write_text(
            "```\n# not a heading\n```\n\n# The Heading\n", encoding="utf-8"
        )
        assert okf.dir_title(d) == "The Heading"

    def test_index_without_heading_falls_back(self, tmp_path: Path) -> None:
        """An index.md with no '# ' heading still falls back to the name."""
        d = tmp_path / "some-dir"
        d.mkdir()
        (d / "index.md").write_text("just prose, no heading\n", encoding="utf-8")
        assert okf.dir_title(d) == "Some Dir"


def _make_concept_dir(tmp_path: Path) -> Path:
    """Build concept/ with two leaves, a non-empty subdir, and reserved files to skip."""
    concept = tmp_path / "concept"
    (concept / "sub").mkdir(parents=True)
    (concept / "alpha.md").write_text("---\ntype: x\ntitle: Alpha\n---\nA", encoding="utf-8")
    (concept / "zeta.md").write_text("---\ntype: x\n---\nZ", encoding="utf-8")  # no title
    (concept / "sub" / "beta.md").write_text("---\ntype: x\ntitle: Beta\n---\nB", "utf-8")
    (concept / "index.md").write_text("# reserved", encoding="utf-8")
    (concept / "log.md").write_text("# reserved", encoding="utf-8")
    return concept


class TestLoadBundleTree:
    def test_structure_order_and_reserved_skipped(self, tmp_path: Path) -> None:
        """Dirs and concepts interleave in name order; reserved files are excluded."""
        tree = okf.load_bundle_tree(_make_concept_dir(tmp_path))
        assert tree.name == "concept"
        # name order of concept/: alpha.md, index.md, log.md, sub, zeta.md
        # → after skipping reserved: alpha (concept), sub (dir), zeta (concept)
        assert [type(c).__name__ for c in tree.children] == [
            "ConceptNode",
            "BundleDir",
            "ConceptNode",
        ]
        assert not any(
            isinstance(c, okf.ConceptNode) and c.path.name in okf.RESERVED_FILES
            for c in tree.children
        )

    def test_concept_titles_and_paths(self, tmp_path: Path) -> None:
        """Leaves carry the resolved title and the concept's file path."""
        concept = _make_concept_dir(tmp_path)
        tree = okf.load_bundle_tree(concept)
        alpha, _sub, zeta = tree.children
        assert isinstance(alpha, okf.ConceptNode)
        assert isinstance(zeta, okf.ConceptNode)
        assert (alpha.title, alpha.path) == ("Alpha", concept / "alpha.md")
        assert (zeta.title, zeta.path) == ("zeta", concept / "zeta.md")  # stem fallback

    def test_nested_directory_recursed(self, tmp_path: Path) -> None:
        """Subdirectories become nested BundleDirs holding their own concepts."""
        concept = _make_concept_dir(tmp_path)
        sub = okf.load_bundle_tree(concept).children[1]
        assert isinstance(sub, okf.BundleDir)
        assert sub.name == "sub"
        assert len(sub.children) == 1
        beta = sub.children[0]
        assert isinstance(beta, okf.ConceptNode)
        assert beta.title == "Beta"

    def test_non_directory_root_is_empty(self, tmp_path: Path) -> None:
        """A root that is not a directory yields an empty BundleDir (no raise)."""
        f = tmp_path / "lonely.md"
        f.write_text("---\ntype: x\n---\nB", encoding="utf-8")
        tree = okf.load_bundle_tree(f)
        assert isinstance(tree, okf.BundleDir)
        assert tree.children == ()


class TestHasChildren:
    def test_dir_with_concepts_or_subdirs(self, tmp_path: Path) -> None:
        """A directory with a concept or a subdirectory has children."""
        assert okf.has_children(_make_concept_dir(tmp_path))
        subdir_only = tmp_path / "subdir-only"
        (subdir_only / "sub").mkdir(parents=True)
        assert okf.has_children(subdir_only)

    def test_only_reserved_and_hidden_entries_is_empty(self, tmp_path: Path) -> None:
        """Reserved files and dot-entries don't count — nothing would be listed."""
        d = tmp_path / "quiet"
        (d / ".obsidian").mkdir(parents=True)
        (d / "index.md").write_text("# reserved", encoding="utf-8")
        (d / "log.md").write_text("# reserved", encoding="utf-8")
        (d / "notes.txt").write_text("not a concept", encoding="utf-8")
        assert not okf.has_children(d)

    def test_non_directory_is_empty(self, tmp_path: Path) -> None:
        """A non-directory path has no children, not an error."""
        assert not okf.has_children(tmp_path / "nowhere")


class TestListChildren:
    def test_one_level_only_subdirs_unexpanded(self, tmp_path: Path) -> None:
        """Children are name-ordered, interleaved, and subdirs come back unexpanded."""
        concept = _make_concept_dir(tmp_path)
        kids = okf.list_children(concept)
        assert [type(c).__name__ for c in kids] == ["ConceptNode", "BundleDir", "ConceptNode"]
        sub = kids[1]
        assert isinstance(sub, okf.BundleDir)
        assert sub.children == ()  # not recursed...
        assert (sub.path / "beta.md").is_file()  # ...even though it has a child on disk
        assert sub.title == "Sub"  # no index.md → Title Cased name (see TestDirTitle)

    def test_reserved_skipped_and_titles_resolved(self, tmp_path: Path) -> None:
        """Reserved files are excluded; leaves carry frontmatter title or stem fallback."""
        kids = okf.list_children(_make_concept_dir(tmp_path))
        assert not any(getattr(c, "path", None) and c.path.name == "index.md" for c in kids)
        alpha, _sub, zeta = kids
        assert isinstance(alpha, okf.ConceptNode)
        assert isinstance(zeta, okf.ConceptNode)
        assert alpha.title == "Alpha"
        assert zeta.title == "zeta"

    def test_descend_by_calling_again(self, tmp_path: Path) -> None:
        """Descending a subdir is a second list_children call on its path."""
        concept = _make_concept_dir(tmp_path)
        sub = okf.list_children(concept)[1]
        descendants = okf.list_children(sub.path)
        assert [c.title for c in descendants if isinstance(c, okf.ConceptNode)] == ["Beta"]

    def test_non_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """A non-directory path yields an empty list, not an error."""
        f = tmp_path / "lonely.md"
        f.write_text("---\ntype: x\n---\nB", encoding="utf-8")
        assert okf.list_children(f) == []

    def test_hidden_entries_skipped(self, tmp_path: Path) -> None:
        """Dot-entries (e.g. .obsidian, dotfiles) are not OKF content and are skipped."""
        root = tmp_path / "bundle"
        (root / ".obsidian").mkdir(parents=True)
        (root / ".secret.md").write_text("---\ntype: x\n---\nS", encoding="utf-8")
        (root / "real.md").write_text("---\ntype: x\ntitle: Real\n---\nR", encoding="utf-8")
        kids = okf.list_children(root)
        assert [c.title for c in kids if isinstance(c, okf.ConceptNode)] == ["Real"]


class TestIndexLinkOrder:
    """list_children follows the curated link order of the directory's index.md."""

    @staticmethod
    def _make_bundle_root(tmp_path: Path, index_body: str) -> Path:
        """Build a root with three subdirs, two concepts, and the given index.md body."""
        root = tmp_path / "bundle"
        for name in ("assets-meta", "concept", "reference"):
            (root / name).mkdir(parents=True)
        (root / "alpha.md").write_text("---\ntype: x\ntitle: Alpha\n---\nA", encoding="utf-8")
        (root / "zeta.md").write_text("---\ntype: x\ntitle: Zeta\n---\nZ", encoding="utf-8")
        (root / "index.md").write_text(index_body, encoding="utf-8")
        return root

    def test_listed_children_keep_index_order(self, tmp_path: Path) -> None:
        """Linked children come first, in link order; dirs and concepts alike."""
        root = self._make_bundle_root(
            tmp_path,
            "# Root\n\n"
            "* [The Wiki](concept/index.md)\n"
            "* [Zeta](zeta.md)\n"
            "* [Reference](reference/index.md)\n"
            "* [Assets Meta](assets-meta/index.md)\n"
            "* [Alpha](alpha.md)\n",
        )
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["concept", "zeta.md", "reference", "assets-meta", "alpha.md"]

    def test_unlisted_children_follow_in_name_order(self, tmp_path: Path) -> None:
        """Children the index.md doesn't list trail the listed ones, alphabetically."""
        root = self._make_bundle_root(
            tmp_path, "# Root\n\n* [Reference](reference/index.md)\n* [Zeta](zeta.md)\n"
        )
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["reference", "zeta.md", "alpha.md", "assets-meta", "concept"]

    def test_prose_links_do_not_count(self, tmp_path: Path) -> None:
        """A link in running prose is a mention, not a listing entry."""
        root = self._make_bundle_root(
            tmp_path,
            "# Root\n\nSee [Zeta](zeta.md) for background.\n\n* [Reference](reference/index.md)\n",
        )
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["reference", "alpha.md", "assets-meta", "concept", "zeta.md"]

    def test_external_absolute_and_parent_links_ignored(self, tmp_path: Path) -> None:
        """Scheme-bearing, absolute /… and ../ links never rank a child."""
        root = self._make_bundle_root(
            tmp_path,
            "# Root\n\n"
            "* [Ext](https://example.com/concept)\n"
            "* [Abs](/reference/index.md)\n"
            "* [Up](../elsewhere.md)\n"
            "* [Zeta](zeta.md)\n",
        )
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["zeta.md", "alpha.md", "assets-meta", "concept", "reference"]

    def test_deep_link_ranks_its_first_segment(self, tmp_path: Path) -> None:
        """A link into a subtree charges the immediate child it enters."""
        root = self._make_bundle_root(
            tmp_path, "# Root\n\n* [Story](concept/stories/lost-in-the-andes.md)\n"
        )
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["concept", "alpha.md", "assets-meta", "reference", "zeta.md"]

    def test_no_index_md_is_name_order(self, tmp_path: Path) -> None:
        """Without an index.md the listing stays plain name order."""
        root = self._make_bundle_root(tmp_path, "unused")
        (root / "index.md").unlink()
        names = [c.path.name for c in okf.list_children(root)]
        assert names == ["alpha.md", "assets-meta", "concept", "reference", "zeta.md"]
