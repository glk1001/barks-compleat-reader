from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.json_settings_manager import SavableTreeViewNode, SettingsManager
from barks_reader.core.saved_page_info import SavedPageInfo

if TYPE_CHECKING:
    from pathlib import Path


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


class TestLastSelectedNode:
    def test_save_none_clears_the_selection(self, tmp_path: Path) -> None:
        store_path = tmp_path / "store.json"
        manager = SettingsManager(store_path)

        manager.save_last_selected_node_path(None)

        # An empty saved path reads back as 'no selection'.
        assert SettingsManager(store_path).get_last_selected_node_path() == (None, {})

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
