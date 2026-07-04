"""Unit tests for the OKF reader's pure render layer (``scripts/okf_render.py``).

These pin the kivy-free core contract — frontmatter parsing, markdown-to-Kivy-
markup rendering, and bundle-bounded link resolution — before the module grows.
When ``okf_render`` moves into ``barks_reader.core``, delete the sys.path shim
below and import from the package instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

# okf_render currently lives in scripts/ as a standalone spike. Until it moves
# into barks_reader.core, put the scripts dir on sys.path so we can import it.
# Appended (not inserted) so this global, session-wide path entry can't shadow a
# same-named module another test resolves earlier; okf_render is unique to scripts/.
# TODO: replace with `from barks_reader.core.okf.render import ...` after the move.
_SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(_SCRIPTS_DIR))

import okf_render as okf  # noqa: E402  (import follows the sys.path shim above)  # ty: ignore[unresolved-import]


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
        """A traversal that escapes the bundle root is rejected."""
        bundle = self._bundle(tmp_path)
        target = okf.resolve_link(bundle / "concept" / "a.md", "../../../../etc/passwd", bundle)
        assert target is None

    def test_missing_file_is_none(self, tmp_path: Path) -> None:
        """A path inside the bundle that does not exist resolves to None."""
        bundle = self._bundle(tmp_path)
        assert okf.resolve_link(bundle / "concept" / "a.md", "sub/missing.md", bundle) is None


class TestRenderPage:
    def test_heading_markup_and_size(self) -> None:
        """A heading becomes a bold block sized from HEADING_SIZES."""
        page = okf.render_page("# Title")
        assert page.frontmatter == {}
        assert page.blocks[0].markup == "[b]Title[/b]"
        assert page.blocks[0].font_size == okf.HEADING_SIZES["h1"]

    def test_inline_emphasis_and_code(self) -> None:
        """Bold, italic, and inline code map to Kivy markup tags."""
        page = okf.render_page("**bold** _it_ `code`")
        markup = page.blocks[0].markup
        assert "[b]bold[/b]" in markup
        assert "[i]it[/i]" in markup
        assert f"[color={okf.CODE_COLOR}]code[/color]" in markup

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

    def test_footnote_marker_and_definition(self) -> None:
        """A footnote yields a tappable marker, a 'Footnotes' header, and an anchored def."""
        page = okf.render_page("Here[^1] is a claim.\n\n[^1]: The supporting detail.")
        assert any("[ref=fn:1]" in b.markup for b in page.blocks)  # the marker
        assert any(b.markup == "[b]Footnotes[/b]" for b in page.blocks)  # the section header
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
        assert (alpha.title, alpha.path) == ("Alpha", concept / "alpha.md")
        assert (zeta.title, zeta.path) == ("zeta", concept / "zeta.md")  # stem fallback

    def test_nested_directory_recursed(self, tmp_path: Path) -> None:
        """Subdirectories become nested BundleDirs holding their own concepts."""
        concept = self._bundle(tmp_path)
        sub = okf.load_bundle_tree(concept).children[1]
        assert isinstance(sub, okf.BundleDir)
        assert sub.name == "sub"
        assert len(sub.children) == 1
        assert sub.children[0].title == "Beta"

    def test_non_directory_root_is_empty(self, tmp_path: Path) -> None:
        """A root that is not a directory yields an empty BundleDir (no raise)."""
        f = tmp_path / "lonely.md"
        f.write_text("---\ntype: x\n---\nB", encoding="utf-8")
        tree = okf.load_bundle_tree(f)
        assert isinstance(tree, okf.BundleDir)
        assert tree.children == ()


class TestEsc:
    def test_escapes_markup_metacharacters(self) -> None:
        """_esc escapes ampersand and both square brackets, and nothing else."""
        assert okf._esc("a & b [c] d") == "a &amp; b &bl;c&br; d"  # noqa: SLF001
