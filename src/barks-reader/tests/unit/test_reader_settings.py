# ruff: noqa: SLF001

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import reader_settings as reader_settings_module
from barks_reader.core.reader_file_paths import BarksPanelsExtType, ReaderFilePaths
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    FANTA_DIR,
    UNSET_WIKI_BUNDLE_DIR_MARKER,
    ReaderSettings,
)
from barks_reader.core.system_file_paths import SystemFilePaths


@pytest.fixture
def mock_config() -> MagicMock:
    """Mock the ConfigParser."""
    config = MagicMock()
    config.get.return_value = "/mock/path"
    config.getboolean.return_value = False
    config.getint.return_value = 0
    return config


@pytest.fixture
def mock_reader_file_paths() -> MagicMock:
    """Mock ReaderFilePaths."""
    return MagicMock(spec=ReaderFilePaths)


@pytest.fixture
def mock_sys_file_paths() -> MagicMock:
    """Mock SystemFilePaths."""
    return MagicMock(spec=SystemFilePaths)


@pytest.fixture
def reader_settings(
    mock_config: MagicMock,
    mock_reader_file_paths: MagicMock,
    mock_sys_file_paths: MagicMock,
) -> ReaderSettings:
    """Create a ReaderSettings instance with mocked dependencies."""
    with (
        patch.object(
            reader_settings_module,
            ReaderFilePaths.__name__,
            return_value=mock_reader_file_paths,
        ),
        patch.object(
            reader_settings_module,
            SystemFilePaths.__name__,
            return_value=mock_sys_file_paths,
        ),
    ):
        settings = ReaderSettings()
        app_settings_path = Path("/app/settings.ini")
        app_data_dir = Path("/app/data")
        settings.set_config(mock_config, app_settings_path, app_data_dir)
        return settings


