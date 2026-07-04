"""Unit tests for the OKF reader's pure core (``okf_reader.core.render``).

These pin the kivy-free core contract — frontmatter parsing, markdown-to-Kivy-
markup rendering, bundle-bounded link resolution, and the bundle tree model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from okf_reader.core import render as okf

if TYPE_CHECKING:
    from pathlib import Path


class TestParseFrontmatter:
    def test_valid_frontmatter_split(self) -> None:
        """A well-formed block yields the parsed dict and the stripped body."""
        fm, body = okf.parse_frontmatter("---\ntitle: X\ntype: concept\n---\nBody here")
        assert fm == {"title": "X", "type": "concept"}
        assert body == "Body here"

    def test_no_frontmatter(self) -> None:
        """Text without a leading block returns an empty dict and the text unchanged."""
        fm, body = okf.parse_frontmatter("Just a body, no frontmatter.")
        assert fm == {}
        assert body == "Just a body, no frontmatter."

    def test_malformed_yaml_falls_back_to_empty(self) -> None:
        """Invalid YAML degrades to an empty dict rather than raising (SPEC §9 tolerance)."""
        fm, body = okf.parse_frontmatter("---\nfoo: [1, 2\n---\nBody")
        assert fm == {}
        assert body == "Body"

    def test_non_mapping_frontmatter_ignored(self) -> None:
        """A YAML block that parses to a list (not a mapping) is treated as no frontmatter."""
        fm, body = okf.parse_frontmatter("---\n- item1\n- item2\n---\nBody")
        assert fm == {}
        assert body == "Body"

    def test_horizontal_rule_in_body_preserved(self) -> None:
        """A '---' inside the body survives (split is bounded to the frontmatter)."""
        fm, body = okf.parse_frontmatter("---\ntype: x\n---\nBefore\n\n---\n\nAfter")
        assert fm == {"type": "x"}
        assert "---" in body
        assert body.endswith("After")


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


class TestRenderPage:
    def test_heading_markup_and_size(self) -> None:
        """A heading becomes a bold, heading-colored block sized from HEADING_SIZES."""
        page = okf.render_page("# Title")
        assert page.frontmatter == {}
        assert page.blocks[0].markup == f"[color={okf.HEADING_COLOR}][b]Title[/b][/color]"
        assert page.blocks[0].font_size == okf.HEADING_SIZES["h1"]

    def test_inline_emphasis_and_code(self) -> None:
        """Bold, italic, and inline code map to Kivy markup tags."""
        page = okf.render_page("**bold** _it_ `code`")
        markup = page.blocks[0].markup
        assert "[b]bold[/b]" in markup
        assert "[i]it[/i]" in markup
        assert f"[color={okf.CODE_COLOR}]code[/color]" in markup

    def test_provenance_notes_dropped(self) -> None:
        """Editorial provenance blockquotes (marked "LLM-owned") are not rendered."""
        md = (
            "> _LLM-owned synthesis. Do not hand-edit — regenerated on reingest."
            " See `CLAUDE.md`._\n\nReal content.\n"
        )
        page = okf.render_page(md)
        assert not any(okf.PROVENANCE_MARKER in b.markup for b in page.blocks)
        assert any("Real content." in b.markup for b in page.blocks)

    def test_provenance_glossary_variant_dropped(self) -> None:
        """The glossary-entry variants of the provenance note are dropped too."""
        md = "> _Glossary entry — a recurring place-name. LLM-owned._\n\nBody.\n"
        page = okf.render_page(md)
        assert [b.markup for b in page.blocks] == ["Body."]

    def test_link_becomes_ref(self) -> None:
        """An inline link becomes a tappable [ref=…] span carrying the href."""
        markup = okf.render_page("[text](foo.md)").blocks[0].markup
        assert "[ref=foo.md]" in markup
        assert f"[color={okf.LINK_COLOR}][u]text[/u]" in markup

    def test_special_characters_escaped(self) -> None:
        """The three Kivy-markup metacharacters are escaped in body text."""
        markup = okf.render_page("price 5 & 6 [note]").blocks[0].markup
        assert "&amp;" in markup
        assert "&bl;note&br;" in markup
        assert "[note]" not in markup  # the literal brackets must not survive

    def test_bullet_list_prefix(self) -> None:
        """List items are prefixed with a bullet glyph."""
        blocks = okf.render_page("- one\n- two").blocks
        assert any(b.markup.startswith("•  one") for b in blocks)
        assert any(b.markup.startswith("•  two") for b in blocks)

    def test_code_fence_block(self) -> None:
        """A fenced code block is a colored block at the code font size."""
        blocks = okf.render_page("```\nsome_code()\n```").blocks
        assert any(b.markup == f"[color={okf.CODE_COLOR}]some_code()[/color]" for b in blocks)

    def test_thematic_break_block(self) -> None:
        """A thematic break renders as a horizontal rule block."""
        blocks = okf.render_page("para one\n\n***\n\npara two").blocks
        assert any(set(b.markup) == {"─"} for b in blocks)

    def test_image_placeholder(self) -> None:
        """An image reference renders as an italic placeholder, never embedded."""
        markup = okf.render_page("![alt text](img.png)").blocks[0].markup
        assert "▨ image: alt text" in markup

    def test_table_rows_and_cells_preserved(self) -> None:
        """A table renders as one block of pipe-joined rows: bold header, all cells kept."""
        md = "| Col A | Col B |\n|-------|-------|\n| one   | *two* |\n| three | four  |\n"
        blocks = okf.render_page(md).blocks
        assert len(blocks) == 1
        rows = blocks[0].markup.split("\n")
        assert rows[0] == "[b]Col A[/b]  |  [b]Col B[/b]"
        assert rows[1] == "one  |  [i]two[/i]"  # inline markup works inside cells
        assert rows[2] == "three  |  four"

    def test_table_between_paragraphs(self) -> None:
        """Surrounding paragraphs are unaffected by the table's token consumption."""
        md = "Before.\n\n| H |\n|---|\n| cell |\n\nAfter.\n"
        markups = [b.markup for b in okf.render_page(md).blocks]
        assert markups == ["Before.", "[b]H[/b]\ncell", "After."]

    def test_footnote_marker_and_definition(self) -> None:
        """A footnote yields a tappable marker, a 'Footnotes' header, and an anchored def."""
        page = okf.render_page("Here[^1] is a claim.\n\n[^1]: The supporting detail.")
        marker = next(b.markup for b in page.blocks if "[ref=fn:1]" in b.markup)
        # Raised by [sup]; the inner [size=…] overrides [sup]'s halving of the font size.
        assert f"[sup][size={okf.FOOTNOTE_REF_SIZE}]&bl;1&br;[/size][/sup]" in marker
        footnotes_header = f"[color={okf.HEADING_COLOR}][b]Footnotes[/b][/color]"
        assert any(b.markup == footnotes_header for b in page.blocks)  # the section header
        defs = [b for b in page.blocks if b.anchor == "fn:1"]
        assert len(defs) == 1
        assert "The supporting detail." in defs[0].markup


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

    def test_index_without_heading_falls_back(self, tmp_path: Path) -> None:
        """An index.md with no '# ' heading still falls back to the name."""
        d = tmp_path / "some-dir"
        d.mkdir()
        (d / "index.md").write_text("just prose, no heading\n", encoding="utf-8")
        assert okf.dir_title(d) == "Some Dir"


