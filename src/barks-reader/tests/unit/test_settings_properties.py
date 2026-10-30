"""The settings saved then loaded, for any values: the reader's ini and the JSON store.

The last item of docs/BACKLOG.md's property-testing section. Two halves:

* ``ReaderSettings`` over a real ``configparser``: a value of every field's kind,
  written as the settings panel writes it, reads back typed, the same through the
  ini file on disk, and the same as ``setting_value_from_panel`` types the panel's
  text; the three setters read back what they were set.
* ``SettingsManager`` as a state machine over its JSON file: last-read pages saved
  per title, the selected node with its state, the screen sizes warned about; after
  every step a manager loaded from the file answers as the live one does.

Module-level ``@given`` functions and a machine run from a module-level function,
for mutmut's repeated pytest runs (docs/mutation-testing.md).
"""

from __future__ import annotations

import json
import string
import tempfile
from configparser import RawConfigParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.json_settings_manager import SavableTreeViewNode, SettingsManager
from barks_reader.core.reader_settings import (
    _FIELDS,
    ALT_ESCAPE_KEY_UNSET,
    BARKS_READER_SECTION,
    FieldKind,
    FieldSpec,
    ReaderSettings,
    read_setting_from_config,
    setting_value_from_panel,
)
from barks_reader.core.reader_utils import expand_path_vars
from barks_reader.core.saved_page_info import SavedPageInfo
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

if TYPE_CHECKING:
    from collections.abc import Iterator

# --- the reader's ini ----------------------------------------------------------------


class _IniConfig(RawConfigParser):
    """A config as Kivy's: a value set is stored as text, and the settings reader's port.

    ``RawConfigParser`` keeps whatever object ``set`` is given and ``getboolean`` then
    fails on an int; Kivy's ``ConfigParser.set`` converts to text first, which the
    reader's setters rely on when they set ``1`` or ``0``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.add_section(BARKS_READER_SECTION)

    def set(self, section: Any, option: str, value: Any = None) -> None:  # noqa: ANN401
        super().set(section, option, str(value))

    def write(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        """Nothing: the reader's `_save_settings` is the caller's, and the tests write by hand."""


def _reloaded(config: _IniConfig) -> _IniConfig:
    """Write the config to an ini file and read it back fresh: the save then load."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "barks-reader.ini"
        with path.open("w", encoding="utf-8") as ini:
            RawConfigParser.write(config, ini)
        loaded = _IniConfig()
        loaded.read(path, encoding="utf-8")
    return loaded


# A value as the panel's text would carry it, with the value reading it gives.
_BOOL_TEXTS = st.sampled_from(["0", "1", "True", "False", "yes", "no", "on", "off"])
_PLAIN_PATH_TEXTS = (
    st.text(alphabet=string.ascii_letters + string.digits + "/._- ", min_size=1, max_size=40)
    .map(str.strip)
    .filter(bool)
)
# Some under ${HOME} or $HOME, as the shipped defaults are: expanded by the fields that
# expand variables, and kept as written by the fields that do not.
_PATH_TEXTS = _PLAIN_PATH_TEXTS | st.builds(
    lambda var, rest: f"{var}/{rest}", st.sampled_from(["${HOME}", "$HOME"]), _PLAIN_PATH_TEXTS
)


@st.composite
def panel_texts(draw: st.DrawFn, spec: FieldSpec) -> tuple[str, Any]:
    """Draw what the panel writes for `spec` and the typed value reading it back gives."""
    match spec.kind:
        case FieldKind.BOOL:
            text = draw(_BOOL_TEXTS)
            return text, RawConfigParser.BOOLEAN_STATES[text.lower()]
        case FieldKind.INT:
            value = draw(st.integers(min_value=-1_000_000, max_value=1_000_000))
            return str(value), value
        case FieldKind.ALT_ESCAPE:
            text = draw(st.integers(min_value=0, max_value=1_000_000).map(str) | st.just("x"))
            return text, (int(text) if text.isdigit() else ALT_ESCAPE_KEY_UNSET)
        case FieldKind.OPTIONS:
            assert spec.options is not None
            text = draw(st.sampled_from(spec.options))
            return text, text
        case FieldKind.LONG_PATH:
            text = draw(_PATH_TEXTS)
            return text, Path(expand_path_vars(text) if spec.expand_vars else text)
    msg = f"unknown field kind {spec.kind}"
    raise AssertionError(msg)


@st.composite
def panel_writes(draw: st.DrawFn) -> dict[str, tuple[str, Any]]:
    """Draw a text and typed value for every field, as a settings panel session writes them."""
    return {spec.key: draw(panel_texts(spec)) for spec in _FIELDS}


@given(panel_writes())
def test_every_setting_the_panel_writes_reads_back_typed_the_same_from_the_ini_file(
    writes: dict[str, tuple[str, Any]],
) -> None:
    config = _IniConfig()
    for key, (text, _value) in writes.items():
        config.set(BARKS_READER_SECTION, key, text)
    reloaded = _reloaded(config)
    for key, (text, value) in writes.items():
        assert read_setting_from_config(config, key) == value
        assert read_setting_from_config(reloaded, key) == value
        assert setting_value_from_panel(key, text) == value
        assert setting_value_from_panel(key, value) == value


