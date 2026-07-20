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

    def test_triple_dash_inside_value_not_a_delimiter(self) -> None:
        """Only a whole '---' line closes the block, not a '---' inside a value."""
        fm, body = okf.parse_frontmatter("---\ntitle: A---B\ntype: x\n---\nBody")
        assert fm == {"title": "A---B", "type": "x"}
        assert body == "Body"


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


def _text_blocks(page: okf.Page) -> list[okf.Block]:
    """Return the page's plain text blocks, type-narrowed past ``TableBlock`` for ty."""
    return [b for b in page.blocks if isinstance(b, okf.Block)]


class TestRenderPage:
    def test_heading_markup_and_size(self) -> None:
        """A heading becomes a bold, heading-colored block sized from HEADING_SIZES."""
        page = okf.render_page("# Title")
        assert page.frontmatter == {}
        block = _text_blocks(page)[0]
        assert block.markup == f"[color={okf.HEADING_COLOR}][b]Title[/b][/color]"
        assert block.font_size == okf.HEADING_SIZES["h1"]
        assert block.heading  # headings start a new visual section in consumers

    def test_heading_flag_set_only_on_headings(self) -> None:
        """Paragraphs are not section starters; the Footnotes header is."""
        page = okf.render_page("# H\n\npara[^1]\n\n[^1]: def")
        flags = [(b.markup[:20], b.heading) for b in _text_blocks(page)]
        assert flags[0][1]  # the h1
        assert not flags[1][1]  # the paragraph
        footnotes_header = next(b for b in _text_blocks(page) if "Footnotes" in b.markup)
        assert footnotes_header.heading

    def test_heading_and_link_colors_default_to_module_palette(self) -> None:
        """With no override, headings/links carry the standalone module colors."""
        page = okf.render_page("# Title\n\n[text](foo.md)")
        blocks = _text_blocks(page)
        assert blocks[0].markup == f"[color={okf.HEADING_COLOR}][b]Title[/b][/color]"
        assert f"[color={okf.LINK_COLOR}]" in blocks[1].markup

    def test_heading_and_link_colors_are_themable(self) -> None:
        """An embedding app recolors headings and links via render_page args."""
        page = okf.render_page(
            "# Title\n\n[text](foo.md)", heading_color="ff0000", link_color="00ff00"
        )
        blocks = _text_blocks(page)
        assert blocks[0].markup == "[color=ff0000][b]Title[/b][/color]"
        assert "[color=00ff00]" in blocks[1].markup
        # The standalone defaults must not leak through when overridden.
        assert okf.HEADING_COLOR not in blocks[0].markup
        assert okf.LINK_COLOR not in blocks[1].markup

    def test_table_header_and_footnote_ref_follow_theme_colors(self) -> None:
        """Themed colors reach table headers (heading) and footnote refs (link)."""
        table = "| Col |\n| --- |\n| v |"
        table_block = next(
            b
            for b in okf.render_page(table, heading_color="abcdef").blocks
            if isinstance(b, okf.TableBlock)
        )
        assert any("[color=abcdef]" in row for row in table_block.rows)
        ref_markup = _text_blocks(okf.render_page("body[^1]\n\n[^1]: def", link_color="123456"))[
            0
        ].markup
        assert "[color=123456]" in ref_markup

    def test_inline_emphasis_and_code(self) -> None:
        """Bold, italic, and inline code map to Kivy markup tags."""
        markup = _text_blocks(okf.render_page("**bold** _it_ `code`"))[0].markup
        assert "[b]bold[/b]" in markup
        assert "[i]it[/i]" in markup
        assert f"[color={okf.CODE_COLOR}]code[/color]" in markup

    def test_provenance_notes_dropped(self) -> None:
        """Editorial provenance blockquotes (marked "LLM-owned") are not rendered."""
        md = (
            "> _LLM-owned synthesis. Do not hand-edit — regenerated on reingest."
            " See `CLAUDE.md`._\n\nReal content.\n"
        )
        blocks = _text_blocks(okf.render_page(md))
        assert not any(okf.PROVENANCE_MARKER in b.markup for b in blocks)
        assert any("Real content." in b.markup for b in blocks)

    def test_provenance_glossary_variant_dropped(self) -> None:
        """The glossary-entry variants of the provenance note are dropped too."""
        md = "> _Glossary entry — a recurring place-name. LLM-owned._\n\nBody.\n"
        assert [b.markup for b in _text_blocks(okf.render_page(md))] == ["Body."]

    def test_link_becomes_ref(self) -> None:
        """An inline link becomes a tappable [ref=…] span carrying the href."""
        markup = _text_blocks(okf.render_page("[text](foo.md)"))[0].markup
        assert "[ref=foo.md]" in markup
        assert f"[color={okf.LINK_COLOR}][u]text[/u]" in markup

    def test_href_markup_metacharacters_percent_encoded(self, tmp_path: Path) -> None:
        """An href with '&' is percent-encoded in [ref=…] and round-trips via resolve_link.

        A raw '&' (which markdown-it passes through, unlike brackets) would corrupt
        the Kivy markup; encoding it survives because resolve_link percent-decodes.
        """
        markup = _text_blocks(okf.render_page("[text](a&b.md)"))[0].markup
        assert "[ref=a%26b.md]" in markup
        target = tmp_path / "a&b.md"
        target.write_text("---\ntype: x\n---\nT", encoding="utf-8")
        assert okf.resolve_link(tmp_path / "page.md", "a%26b.md", tmp_path) == target

    def test_special_characters_escaped(self) -> None:
        """The three Kivy-markup metacharacters are escaped in body text."""
        markup = _text_blocks(okf.render_page("price 5 & 6 [note]"))[0].markup
        assert "&amp;" in markup
        assert "&bl;note&br;" in markup
        assert "[note]" not in markup  # the literal brackets must not survive

    def test_bullet_list_marker_and_indent(self) -> None:
        """List items carry the bullet in the marker slot, not baked into the text."""
        blocks = _text_blocks(okf.render_page("- one\n- two"))
        assert [(b.marker, b.indent, b.markup) for b in blocks] == [
            ("•", 1, "one"),
            ("•", 1, "two"),
        ]

    def test_list_continuation_paragraph_indented_without_marker(self) -> None:
        """A loose item's second paragraph aligns under the text: indent, no marker."""
        blocks = _text_blocks(okf.render_page("- first para\n\n  second para\n- next"))
        assert [(b.marker, b.indent, b.markup) for b in blocks] == [
            ("•", 1, "first para"),
            ("", 1, "second para"),
            ("•", 1, "next"),
        ]

    def test_blockquote_paragraph_indented_without_marker(self) -> None:
        """A blockquote paragraph is indented one level, with no marker glyph."""
        blocks = _text_blocks(okf.render_page("> quoted text"))
        assert [(b.marker, b.indent, b.markup) for b in blocks] == [("", 1, "quoted text")]

    def test_code_fence_block(self) -> None:
        """A fenced code block is a colored block at the code font size."""
        blocks = _text_blocks(okf.render_page("```\nsome_code()\n```"))
        assert any(b.markup == f"[color={okf.CODE_COLOR}]some_code()[/color]" for b in blocks)

    def test_thematic_break_block(self) -> None:
        """A thematic break renders as a horizontal rule block."""
        blocks = _text_blocks(okf.render_page("para one\n\n***\n\npara two"))
        assert any(set(b.markup) == {"─"} for b in blocks)

    def test_html_block_shown_as_code(self) -> None:
        """A raw HTML block is displayed code-style rather than silently dropped."""
        blocks = _text_blocks(okf.render_page("Before.\n\n<div>block html</div>\n\nAfter."))
        expected = f"[color={okf.CODE_COLOR}]<div>block html</div>[/color]"
        assert [b.markup for b in blocks] == ["Before.", expected, "After."]

    def test_html_comment_block_skipped(self) -> None:
        """A pure HTML comment is author metadata, not content, and is not rendered."""
        md = "Before.\n\n<!-- bib-notes-mined -->\n\nAfter."
        blocks = _text_blocks(okf.render_page(md))
        assert [b.markup for b in blocks] == ["Before.", "After."]

    def test_image_placeholder(self) -> None:
        """An image reference renders as an italic placeholder, never embedded."""
        markup = _text_blocks(okf.render_page("![alt text](img.png)"))[0].markup
        assert "▨ image: alt text" in markup

    def test_ordered_list_numbered(self) -> None:
        """Ordered-list items keep their numbers instead of degrading to bullets."""
        blocks = _text_blocks(okf.render_page("1. first\n2. second"))
        assert [(b.marker, b.markup) for b in blocks] == [("1.", "first"), ("2.", "second")]

    def test_ordered_list_start_and_renumbering(self) -> None:
        """Numbering runs sequentially from the list's start, as CommonMark renders it."""
        blocks = _text_blocks(okf.render_page("3. a\n3. b"))  # source repeats '3.'
        assert [(b.marker, b.markup) for b in blocks] == [("3.", "a"), ("4.", "b")]

    def test_ordered_list_numbering_survives_nested_bullets(self) -> None:
        """A nested bullet list neither resets nor inherits the outer numbering."""
        blocks = _text_blocks(okf.render_page("1. a\n   - sub\n2. b"))
        assert [(b.marker, b.indent, b.markup) for b in blocks] == [
            ("1.", 1, "a"),
            ("•", 2, "sub"),
            ("2.", 1, "b"),
        ]

    def test_table_rows_padded_to_aligned_columns(self) -> None:
        """A table becomes a TableBlock: colored header, cells space-padded per column.

        Padding counts *visible* characters, so a cell's markup tags don't skew
        its column ("two" aligns despite its [i]…[/i] wrapper).
        """
        md = "| Col A | Col B |\n|-------|-------|\n| one   | *two* |\n| three | four  |\n"
        blocks = okf.render_page(md).blocks
        assert len(blocks) == 1
        table = blocks[0]
        assert isinstance(table, okf.TableBlock)
        assert table.rows[0] == f"[color={okf.HEADING_COLOR}]Col A  Col B[/color]"
        assert table.rows[1] == "one    [i]two[/i]"  # "one" padded to width of "three"
        assert table.rows[2] == "three  four"

    def test_table_long_cell_wraps_within_its_column(self) -> None:
        """A cell past TABLE_COL_WRAP_WIDTH wraps at word boundaries inside its column."""
        a, b, c = "a" * 20, "b" * 20, "c" * 10
        md = f"| T | N |\n|---|---|\n| {a} {b} {c} | x |\n| short | y |\n"
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        # Column width = the widest wrapped line (31), not the unwrapped cell (52).
        assert table.rows[1] == f"{a}{' ' * 11}  x\n{b} {c}"
        assert table.rows[2] == f"short{' ' * 26}  y"

    def test_table_wrap_never_splits_markup_tags(self) -> None:
        """Wrapping breaks at visible spaces only; a split tag pair is re-balanced per line."""
        a, b, c = "a" * 20, "b" * 20, "c" * 10
        md = f"| T | N |\n|---|---|\n| *{a} {b} {c}* | x |\n"
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        # [i]…[/i] closes at each line's end and reopens on the next; padding
        # counts visible chars only.
        assert table.rows[1] == f"[i]{a}[/i]{' ' * 11}  x\n[i]{b} {c}[/i]"

    def test_table_wrapped_link_cell_keeps_markup_out_of_next_column(self) -> None:
        """A wrapped link cell must not leak its ref/color/underline across the row.

        Each physical line closes the link's tags before the row's remaining
        columns are appended, and the continuation line reopens them — otherwise
        the still-open [u]/[color]/[ref] would style (and hit-test) every cell
        to the row's right.
        """
        md = (
            "| Vol | Title | Yrs |\n|---|---|---|\n"
            "| 14 | [The Seven Cities of Gold and Then Some](x.md) | 1954-55 |\n"
        )
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        link_open = f"[ref=x.md][color={okf.LINK_COLOR}][u]"
        assert table.rows[1] == (
            f" 14  {link_open}The Seven Cities of Gold and[/u][/color][/ref]  1954-55\n"
            f"     {link_open}Then Some[/u][/color][/ref]"
        )

    def test_table_numeric_columns_right_justified(self) -> None:
        """A column of plain numbers is right-justified; text columns stay left."""
        md = "| Title | Pages |\n|---|---|\n| A Story | 8 |\n| Longer Story | -1.00 |\n"
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        assert table.rows[0] == f"[color={okf.HEADING_COLOR}]Title{' ' * 7}  Pages[/color]"
        assert table.rows[1] == f"A Story{' ' * 5}  {' ' * 4}8"
        assert table.rows[2] == "Longer Story  -1.00"  # negatives count as numeric

    def test_table_mixed_column_stays_left_justified(self) -> None:
        """One non-numeric cell (e.g. a page code) keeps the whole column left-justified."""
        md = "| Pg | X |\n|---|---|\n| 151 | a |\n| 570b | b |\n"
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        assert table.rows[1] == "151   a"  # "151" left-justified in the 4-wide column
        assert table.rows[2] == "570b  b"

    def test_table_rewriter_transforms_before_layout(self) -> None:
        """A TableRewriter reshapes (header, body) and the layout follows the result."""

        class FoldFlagIntoTitle:
            """Drop the 'F' column, parenthesizing 'T' cells on rows where it is empty."""

            def rewrite(
                self, header: list[str], body: list[list[str]]
            ) -> tuple[list[str], list[list[str]]]:
                assert header == ["T", "F"]
                new_body = [[cell if flag else f"({cell})"] for cell, flag in body]
                return [header[0]], new_body

            def wrap_widths(self, header: list[str]) -> list[int | None]:
                return [None] * len(header)

        md = "| T | F |\n|---|---|\n| own | x |\n| assigned |  |\n"
        table = okf.render_page(md, table_rewriter=FoldFlagIntoTitle()).blocks[0]
        assert isinstance(table, okf.TableBlock)
        assert table.rows == [
            f"[color={okf.HEADING_COLOR}]T[/color]",  # single column left; still colored
            "own",
            "(assigned)",
        ]

    def test_table_rewriter_per_column_wrap_override(self) -> None:
        """A rewriter's wrap_widths override wraps a column sooner than the default."""

        class NarrowFirstColumn:
            def rewrite(
                self, header: list[str], body: list[list[str]]
            ) -> tuple[list[str], list[list[str]]]:
                return header, body

            def wrap_widths(self, header: list[str]) -> list[int | None]:
                assert header == ["A", "B"]
                return [6, None]

        md = "| A | B |\n|---|---|\n| aaa bbb | x |\n"
        table = okf.render_page(md, table_rewriter=NarrowFirstColumn()).blocks[0]
        assert isinstance(table, okf.TableBlock)
        # "aaa bbb" (7 visible) is under the 32 default but over the override of 6.
        assert table.rows[1] == "aaa  x\nbbb"

    def test_table_unbreakable_word_does_not_widen_column(self) -> None:
        """A single word past TABLE_COL_WRAP_WIDTH overflows its own row, not the column."""
        long_cell = "L" * (okf.TABLE_COL_WRAP_WIDTH + 10)
        md = f"| A | B |\n|---|---|\n| short | x |\n| {long_cell} | y |\n"
        table = okf.render_page(md).blocks[0]
        assert isinstance(table, okf.TableBlock)
        assert table.rows[1] == "short  x"  # column width set by "short", not the outlier
        assert table.rows[2] == f"{long_cell}  y"  # the outlier row alone runs long

    def test_table_between_paragraphs(self) -> None:
        """Surrounding paragraphs are unaffected by the table's token consumption."""
        md = "Before.\n\n| H |\n|---|\n| cell |\n\nAfter.\n"
        page = okf.render_page(md)
        assert [b.markup for b in _text_blocks(page)] == ["Before.", "After."]
        table = page.blocks[1]
        assert isinstance(table, okf.TableBlock)
        assert table.rows == [f"[color={okf.HEADING_COLOR}]H[/color]", "cell"]

    def test_footnote_marker_and_definition(self) -> None:
        """A footnote yields a tappable marker, a 'Footnotes' header, and an anchored def."""
        page = okf.render_page("Here[^1] is a claim.\n\n[^1]: The supporting detail.")
        blocks = _text_blocks(page)
        marker = next(b.markup for b in blocks if "[ref=fn:1]" in b.markup)
        # Raised by [sup]; the inner [size=…] overrides [sup]'s halving of the font size.
        assert f"[sup][size={okf.FOOTNOTE_REF_SIZE}]&bl;1&br;[/size][/sup]" in marker
        footnotes_header = f"[color={okf.HEADING_COLOR}][b]Footnotes[/b][/color]"
        assert any(b.markup == footnotes_header for b in blocks)  # the section header
        defs = [b for b in blocks if b.anchor == "fn:1"]
        assert len(defs) == 1
        assert "The supporting detail." in defs[0].markup
        # Definitions are metadata: dimmed grey, wrapping the whole block.
        assert defs[0].markup.startswith(f"[color={okf.FOOTNOTE_TEXT_COLOR}]")
        assert defs[0].markup.endswith("[/color]")

    def test_footnote_code_dimmed_body_code_not(self) -> None:
        """Inline code is muted inside footnote definitions, full-color in the body."""
        page = okf.render_page("Body `code`[^1].\n\n[^1]: See `path/to/file.py`.")
        blocks = _text_blocks(page)
        body = next(b.markup for b in blocks if "Body" in b.markup)
        assert f"[color={okf.CODE_COLOR}]code[/color]" in body
        definition = next(b.markup for b in blocks if b.anchor == "fn:1")
        assert f"[color={okf.FOOTNOTE_CODE_COLOR}]path/to/file.py[/color]" in definition


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


class TestEsc:
    def test_escapes_markup_metacharacters(self) -> None:
        """_esc escapes ampersand and both square brackets, and nothing else."""
        assert okf._esc("a & b [c] d") == "a &amp; b &bl;c&br; d"  # noqa: SLF001