class TestLoadBundleTree:
    @staticmethod
    def _bundle(tmp_path: Path) -> Path:
        """Build concept/ with two leaves, a subdir, and reserved files to skip."""
        concept = tmp_path / "concept"
        (concept / "sub").mkdir(parents=True)
        (concept / "alpha.md").write_text("---\ntype: x\ntitle: Alpha\n---\nA", encoding="utf-8")
        (concept / "zeta.md").write_text("---\ntype: x\n---\nZ", encoding="utf-8")  # no title
        (concept / "sub" / "beta.md").write_text("---\ntype: x\ntitle: Beta\n---\nB", "utf-8")
        (concept / "index.md").write_text("# reserved", encoding="utf-8")
        (concept / "log.md").write_text("# reserved", encoding="utf-8")
        return concept

    def test_structure_order_and_reserved_skipped(self, tmp_path: Path) -> None:
        """Dirs and concepts interleave in name order; reserved files are excluded."""
        tree = okf.load_bundle_tree(self._bundle(tmp_path))
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
        concept = self._bundle(tmp_path)
        tree = okf.load_bundle_tree(concept)
        alpha, _sub, zeta = tree.children
        assert isinstance(alpha, okf.ConceptNode)
        assert isinstance(zeta, okf.ConceptNode)
        assert (alpha.title, alpha.path) == ("Alpha", concept / "alpha.md")
        assert (zeta.title, zeta.path) == ("zeta", concept / "zeta.md")  # stem fallback

    def test_nested_directory_recursed(self, tmp_path: Path) -> None:
        """Subdirectories become nested BundleDirs holding their own concepts."""
        concept = self._bundle(tmp_path)
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


class TestListChildren:
    @staticmethod
    def _bundle(tmp_path: Path) -> Path:
        """Build concept/ with a leaf, a non-empty subdir, and a reserved file."""
        concept = tmp_path / "concept"
        (concept / "sub").mkdir(parents=True)
        (concept / "alpha.md").write_text("---\ntype: x\ntitle: Alpha\n---\nA", encoding="utf-8")
        (concept / "zeta.md").write_text("---\ntype: x\n---\nZ", encoding="utf-8")  # no title
        (concept / "sub" / "beta.md").write_text("---\ntype: x\ntitle: Beta\n---\nB", "utf-8")
        (concept / "index.md").write_text("# reserved", encoding="utf-8")
        return concept

    def test_one_level_only_subdirs_unexpanded(self, tmp_path: Path) -> None:
        """Children are name-ordered, interleaved, and subdirs come back unexpanded."""
        concept = self._bundle(tmp_path)
        kids = okf.list_children(concept)
        assert [type(c).__name__ for c in kids] == ["ConceptNode", "BundleDir", "ConceptNode"]
        sub = kids[1]
        assert isinstance(sub, okf.BundleDir)
        assert sub.children == ()  # not recursed...
        assert (sub.path / "beta.md").is_file()  # ...even though it has a child on disk
        assert sub.title == "Sub"  # no index.md → Title Cased name (see TestDirTitle)

    def test_reserved_skipped_and_titles_resolved(self, tmp_path: Path) -> None:
        """Reserved files are excluded; leaves carry frontmatter title or stem fallback."""
        kids = okf.list_children(self._bundle(tmp_path))
        assert not any(getattr(c, "path", None) and c.path.name == "index.md" for c in kids)
        alpha, _sub, zeta = kids
        assert isinstance(alpha, okf.ConceptNode)
        assert isinstance(zeta, okf.ConceptNode)
        assert alpha.title == "Alpha"
        assert zeta.title == "zeta"

    def test_descend_by_calling_again(self, tmp_path: Path) -> None:
        """Descending a subdir is a second list_children call on its path."""
        concept = self._bundle(tmp_path)
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


class TestEsc:
    def test_escapes_markup_metacharacters(self) -> None:
        """_esc escapes ampersand and both square brackets, and nothing else."""
        assert okf._esc("a & b [c] d") == "a &amp; b &bl;c&br; d"  # noqa: SLF001
