from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.json_settings_manager import (
    CORRUPT_SUFFIX,
    SavableTreeViewNode,
    SettingsManager,
)
from barks_reader.core.saved_page_info import SavedPageInfo


class _FakeTreeViewNode:
    """A minimal node satisfying `SavableTreeViewNode` structurally."""

    def __init__(self, name: str, level: int, parent: _FakeTreeViewNode | None = None) -> None:
        self._name = name
        self.level = level
        self.parent_node = parent
        self.nodes: list[_FakeTreeViewNode] = []
        self.is_open = False
        self.saved_state: dict[str, Any] = {}

    def get_name(self) -> str:
        return self._name


def _a_saved_page() -> SavedPageInfo:
    return SavedPageInfo(
        page_index=6, display_page_num="7", page_type=PageType.BODY, last_body_page="30"
    )


class TestEmptyStore:
    def test_missing_file_starts_empty(self, tmp_path: Path) -> None:
        manager = SettingsManager(tmp_path / "store.json")

        assert manager.get_last_selected_node_path() == (None, {})
        assert manager.get_last_read_page("Lost in the Andes!") is None

    def test_missing_file_is_not_created_until_a_save(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        SettingsManager(store_path)

        assert not store_path.exists()

    def test_empty_file_starts_empty(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        store_path.write_text("")

        manager = SettingsManager(store_path)

        assert manager.get_last_selected_node_path() == (None, {})


class TestCorruptStore:
    """A settings file that is not a JSON object once stopped the app booting."""

    @pytest.mark.parametrize(
        ("contents", "reason"),
        [
            pytest.param(
                '{"AAA_Settings": {"last_selected_node": ["Hi', "not valid JSON (", id="cut short"
            ),
            pytest.param("[1, 2, 3]", "a JSON list, not an object.", id="a list"),
            pytest.param('"text"', "a JSON str, not an object.", id="a string"),
        ],
    )
    def test_a_corrupt_file_is_moved_aside_and_settings_start_empty(
        self, tmp_path: Path, contents: str, reason: str, loguru_sink: list[str]
    ) -> None:
        store_path = tmp_path / "store.json"
        store_path.write_text(contents, encoding="utf-8")

        manager = SettingsManager(store_path)

        assert manager.get_last_selected_node_path() == (None, {})
        assert not store_path.exists()
        corrupt_path = tmp_path / f"store.json{CORRUPT_SUFFIX}"
        assert corrupt_path.read_text(encoding="utf-8") == contents
        assert any("starting with empty settings" in line for line in loguru_sink)
        # The log says what is wrong with the file, for whoever looks at the .corrupt copy.
        assert any(f'"{store_path}" is {reason}' in line for line in loguru_sink)

    def test_a_file_that_is_not_utf8_is_moved_aside(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        store_path.write_bytes(b"\xff\xfe{")

        SettingsManager(store_path)

        assert (tmp_path / f"store.json{CORRUPT_SUFFIX}").exists()

    def test_a_file_that_cannot_be_read_is_left_in_place(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        """A folder where the file should be: reading it fails, but it is not corrupt."""
        store_path = tmp_path / "store.json"
        store_path.mkdir()

        manager = SettingsManager(store_path)

        assert manager.get_last_selected_node_path() == (None, {})
        assert store_path.is_dir()
        assert not (tmp_path / f"store.json{CORRUPT_SUFFIX}").exists()
        assert any("could not be read" in line for line in loguru_sink)

    @pytest.mark.parametrize(
        "contents",
        [
            pytest.param({"AAA_Settings": []}, id="settings a list"),
            pytest.param({"AAA_Settings": "x", "Lost in the Andes!": "x"}, id="strings"),
            pytest.param({"Lost in the Andes!": [1]}, id="title a list"),
        ],
    )
    def test_a_section_that_is_not_an_object_counts_as_unset(
        self, tmp_path: Path, contents: dict[str, Any]
    ) -> None:
        """A hand-edited file: the top level is an object, a section in it is not."""
        store_path = tmp_path / "store.json"
        store_path.write_text(json.dumps(contents), encoding="utf-8")

        manager = SettingsManager(store_path)

        assert manager.get_last_selected_node_path() == (None, {})
        assert manager.get_last_read_page("Lost in the Andes!") is None

    def test_the_next_save_writes_a_good_file(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        store_path.write_text("{", encoding="utf-8")

        SettingsManager(store_path).save_last_read_page("Lost in the Andes!", _a_saved_page())

        assert SettingsManager(store_path).get_last_read_page("Lost in the Andes!") == (
            _a_saved_page()
        )


class TestAtomicSave:
    def test_a_save_leaves_no_temp_file(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"

        SettingsManager(store_path).save_last_read_page("Lost in the Andes!", _a_saved_page())

        assert [p.name for p in tmp_path.iterdir()] == ["store.json"]

    def test_a_write_that_fails_leaves_the_old_file_whole(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)
        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())
        before = store_path.read_text(encoding="utf-8")

        real_write_text = Path.write_text

        def write_half_then_fail(path: Path, data: str, *args: object, **kwargs: object) -> int:
            real_write_text(path, data[: len(data) // 2], *args, **kwargs)  # ty: ignore[invalid-argument-type]
            msg = "disk full"
            raise OSError(msg)

        monkeypatch.setattr(Path, Path.write_text.__name__, write_half_then_fail)
        manager.save_last_read_page("Trail of the Unicorn", _a_saved_page())

        assert store_path.read_text(encoding="utf-8") == before

    def test_a_save_that_fails_before_writing_anything_is_logged_too(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        """A full disk refuses the temp file itself: there is then none to clean up."""
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)

        def disk_full(_path: Path, *_args: object, **_kwargs: object) -> int:
            msg = "No space left on device"
            raise OSError(msg)

        monkeypatch.setattr(Path, Path.write_text.__name__, disk_full)
        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())
        monkeypatch.undo()

        assert list(tmp_path.iterdir()) == []
        assert any("Could not save the settings" in line for line in loguru_sink)

    def test_a_save_that_fails_is_logged_and_the_reading_goes_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        """A save comes with every page turn: one that fails must not stop the reader."""
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)
        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())

        def held_by_an_antivirus(_self: Path, _target: Path) -> Path:
            msg = "the file is in use"
            raise PermissionError(msg)

        monkeypatch.setattr(Path, Path.replace.__name__, held_by_an_antivirus)
        manager.save_last_read_page("Trail of the Unicorn", _a_saved_page())
        monkeypatch.undo()

        assert [p.name for p in tmp_path.iterdir()] == ["store.json"]
        assert any("Could not save the settings" in line for line in loguru_sink)
        # The settings in memory are whole, and the next save writes them.
        assert manager.get_last_read_page("Trail of the Unicorn") == _a_saved_page()
        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())
        assert SettingsManager(store_path).get_last_read_page("Trail of the Unicorn") == (
            _a_saved_page()
        )


class TestLastSelectedNode:
    def test_save_none_clears_the_selection(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)

        manager.save_last_selected_node_path(None)

        # An empty saved path reads back as 'no selection'.
        assert SettingsManager(store_path).get_last_selected_node_path() == (None, {})
        # On disk it is an empty list, not a null: the format has to stay loadable
        # by the kivy JsonStore layout this module replaced.
        assert json.loads(store_path.read_text(encoding="utf-8")) == {
            "AAA_Settings": {"last_selected_node": [], "last_selected_node_state": {}}
        }

    def test_node_path_and_state_round_trip_through_disk(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)

        root = _FakeTreeViewNode("ignored-for-root", level=0)
        stories = _FakeTreeViewNode("The Stories", level=1, parent=root)
        chrono = _FakeTreeViewNode("Chronological", level=2, parent=stories)
        chrono.saved_state["open"] = True

        manager.save_last_selected_node_path(cast("SavableTreeViewNode", chrono))

        path, state = SettingsManager(store_path).get_last_selected_node_path()
        assert path == ["Chronological", "The Stories", "root"]
        assert state == {"open": True}


class TestLastReadPage:
    def test_round_trips_through_disk(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)
        page = _a_saved_page()

        manager.save_last_read_page("Lost in the Andes!", page)

        reloaded = SettingsManager(store_path).get_last_read_page("Lost in the Andes!")
        assert reloaded == page

    def test_saving_again_replaces_the_entry(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)

        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())
        newer_page = SavedPageInfo(
            page_index=11, display_page_num="12", page_type=PageType.BODY, last_body_page="30"
        )
        manager.save_last_read_page("Lost in the Andes!", newer_page)

        reloaded = SettingsManager(store_path).get_last_read_page("Lost in the Andes!")
        assert reloaded == newer_page

    def test_titles_are_independent(self, tmp_path: Path) -> None:
        manager = SettingsManager(tmp_path / "store.json")

        manager.save_last_read_page("Lost in the Andes!", _a_saved_page())

        assert manager.get_last_read_page("Some Other Title") is None


class TestJsonStoreFormatCompatibility:
    def test_loads_a_file_written_by_kivy_jsonstore(self, tmp_path: Path) -> None:
        """User settings files written by the old kivy JsonStore must load unchanged."""
        store_path = tmp_path / "store.json"
        store_path.write_text(
            json.dumps(
                {
                    "AAA_Settings": {
                        "last_selected_node": ["Chronological", "The Stories", "root"],
                        "last_selected_node_state": {"open": True},
                    },
                    "Lost in the Andes!": {"last_read_page": _a_saved_page().to_json()},
                },
                indent=4,
            )
        )

        manager = SettingsManager(store_path)

        path, state = manager.get_last_selected_node_path()
        assert path == ["Chronological", "The Stories", "root"]
        assert state == {"open": True}
        assert manager.get_last_read_page("Lost in the Andes!") == _a_saved_page()

    def test_writes_an_indented_json_object(self, tmp_path: Path) -> None:
        """Preserve the JsonStore on-disk shape (top-level object, indent=4)."""
        store_path = tmp_path / "store.json"
        SettingsManager(store_path).save_last_read_page("Lost in the Andes!", _a_saved_page())

        contents = store_path.read_text()
        assert contents.startswith('{\n    "')
        assert json.loads(contents) == {
            "Lost in the Andes!": {"last_read_page": _a_saved_page().to_json()}
        }

    def test_missing_state_key_defaults_to_empty(self, tmp_path: Path) -> None:
        """Older stores may lack last_selected_node_state."""
        store_path = tmp_path / "store.json"
        store_path.write_text(json.dumps({"AAA_Settings": {"last_selected_node": ["A", "root"]}}))

        path, state = SettingsManager(store_path).get_last_selected_node_path()

        assert path == ["A", "root"]
        assert state == {}


class TestLegacyHistoryNodePathMigration:
    def test_legacy_reading_history_path_migrates(self, tmp_path: Path) -> None:
        """The old top-level 'Reading History' node is now 'History' under 'Reading'."""
        store_path = tmp_path / "store.json"
        store_path.write_text(
            json.dumps({"AAA_Settings": {"last_selected_node": ["Reading History", "root"]}})
        )

        path, _state = SettingsManager(store_path).get_last_selected_node_path()

        assert path == ["History", "Reading", "root"]

    def test_other_paths_pass_through_unchanged(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        store_path.write_text(
            json.dumps(
                {"AAA_Settings": {"last_selected_node": ["Chronological", "The Stories", "root"]}}
            )
        )

        path, _state = SettingsManager(store_path).get_last_selected_node_path()

        assert path == ["Chronological", "The Stories", "root"]


class TestReadCueOpensLeft:
    LEFT = 3

    def test_none_are_left_until_a_count_is_saved(self, tmp_path: Path) -> None:
        assert SettingsManager(tmp_path / "store.json").get_read_cue_opens_left() == 0

    def test_a_saved_count_is_remembered_across_restarts(self, tmp_path: Path) -> None:
        store = tmp_path / "store.json"
        SettingsManager(store).save_read_cue_opens_left(self.LEFT)

        assert SettingsManager(store).get_read_cue_opens_left() == self.LEFT

    def test_a_count_below_nothing_is_saved_as_none(self, tmp_path: Path) -> None:
        store = tmp_path / "store.json"
        SettingsManager(store).save_read_cue_opens_left(-1)

        assert SettingsManager(store).get_read_cue_opens_left() == 0

    def test_saving_the_selected_node_keeps_the_count(self, tmp_path: Path) -> None:
        """The reader settings are rewritten whole: the count is kept apart from them."""
        store = tmp_path / "store.json"
        manager = SettingsManager(store)
        manager.save_read_cue_opens_left(self.LEFT)
        manager.save_last_selected_node_path(None)

        assert SettingsManager(store).get_read_cue_opens_left() == self.LEFT

    @pytest.mark.parametrize("held", [3, [3], {"opens_left": "3"}, {"opens_left": True}])
    def test_a_count_of_another_shape_counts_as_none(self, tmp_path: Path, held: object) -> None:
        """A hand-edited file may hold anything here: none are left, and saving mends it."""
        store = tmp_path / "store.json"
        store.write_text(json.dumps({"AAA_Read_Cue": held}))
        manager = SettingsManager(store)
        assert manager.get_read_cue_opens_left() == 0

        manager.save_read_cue_opens_left(1)

        assert SettingsManager(store).get_read_cue_opens_left() == 1


class TestScreenSizesWarned:
    def test_a_warned_screen_size_is_remembered_across_restarts(self, tmp_path: Path) -> None:
        store = tmp_path / "store.json"
        manager = SettingsManager(store)
        assert not manager.is_screen_size_warned("1366x768")

        manager.save_screen_size_warned("1366x768")

        reopened = SettingsManager(store)
        assert reopened.is_screen_size_warned("1366x768")
        assert not reopened.is_screen_size_warned("1600x900")

    def test_a_second_warned_size_keeps_the_first(self, tmp_path: Path) -> None:
        store = tmp_path / "store.json"
        manager = SettingsManager(store)
        manager.save_screen_size_warned("1366x768")
        manager.save_screen_size_warned("1600x900")

        reopened = SettingsManager(store)
        assert reopened.is_screen_size_warned("1366x768")
        assert reopened.is_screen_size_warned("1600x900")

    def test_warned_sizes_of_another_shape_count_as_none(self, tmp_path: Path) -> None:
        """A hand-edited file may hold a list here: nothing is warned, and saving mends it."""
        store = tmp_path / "store.json"
        store.write_text(json.dumps({"AAA_Screen_Sizes_Warned": ["1366x768"]}))
        manager = SettingsManager(store)
        assert not manager.is_screen_size_warned("1366x768")

        manager.save_screen_size_warned("1366x768")

        assert SettingsManager(store).is_screen_size_warned("1366x768")

    def test_saving_the_selected_node_keeps_the_warned_sizes(self, tmp_path: Path) -> None:
        """The reader settings are rewritten whole; the warned sizes are kept apart."""
        manager = SettingsManager(tmp_path / "store.json")
        manager.save_screen_size_warned("1366x768")
        manager.save_last_selected_node_path(cast("SavableTreeViewNode", _FakeTreeViewNode("A", 0)))
        assert SettingsManager(tmp_path / "store.json").is_screen_size_warned("1366x768")