class TestReaderSettings:
    def test_init(self) -> None:
        """Test initialization of ReaderSettings."""
        with (
            patch.object(reader_settings_module, ReaderFilePaths.__name__) as mock_rfp,
            patch.object(reader_settings_module, SystemFilePaths.__name__) as mock_sfp,
        ):
            settings = ReaderSettings()
            assert settings._reader_file_paths == mock_rfp.return_value
            assert settings._reader_sys_file_paths == mock_sfp.return_value

    def test_set_config(self, reader_settings: ReaderSettings, mock_config: MagicMock) -> None:
        """Test setting the configuration."""
        assert reader_settings._config == mock_config
        assert reader_settings.get_app_settings_path() == Path("/app/settings.ini")
        assert reader_settings.get_user_data_path() == Path("/app/barks-reader.json")

    def test_get_fantagraphics_volumes_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test retrieving the Fantagraphics volumes directory."""
        mock_config.get.return_value = "/fanta/volumes"
        path = reader_settings.fantagraphics_volumes_dir

        mock_config.get.assert_called_with(BARKS_READER_SECTION, FANTA_DIR)
        assert path == Path("/fanta/volumes")

    def test_force_barks_panels_dir_png(
        self,
        reader_settings: ReaderSettings,
        mock_config: MagicMock,
        mock_reader_file_paths: MagicMock,
    ) -> None:
        """Test forcing Barks panels directory to PNG."""
        mock_config.get.return_value = "$VAR/panels"

        # Patch os.path.expandvars in the module
        with patch.object(
            reader_settings_module.os.path,
            os.path.expandvars.__name__,
            return_value="/expanded/panels",
        ) as mock_expand:
            reader_settings.force_barks_panels_dir(use_png_images=True)

            mock_expand.assert_called_with("$VAR/panels")
            mock_reader_file_paths.set_barks_panels_source.assert_called_with(
                Path("/expanded/panels"), BarksPanelsExtType.MOSTLY_PNG
            )

    def test_force_barks_panels_dir_jpg(
        self, reader_settings: ReaderSettings, mock_reader_file_paths: MagicMock
    ) -> None:
        """Test forcing Barks panels directory to JPG."""
        expected_path = Path("/app/data/Reader Files/Barks Panels.zip")

        reader_settings.force_barks_panels_dir(use_png_images=False)

        mock_reader_file_paths.set_barks_panels_source.assert_called_with(
            expected_path, BarksPanelsExtType.JPG
        )

    def test_is_first_use_of_reader_setter(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test setting the 'is_first_use_of_reader' property."""
        with patch.object(reader_settings, ReaderSettings._save_settings.__name__) as mock_save:
            reader_settings.is_first_use_of_reader = False
            mock_config.set.assert_called_with(BARKS_READER_SECTION, "is_first_use_of_reader", 0)
            mock_save.assert_called_once()

            mock_save.reset_mock()
            reader_settings.is_first_use_of_reader = True
            mock_config.set.assert_called_with(BARKS_READER_SECTION, "is_first_use_of_reader", 1)
            mock_save.assert_called_once()

    def test_is_valid_fantagraphics_volumes_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of Fantagraphics volumes directory."""
        # Case 1: use_prebuilt_archives is True
        mock_config.getboolean.side_effect = lambda _section, key: key == "use_prebuilt_comics"
        assert reader_settings.is_valid_fantagraphics_volumes_dir(Path("/any/path")) is True

        # Case 2: use_prebuilt_archives is False, dir exists
        mock_config.getboolean.side_effect = None
        mock_config.getboolean.return_value = False
        with patch.object(Path, Path.is_dir.__name__, return_value=True):
            assert reader_settings.is_valid_fantagraphics_volumes_dir(Path("/valid/path")) is True

        # Case 3: use_prebuilt_archives is False, dir does not exist
        with patch.object(Path, Path.is_dir.__name__, return_value=False):
            assert (
                reader_settings.is_valid_fantagraphics_volumes_dir(Path("/invalid/path")) is False
            )

    def test_is_valid_use_png_images(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of PNG images setting."""
        # Case 1: use_png_images = True
        mock_config.getboolean.return_value = True
        mock_config.get.return_value = "/png/dir"
        with (
            patch.object(
                reader_settings_module.os.path, os.path.expandvars.__name__, return_value="/png/dir"
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=True),
        ):
            assert reader_settings._is_valid_use_png_images(use_png_images=True) is True

        with (
            patch.object(
                reader_settings_module.os.path, os.path.expandvars.__name__, return_value="/png/dir"
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=False),
        ):
            assert reader_settings._is_valid_use_png_images(use_png_images=True) is False

        # Case 2: use_png_images = False
        mock_config.getboolean.return_value = False
        with patch.object(Path, Path.is_file.__name__, return_value=True):
            assert reader_settings._is_valid_use_png_images(use_png_images=False) is True

        with patch.object(Path, Path.is_file.__name__, return_value=False):
            assert reader_settings._is_valid_use_png_images(use_png_images=False) is False

    def test_wiki_bundle_dir_bundled(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test wiki_bundle_dir with use_live_wiki_bundle off (bundled copy)."""
        mock_config.getboolean.return_value = False
        expected_path = Path("/app/data/Reader Files/Carl Barks Wiki")

        # Bundled dir is a valid bundle (root index.md exists).
        with patch.object(Path, Path.is_file.__name__, return_value=True):
            assert reader_settings.wiki_bundle_dir == expected_path

        # Bundled dir is missing or not a bundle: wiki is hidden.
        with patch.object(Path, Path.is_file.__name__, return_value=False):
            assert reader_settings.wiki_bundle_dir is None

    def test_wiki_bundle_dir_live(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test wiki_bundle_dir with use_live_wiki_bundle on (wiki_bundle_dir setting)."""
        mock_config.getboolean.return_value = True

        # Setting points at a valid bundle.
        mock_config.get.return_value = "/wiki/bundle"
        with (
            patch.object(
                reader_settings_module.os.path,
                os.path.expandvars.__name__,
                return_value="/wiki/bundle",
            ),
            patch.object(Path, Path.is_file.__name__, return_value=True),
        ):
            assert reader_settings.wiki_bundle_dir == Path("/wiki/bundle")

        # Setting points at a non-bundle directory (no root index.md).
        with (
            patch.object(
                reader_settings_module.os.path,
                os.path.expandvars.__name__,
                return_value="/wiki/bundle",
            ),
            patch.object(Path, Path.is_file.__name__, return_value=False),
        ):
            assert reader_settings.wiki_bundle_dir is None

        # Setting is the unset marker.
        mock_config.get.return_value = UNSET_WIKI_BUNDLE_DIR_MARKER
        with patch.object(
            reader_settings_module.os.path,
            os.path.expandvars.__name__,
            return_value=UNSET_WIKI_BUNDLE_DIR_MARKER,
        ):
            assert reader_settings.wiki_bundle_dir is None

    def test_is_valid_wiki_bundle_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of the wiki bundle directory setting."""
        # Case 1: use_live_wiki_bundle = False - the setting is not in use.
        mock_config.getboolean.return_value = False
        assert reader_settings._is_valid_wiki_bundle_dir(Path("/any/path")) is True

        # Case 2: use_live_wiki_bundle = True - unset marker is valid.
        mock_config.getboolean.return_value = True
        assert reader_settings._is_valid_wiki_bundle_dir(Path(UNSET_WIKI_BUNDLE_DIR_MARKER)) is True

        # Case 3: use_live_wiki_bundle = True - a set path must be a bundle.
        with (
            patch.object(Path, Path.is_dir.__name__, return_value=True),
            patch.object(Path, Path.is_file.__name__, return_value=True),
        ):
            assert reader_settings._is_valid_wiki_bundle_dir(Path("/wiki/bundle")) is True

        with (
            patch.object(Path, Path.is_dir.__name__, return_value=True),
            patch.object(Path, Path.is_file.__name__, return_value=False),
        ):
            assert reader_settings._is_valid_wiki_bundle_dir(Path("/wiki/bundle")) is False

        with patch.object(Path, Path.is_dir.__name__, return_value=False):
            assert reader_settings._is_valid_wiki_bundle_dir(Path("/wiki/bundle")) is False

    def test_is_valid_use_live_wiki_bundle(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of the use_live_wiki_bundle setting."""
        # Case 1: turning it off is always valid (bundled copy is optional).
        assert reader_settings._is_valid_use_live_wiki_bundle(use_live_wiki_bundle=False) is True

        # Case 2: turning it on requires a valid (or unset) wiki_bundle_dir.
        mock_config.getboolean.return_value = True
        mock_config.get.return_value = "/wiki/bundle"
        with (
            patch.object(
                reader_settings_module.os.path,
                os.path.expandvars.__name__,
                return_value="/wiki/bundle",
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=True),
            patch.object(Path, Path.is_file.__name__, return_value=True),
        ):
            assert reader_settings._is_valid_use_live_wiki_bundle(use_live_wiki_bundle=True) is True

        with (
            patch.object(
                reader_settings_module.os.path,
                os.path.expandvars.__name__,
                return_value="/wiki/bundle",
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=False),
        ):
            assert (
                reader_settings._is_valid_use_live_wiki_bundle(use_live_wiki_bundle=True) is False
            )

        mock_config.get.return_value = UNSET_WIKI_BUNDLE_DIR_MARKER
        with patch.object(
            reader_settings_module.os.path,
            os.path.expandvars.__name__,
            return_value=UNSET_WIKI_BUNDLE_DIR_MARKER,
        ):
            assert reader_settings._is_valid_use_live_wiki_bundle(use_live_wiki_bundle=True) is True

    def test_properties(self, reader_settings: ReaderSettings, mock_config: MagicMock) -> None:
        """Test various simple property getters."""
        mock_config.getboolean.return_value = True
        assert reader_settings.goto_saved_node_on_start is True

        mock_config.getint.return_value = 100
        assert reader_settings._read(reader_settings_module.MAIN_WINDOW_HEIGHT) == 100  # noqa: PLR2004

        mock_config.get.return_value = "INFO"
        assert reader_settings.log_level == "INFO"


class TestSettingsPanelSchema:
    """`_get_reader_settings_json` builds the Kivy settings-panel schema.

    Kivy reads these dicts by exact key name, so a renamed or dropped key produces a
    panel that silently loses a control rather than an error. The whole schema is
    therefore checked against the `_FIELDS` table it is derived from.
    """

    @pytest.fixture
    def schema(self) -> list[dict[str, object]]:
        return json.loads(reader_settings_module._get_reader_settings_json())

    def test_entries_appear_in_field_order_with_their_section_titles(
        self, schema: list[dict[str, object]]
    ) -> None:
        """A spec with a `section_header` emits a title separator *before* its entry."""
        expected: list[tuple[str, str]] = []
        for spec in reader_settings_module._FIELDS:
            if spec.section_header:
                expected.append(("title", spec.section_header))
            expected.append((spec.kind.value, spec.key))

        actual = [
            (item["type"], item["title"] if item["type"] == "title" else item["key"])
            for item in schema
        ]
        assert actual == expected

    def test_every_setting_entry_carries_the_full_kivy_contract(
        self, schema: list[dict[str, object]]
    ) -> None:
        by_key = {item["key"]: item for item in schema if item["type"] != "title"}

        assert set(by_key) == {spec.key for spec in reader_settings_module._FIELDS}
        for spec in reader_settings_module._FIELDS:
            entry = by_key[spec.key]
            assert entry["title"] == spec.title
            assert entry["desc"] == spec.desc
            assert entry["type"] == spec.kind.value
            assert entry["section"] == BARKS_READER_SECTION

    def test_option_lists_are_emitted_only_where_the_spec_has_them(
        self, schema: list[dict[str, object]]
    ) -> None:
        by_key = {item["key"]: item for item in schema if item["type"] != "title"}

        for spec in reader_settings_module._FIELDS:
            entry = by_key[spec.key]
            if spec.options is None:
                assert "options" not in entry
            else:
                assert entry["options"] == list(spec.options)

    def test_options_fields_carry_their_default_value(
        self, schema: list[dict[str, object]]
    ) -> None:
        """Only `OPTIONS` entries get a `value`; Kivy uses it as the panel's default."""
        by_key = {item["key"]: item for item in schema if item["type"] != "title"}
        seen_options_field = False

        for spec in reader_settings_module._FIELDS:
            entry = by_key[spec.key]
            if spec.kind is reader_settings_module.FieldKind.OPTIONS:
                seen_options_field = True
                assert entry["value"] == spec.config_default
            else:
                assert "value" not in entry

        assert seen_options_field, "no OPTIONS field in _FIELDS — the branch went untested"

    def test_a_known_entry_in_full(self, schema: list[dict[str, object]]) -> None:
        """One entry compared whole, to pin the exact key spelling Kivy expects."""
        fanta = next(item for item in schema if item.get("key") == FANTA_DIR)
        spec = reader_settings_module._FIELDS_BY_KEY[FANTA_DIR]

        assert fanta == {
            "title": spec.title,
            "desc": spec.desc,
            "type": spec.kind.value,
            "section": BARKS_READER_SECTION,
            "key": FANTA_DIR,
        }


class TestReadSettingFromConfig:
    """Every field kind reads through the right `ConfigParser` accessor and section."""

    @staticmethod
    def _key_of(kind: reader_settings_module.FieldKind) -> str | None:
        return next(
            (spec.key for spec in reader_settings_module._FIELDS if spec.kind is kind), None
        )

    @pytest.mark.parametrize(
        ("kind", "accessor"),
        [
            pytest.param(reader_settings_module.FieldKind.BOOL, "getboolean", id="bool"),
            pytest.param(reader_settings_module.FieldKind.INT, "getint", id="int"),
            pytest.param(reader_settings_module.FieldKind.LONG_PATH, "get", id="long_path"),
        ],
    )
    def test_the_section_and_key_reach_the_accessor(
        self, kind: reader_settings_module.FieldKind, accessor: str
    ) -> None:
        key = self._key_of(kind)
        assert key is not None, f"no {kind} field in _FIELDS"

        config = MagicMock()
        config.get.return_value = "/some/path"
        reader_settings_module.read_setting_from_config(config, key)

        getattr(config, accessor).assert_called_once_with(BARKS_READER_SECTION, key)

    def test_an_unparseable_alt_escape_key_falls_back_to_unset(self) -> None:
        key = self._key_of(reader_settings_module.FieldKind.ALT_ESCAPE)
        assert key is not None, "no ALT_ESCAPE field in _FIELDS"

        config = MagicMock()
        config.getint.side_effect = ValueError("not a number")

        assert (
            reader_settings_module.read_setting_from_config(config, key)
            == reader_settings_module.ALT_ESCAPE_KEY_UNSET
        )
        config.getint.assert_called_once_with(BARKS_READER_SECTION, key)


class TestDerivedUserPaths:
    def test_the_user_data_and_history_files_sit_beside_the_settings_file(
        self, reader_settings: ReaderSettings
    ) -> None:
        """Both live in the app config dir under their exact, lowercase names."""
        assert reader_settings.get_user_data_path() == Path("/app/barks-reader.json")
        assert reader_settings.get_user_history_path() == Path("/app/barks-reader-history.json")


class TestWikiBundleIndexGate:
    def test_a_directory_without_a_lowercase_index_md_is_not_a_bundle(
        self, reader_settings: ReaderSettings, mock_config: MagicMock, tmp_path: Path
    ) -> None:
        """The bundle is detected by its root `index.md` — the name is case-sensitive."""
        mock_config.getboolean.return_value = True
        bundle = tmp_path / "wiki"
        bundle.mkdir()
        (bundle / "INDEX.MD").write_text("not the right name")

        assert reader_settings._is_valid_wiki_bundle_dir(bundle) is False

        (bundle / "index.md").write_text("# Wiki")
        assert reader_settings._is_valid_wiki_bundle_dir(bundle) is True
