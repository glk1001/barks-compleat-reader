"""Tests for the record of generated files: its sources, its comparison and its recording."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import generated_files
import pytest
from generated_files import (
    GENERATED_SETS,
    INDEX_SOURCE,
    GeneratedSet,
    ReaderDirs,
    background_sources,
    document_sources,
    folder_hash,
    load_record,
    record_sets,
    stale_reasons,
)
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from pathlib import Path

MD = '# Guide\n\n<img class="shot" src="shot.jpg" alt="a shot">\n\n![an icon](icons/dot.png)\n'
CSS = '@font-face { src: url("fonts/script.ttf"); }\nbody { color: black; }\n'
GUIDE = "guide"


def _dirs(root: Path) -> ReaderDirs:
    return ReaderDirs(
        how_to=root / "how-to",
        intro=root / "intro",
        statistics=root / "Statistics",
        indexes=root / "Indexes",
        reader_files=root,
    )


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    return write_tree(
        tmp_path / "src",
        {
            "guide.md": MD,
            "style.css": CSS,
            "shot.jpg": b"shot",
            "icons/dot.png": b"dot",
            "fonts/script.ttf": b"font",
        },
    )


@pytest.fixture
def dirs(tmp_path: Path) -> ReaderDirs:
    write_tree(tmp_path / "reader", {"how-to/page-1.jpg": b"one", "how-to/page-2.jpg": b"two"})
    return _dirs(tmp_path / "reader")


@pytest.fixture
def guide(source_dir: Path) -> tuple[GeneratedSet, ...]:
    return (
        GeneratedSet(
            GUIDE,
            lambda _dirs: document_sources(source_dir / "guide.md", source_dir / "style.css"),
            lambda dirs: sorted(dirs.how_to.glob("page-*")),
            "the generator",
        ),
    )


class TestDocumentSources:
    def test_the_markdown_s_images_and_the_stylesheet_s_files_are_sources(
        self, source_dir: Path
    ) -> None:
        found = document_sources(source_dir / "guide.md", source_dir / "style.css")

        assert {name.rsplit("/", 1)[-1] for name in found} == {
            "guide.md",
            "style.css",
            "shot.jpg",
            "dot.png",
            "script.ttf",
        }

    def test_an_extra_file_is_a_source(self, source_dir: Path) -> None:
        art = source_dir / "art.png"
        art.write_bytes(b"art")

        found = document_sources(source_dir / "guide.md", source_dir / "style.css", art)

        assert art.as_posix() in found

    def test_a_source_that_is_gone_is_named_missing(self, source_dir: Path) -> None:
        (source_dir / "shot.jpg").unlink()

        found = document_sources(source_dir / "guide.md", source_dir / "style.css")

        assert found[(source_dir / "shot.jpg").as_posix()] == "missing"

    def test_a_remote_image_is_no_file_to_hash(self, source_dir: Path) -> None:
        (source_dir / "guide.md").write_text(
            '<img src="https://example.com/a.png">\n', encoding="utf-8"
        )

        found = document_sources(source_dir / "guide.md", source_dir / "style.css")

        assert not any("example.com" in name for name in found)

    def test_a_source_in_the_repo_is_named_from_its_root(self) -> None:
        found = document_sources(generated_files.HOW_TO_MD, generated_files.HOW_TO_CSS)

        assert "docs/how-to-use.md" in found
        assert "scripts/how-to-style.css" in found
        assert "missing" not in found.values()


class TestBackgroundSources:
    def test_each_is_hashed_under_its_name_and_one_that_is_gone_is_missing(
        self, tmp_path: Path
    ) -> None:
        fixes = write_tree(tmp_path / "fixes", {"Vol 7/images/244.jpg": b"art"})
        backgrounds = {
            "fixes/Vol 7/images/244.jpg": fixes / "Vol 7/images/244.jpg",
            "fixes/Vol 7/images/245.jpg": fixes / "Vol 7/images/245.jpg",
        }

        found = background_sources(backgrounds, fixes)

        assert found == {
            "fixes/Vol 7/images/244.jpg": generated_files.file_hash(fixes / "Vol 7/images/244.jpg"),
            "fixes/Vol 7/images/245.jpg": generated_files.MISSING,
        }

    def test_a_machine_with_no_fixes_directory_checks_none(self, tmp_path: Path) -> None:
        backgrounds = {"fixes/Vol 7/images/244.jpg": tmp_path / "fixes/Vol 7/images/244.jpg"}

        found = background_sources(backgrounds, tmp_path / "fixes")

        assert found == {"fixes/Vol 7/images/244.jpg": generated_files.UNCHECKED}

    def test_the_how_to_s_are_among_its_sources_named_from_the_barks_root(self) -> None:
        by_name = {generated.name: generated for generated in GENERATED_SETS}

        found = by_name[generated_files.HOW_TO].sources(_dirs(generated_files.REPO_ROOT))

        assert "docs/how-to-use.md" in found
        backgrounds = [name for name in found if name.endswith("/images/244.jpg")]
        assert len(backgrounds) == 1
        assert backgrounds[0].startswith("Fantagraphics-fixes-and-additions/Carl Barks Vol. 7 ")


class TestFolderHash:
    def test_a_changed_added_or_renamed_file_changes_it(self, tmp_path: Path) -> None:
        root = write_tree(tmp_path / "Indexes", {"a.seg": b"aaaa", "sub/b.json": b"b"})
        hashes = {folder_hash(root)}

        (root / "a.seg").write_bytes(b"bbbb")
        hashes.add(folder_hash(root))
        (root / "c.json").write_bytes(b"c")
        hashes.add(folder_hash(root))
        (root / "c.json").rename(root / "d.json")
        hashes.add(folder_hash(root))

        assert len(hashes) == 4  # noqa: PLR2004

    def test_what_a_desktop_leaves_does_not_count(self, tmp_path: Path) -> None:
        root = write_tree(tmp_path / "Indexes", {"a.seg": b"a"})
        before = folder_hash(root)

        write_tree(root, {".DS_Store": b"x", "Thumbs.db": b"x", "._a.seg": b"x"})

        assert folder_hash(root) == before


class TestStaleReasons:
    def test_a_set_as_recorded_is_not_stale(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, guide)

        assert stale_reasons(load_record(record_path), dirs, guide) == []

    def test_a_set_never_recorded_is_said(
        self, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        (reason,) = stale_reasons({}, dirs, guide)

        assert reason.startswith(f"{GUIDE}: not in generated-files.json")
        assert f"--record {GUIDE}" in reason

    @pytest.mark.parametrize("edited", ["guide.md", "style.css", "shot.jpg", "fonts/script.ttf"])
    def test_an_edited_source_makes_it_stale_and_is_named(
        self,
        tmp_path: Path,
        source_dir: Path,
        dirs: ReaderDirs,
        guide: tuple[GeneratedSet, ...],
        edited: str,
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, guide)

        with (source_dir / edited).open("ab") as opened:
            opened.write(b" more")

        (reason,) = stale_reasons(load_record(record_path), dirs, guide)
        assert f"{GUIDE} is stale" in reason
        assert edited in reason
        assert "the generator" in reason

    def test_an_image_added_to_the_text_makes_it_stale(
        self, tmp_path: Path, source_dir: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, guide)
        (source_dir / "new.jpg").write_bytes(b"new")
        (source_dir / "guide.md").write_text(MD + '<img src="new.jpg">\n', encoding="utf-8")

        (reason,) = stale_reasons(load_record(record_path), dirs, guide)

        assert "new.jpg" in reason

    def test_files_that_are_not_the_ones_recorded_are_said(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, guide)
        (dirs.how_to / "page-2.jpg").write_bytes(b"another")
        (dirs.how_to / "page-3.jpg").write_bytes(b"three")

        (reason,) = stale_reasons(load_record(record_path), dirs, guide)

        assert "its files are not the ones recorded: page-2.jpg, page-3.jpg" in reason

    def test_many_changes_are_counted_past_the_first_few(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, guide)
        for number in range(3, 11):
            (dirs.how_to / f"page-{number}.jpg").write_bytes(b"x")

        (reason,) = stale_reasons(load_record(record_path), dirs, guide)

        assert reason.count("page-") == 5  # noqa: PLR2004
        assert "and 3 more" in reason


class TestSourcesThisMachineCannotSee:
    """A background is `UNCHECKED` where there is no fixes directory to look in."""

    @staticmethod
    def _guide(source_dir: Path, art: str) -> tuple[GeneratedSet, ...]:
        return (
            GeneratedSet(
                GUIDE,
                lambda _dirs: {
                    **document_sources(source_dir / "guide.md", source_dir / "style.css"),
                    "fixes/art.jpg": art,
                },
                lambda dirs: sorted(dirs.how_to.glob("page-*")),
                "the generator",
            ),
        )

    def test_one_is_left_out_of_the_comparison(
        self, tmp_path: Path, source_dir: Path, dirs: ReaderDirs
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, self._guide(source_dir, "a-hash"))
        elsewhere = self._guide(source_dir, generated_files.UNCHECKED)

        assert stale_reasons(load_record(record_path), dirs, elsewhere) == []

    def test_the_sources_it_can_see_are_still_compared(
        self, tmp_path: Path, source_dir: Path, dirs: ReaderDirs
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, self._guide(source_dir, "a-hash"))
        (source_dir / "guide.md").write_text("# Edited\n", encoding="utf-8")
        elsewhere = self._guide(source_dir, generated_files.UNCHECKED)

        (reason,) = stale_reasons(load_record(record_path), dirs, elsewhere)

        assert "changed since it was made: " in reason
        assert "guide.md" in reason
        assert "fixes/art.jpg" not in reason

    def test_a_changed_one_is_stale_where_it_can_be_seen(
        self, tmp_path: Path, source_dir: Path, dirs: ReaderDirs
    ) -> None:
        record_path = tmp_path / "record.json"
        record_sets([GUIDE], dirs, record_path, self._guide(source_dir, "a-hash"))

        (reason,) = stale_reasons(
            load_record(record_path), dirs, self._guide(source_dir, "another-hash")
        )

        assert reason.startswith(f"{GUIDE} is stale: changed since it was made: fixes/art.jpg")

    def test_such_a_machine_cannot_record_the_set(
        self, tmp_path: Path, source_dir: Path, dirs: ReaderDirs
    ) -> None:
        record_path = tmp_path / "record.json"
        elsewhere = self._guide(source_dir, generated_files.UNCHECKED)

        with pytest.raises(ValueError, match="lacks some of its sources"):
            record_sets([GUIDE], dirs, record_path, elsewhere)

        assert not record_path.exists()


class TestRecordSets:
    def test_recording_one_set_leaves_the_others_as_they_were(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"
        record_path.write_text(json.dumps({"other": {"sources": {}, "outputs": {}}}))

        assert record_sets([GUIDE], dirs, record_path, guide) == [GUIDE]

        record = load_record(record_path)
        assert set(record) == {GUIDE, "other"}
        assert set(record[GUIDE]["outputs"]) == {"page-1.jpg", "page-2.jpg"}

    def test_all_records_every_set(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        assert record_sets(["all"], dirs, tmp_path / "record.json", guide) == [GUIDE]

    def test_a_name_that_is_no_set_is_refused(
        self, tmp_path: Path, dirs: ReaderDirs, guide: tuple[GeneratedSet, ...]
    ) -> None:
        with pytest.raises(ValueError, match="No such generated set: nope"):
            record_sets(["nope"], dirs, tmp_path / "record.json", guide)

    def test_a_set_with_no_files_is_not_recorded(
        self, tmp_path: Path, guide: tuple[GeneratedSet, ...]
    ) -> None:
        record_path = tmp_path / "record.json"

        with pytest.raises(ValueError, match="no generated files found"):
            record_sets([GUIDE], _dirs(tmp_path / "empty"), record_path, guide)

        assert not record_path.exists()

    def test_no_record_file_records_nothing(self, tmp_path: Path) -> None:
        assert load_record(tmp_path / "gone.json") == {}


class TestTheSetsThereAre:
    def test_the_word_statistics_are_made_from_the_index_and_found_by_name(
        self, tmp_path: Path
    ) -> None:
        root = write_tree(
            tmp_path / "reader",
            {
                "Indexes/a.seg": b"a",
                "Statistics/most_frequent.png": b"1",
                "Statistics/tfidf_wordcloud_1943-46.png": b"2",
                "Statistics/tfidf_ranked_words_1943-46.txt": b"3",
                "Statistics/stories_per_year.png": b"a chart, checked elsewhere",
            },
        )
        words = next(s for s in GENERATED_SETS if s.name == generated_files.WORD_STATISTICS)

        found = generated_files.current(words, _dirs(root))

        assert found["sources"] == {INDEX_SOURCE: folder_hash(root / "Indexes")}
        assert set(found["outputs"]) == {
            "most_frequent.png",
            "tfidf_wordcloud_1943-46.png",
            "tfidf_ranked_words_1943-46.txt",
        }

    def test_an_index_that_is_not_there_is_a_missing_source(self, tmp_path: Path) -> None:
        words = next(s for s in GENERATED_SETS if s.name == generated_files.WORD_STATISTICS)

        assert words.sources(_dirs(tmp_path))[INDEX_SOURCE] == "missing"

    def test_the_documents_pages_are_their_folders_page_files(self, tmp_path: Path) -> None:
        root = write_tree(
            tmp_path / "reader",
            {"how-to/page-1.jpg": b"1", "how-to/notes.txt": b"x", "intro/page-1.jpg": b"1"},
        )
        by_name = {s.name: s for s in GENERATED_SETS}

        how_to = by_name[generated_files.HOW_TO].outputs(_dirs(root))
        intro = by_name[generated_files.INTRODUCTION].outputs(_dirs(root))

        assert [path.name for path in how_to] == ["page-1.jpg"]
        assert [path.parent.name for path in intro] == ["intro"]

    def test_the_icons_are_made_from_their_sources_and_found_where_the_app_reads_them(
        self, tmp_path: Path
    ) -> None:
        root = write_tree(
            tmp_path,
            {
                "Reader Icons/ActionBar Icons/icon-power.png": b"power",
                "Reader Icons/ActionBar Icons/icon-next-orig.png": b"not an icon the app reads",
                "Various/icon-eye-open.png": b"eye",
                "Various/empty-page.jpg": b"not an icon",
            },
        )
        by_name = {generated.name: generated for generated in GENERATED_SETS}
        icons = by_name[generated_files.ICONS]

        found = generated_files.current(icons, _dirs(root))

        assert set(found["outputs"]) == {"icon-power.png", "icon-eye-open.png"}
        assert "assets/reader-icon-sources/icon-power.svg" in found["sources"]
        assert generated_files.MISSING not in found["sources"].values()

    def test_the_reader_files_folder_is_the_one_the_icons_folder_is_in(
        self, tmp_path: Path
    ) -> None:
        class Paths:
            def get_how_to_doc_dir(self) -> Path:
                return tmp_path / "how-to"

            def get_intro_doc_dir(self) -> Path:
                return tmp_path / "intro"

            def get_statistics_dir(self) -> Path:
                return tmp_path / "Statistics"

            def get_barks_reader_indexes_dir(self) -> Path:
                return tmp_path / "Indexes"

            def get_reader_icon_files_dir(self) -> Path:
                return tmp_path / "Reader Files" / "Reader Icons"

        assert generated_files.dirs_from(Paths()).reader_files == tmp_path / "Reader Files"

    def test_every_set_committed_as_recorded_names_sources_that_exist(self) -> None:
        """A record made on one machine must be checkable on another: no absolute paths."""
        for name, entry in load_record().items():
            for source in entry["sources"]:
                assert not source.startswith("/"), f"{name}: {source}"


class TestMain:
    def test_list_names_the_sets(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert generated_files.main(["--list"]) == 0

        out = capsys.readouterr().out
        assert [line.split(":")[0] for line in out.splitlines()] == [s.name for s in GENERATED_SETS]

    def test_a_stale_set_is_printed_and_fails(
        self, dirs: ReaderDirs, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(generated_files, "reader_dirs", return_value=dirs),
            patch.object(generated_files, "load_record", return_value={}),
        ):
            assert generated_files.main([]) == 1

        assert "not in generated-files.json" in capsys.readouterr().out

    def test_nothing_stale_passes(
        self, dirs: ReaderDirs, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(generated_files, "reader_dirs", return_value=dirs),
            patch.object(generated_files, "stale_reasons", return_value=[]),
        ):
            assert generated_files.main([]) == 0

        assert "are as recorded" in capsys.readouterr().out

    def test_record_reports_a_bad_name_and_fails(
        self, dirs: ReaderDirs, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(generated_files, "reader_dirs", return_value=dirs):
            assert generated_files.main(["--record", "nope"]) == 1

        assert "No such generated set" in capsys.readouterr().err

    def test_record_writes_and_says_to_commit(
        self, tmp_path: Path, dirs: ReaderDirs, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(generated_files, "reader_dirs", return_value=dirs),
            patch.object(generated_files, "record_sets", return_value=["how-to"]) as record,
        ):
            assert generated_files.main(["--record", "how-to"]) == 0

        record.assert_called_once_with(["how-to"], dirs)
        assert "commit it" in capsys.readouterr().out
        assert not (tmp_path / "generated-files.json").exists()