@given(st.booleans(), st.integers(min_value=0, max_value=1_000_000))
def test_the_setters_read_back_what_they_were_set_here_and_after_a_reload(
    first_use: bool, keycode: int
) -> None:
    config = _IniConfig()
    for spec in _FIELDS:  # Every field present, as the panel leaves the file.
        default = spec.config_default() if callable(spec.config_default) else spec.config_default
        config.set(BARKS_READER_SECTION, spec.key, default)
    reader_settings = ReaderSettings()
    reader_settings.set_config(config, Path("/app/barks-reader.ini"), Path("/app"))

    reader_settings.is_first_use_of_reader = first_use
    reader_settings.set_alt_escape_key(keycode)

    for cfg in (config, _reloaded(config)):
        loaded = ReaderSettings()
        loaded.set_config(cfg, Path("/app/barks-reader.ini"), Path("/app"))
        assert loaded.is_first_use_of_reader is first_use
        assert loaded.get_alt_escape_key() == keycode


# --- the JSON store ---------------------------------------------------------------------


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


# The store's own sections sit beside the titles; a title named like one would collide.
_TITLES = st.text(min_size=1, max_size=30).filter(lambda t: not t.startswith("AAA_"))
_NAMES = st.text(min_size=1, max_size=20)
_STATES = st.dictionaries(
    st.text(max_size=10), st.booleans() | st.integers() | st.text(max_size=10), max_size=3
)
_PAGES = st.builds(
    SavedPageInfo,
    page_index=st.integers(min_value=0, max_value=200),
    display_page_num=st.text(min_size=1, max_size=4),
    page_type=st.sampled_from(list(PageType)),
    last_body_page=st.text(min_size=1, max_size=4),
)
_SIZE_KEY_NAMES = ["1024x768", "1280x720", "800x600", "1366x768"]
_SIZE_KEYS = st.sampled_from(_SIZE_KEY_NAMES)

# The one path the store rewrites on the way back out (the History node moved).
_LEGACY_HISTORY_PATH = ["Reading History", "root"]
_NEW_HISTORY_PATH = ["History", "Reading", "root"]


class SettingsStoreMachine(RuleBasedStateMachine):
    """A settings store on disk, beside a model of what it should give back."""

    def __init__(self) -> None:
        super().__init__()
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "barks-reader.json"
        self.store = SettingsManager(self.path)
        self.pages: dict[str, SavedPageInfo] = {}
        self.node: tuple[list[str], dict[str, Any]] | None = None
        self.warned: set[str] = set()

    def teardown(self) -> None:
        self._dir.cleanup()

    def _managers(self) -> Iterator[SettingsManager]:
        """Yield the live store and one loaded from its file: both must answer the same."""
        yield self.store
        yield SettingsManager(self.path)

    # --- rules ---

    @rule(title=_TITLES, page=_PAGES)
    def save_a_last_read_page(self, title: str, page: SavedPageInfo) -> None:
        self.store.save_last_read_page(title, page)
        self.pages[title] = page

    @rule(names=st.lists(_NAMES, min_size=1, max_size=4), state=_STATES)
    def save_the_selected_node(self, names: list[str], state: dict[str, Any]) -> None:
        root = _FakeTreeViewNode("root-name-is-ignored", level=0)
        node = root
        for level, name in enumerate(names, start=1):
            node = _FakeTreeViewNode(name, level, parent=node)
        node.saved_state = dict(state)
        self.store.save_last_selected_node_path(cast("SavableTreeViewNode", node))
        path = [*reversed(names), "root"]
        self.node = (_NEW_HISTORY_PATH if path == _LEGACY_HISTORY_PATH else path, dict(state))

    @rule()
    def clear_the_selected_node(self) -> None:
        self.store.save_last_selected_node_path(None)
        self.node = None

    @rule(size_key=_SIZE_KEYS)
    def warn_about_a_screen_size(self, size_key: str) -> None:
        self.store.save_screen_size_warned(size_key)
        self.warned.add(size_key)

    # --- invariants ---

    @invariant()
    def every_title_s_page_reads_back_live_and_from_the_file(self) -> None:
        for manager in self._managers():
            for title, page in self.pages.items():
                assert manager.get_last_read_page(title) == page
            assert manager.get_last_read_page("no such title") is None

    @invariant()
    def the_selected_node_reads_back_live_and_from_the_file(self) -> None:
        for manager in self._managers():
            path, state = manager.get_last_selected_node_path()
            if self.node is None:
                assert path is None
                assert state == {}
            else:
                assert (path, state) == self.node

    @invariant()
    def the_sizes_warned_about_stay_warned_live_and_from_the_file(self) -> None:
        for manager in self._managers():
            for size_key in _SIZE_KEY_NAMES:
                assert manager.is_screen_size_warned(size_key) == (size_key in self.warned)

    @invariant()
    def the_file_is_one_json_object_or_not_yet_written(self) -> None:
        if self.path.exists():
            assert isinstance(json.loads(self.path.read_text(encoding="utf-8")), dict)
        else:
            assert not self.pages
            assert self.node is None
            assert not self.warned


def test_the_settings_store_gives_back_what_was_saved_under_any_sequence_of_saves() -> None:
    run_state_machine_as_test(
        SettingsStoreMachine, settings=settings(stateful_step_count=25, deadline=None)
    )
