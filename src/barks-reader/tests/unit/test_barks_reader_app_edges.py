# ruff: noqa: SLF001
"""The app's edges no GUI run reaches: failures, refusals and the rarer settings.

Each runs on a stand-in for the app, or calls a module function directly, with
the window and Kivy's clock stood in for; no Kivy app is booted.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.barks_reader_app as app_module
import pytest
from barks_reader.ui.barks_reader_app import BarksReaderApp
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen, SwapTransition, TransitionBase

if TYPE_CHECKING:
    from collections.abc import Iterator

_WORKAROUND_FLAG = "_kivy_workaround_applied"


def _app(**attrs: object) -> Any:  # noqa: ANN401
    return cast("Any", SimpleNamespace(**attrs))


def test_settings_before_any_window_is_refused() -> None:
    with pytest.raises(RuntimeError, match="you cannot open settings yet"):
        BarksReaderApp.display_settings(_app(_app_window=None), MagicMock())


class TestCustomTitleBar:
    def _set(self, *, allowed: bool) -> MagicMock:
        with patch.object(app_module, "Window") as window:
            window.set_custom_titlebar.return_value = allowed
            BarksReaderApp._set_custom_title_bar(_app(_main_screen=MagicMock()))
        return window

    def test_where_the_system_allows_it_the_bar_drags_the_window(
        self, loguru_sink: list[str]
    ) -> None:
        window = self._set(allowed=True)
        assert window.custom_titlebar is True
        assert "Window: setting custom titlebar successful" in loguru_sink

    def test_where_it_does_not_the_system_bar_stays_and_it_says_so(
        self, loguru_sink: list[str]
    ) -> None:
        self._set(allowed=False)
        assert "Window: setting custom titlebar not allowed on this system." in loguru_sink


class TestFinalizeWindowSetup:
    @pytest.fixture
    def app(self) -> Any:  # noqa: ANN401
        reader_settings = MagicMock()
        reader_settings.sys_file_paths.get_barks_reader_app_window_icon_path.return_value = Path(
            "/icons/app.png"
        )
        return _app(
            reader_settings=reader_settings,
            _window_geometry=MagicMock(),
            _main_screen=MagicMock(),
            icon=None,
        )

    def _finalize(self, app: Any, *, monitors: int) -> tuple[MagicMock, MagicMock]:  # noqa: ANN401
        with (
            patch.object(app_module, "Window") as window,
            patch.object(app_module, "Config") as config,
            patch.object(app_module, "Clock") as clock,
            patch.object(app_module, "write_linux_desktop_entry"),
            patch.object(app_module, "force_x11_wm_class"),
            patch.object(app_module.SCREEN_METRICS, "NUM_MONITORS", monitors),
        ):
            config.getint.side_effect = lambda _section, key: {"left": 40, "top": 30}[key]
            BarksReaderApp._finalize_window_setup(app)
        return window, clock

    def test_with_several_monitors_a_move_is_followed_too(self, app: Any) -> None:  # noqa: ANN401
        window, _ = self._finalize(app, monitors=2)
        window.bind.assert_any_call(on_move=app._window_geometry.on_window_pos_change)
        window.bind.assert_any_call(on_resize=app._window_geometry.on_window_resize)

    def test_with_one_monitor_only_a_resize_is(self, app: Any) -> None:  # noqa: ANN401
        window, _ = self._finalize(app, monitors=1)
        window.bind.assert_called_once_with(on_resize=app._window_geometry.on_window_resize)

    def test_full_screen_at_start_when_set_and_shown_after_the_delay(
        self,
        app: Any,  # noqa: ANN401
    ) -> None:
        app.reader_settings.goto_fullscreen_on_app_start = True

        window, clock = self._finalize(app, monitors=1)

        app._main_screen.force_fullscreen.assert_called_once_with()
        assert app.icon == str(Path("/icons/app.png"))
        assert (window.left, window.top) == (40, 30)  # nudged and put back
        assert clock.schedule_once.call_args.args[1] == app_module.WINDOW_SHOW_DELAY

    def test_not_full_screen_when_not_set(self, app: Any) -> None:  # noqa: ANN401
        app.reader_settings.goto_fullscreen_on_app_start = False
        self._finalize(app, monitors=1)
        app._main_screen.force_fullscreen.assert_not_called()


class TestAltEscapeDismissesTheTopPopup:
    ALT_KEY = 113

    def _press(self, children: list[object], key: int = ALT_KEY) -> bool:
        with (
            patch.object(app_module, "get_alt_escape_key", return_value=self.ALT_KEY),
            patch.object(app_module, "is_escape_key", return_value=True),
            patch.object(app_module, "Window") as window,
        ):
            window.children = children
            return app_module._dismiss_top_popup_on_alt_escape(None, key, 0, "", [])

    @staticmethod
    def _popup(*, auto_dismiss: bool) -> MagicMock:
        popup = MagicMock(spec=ModalView)
        popup.auto_dismiss = auto_dismiss
        return popup

    def test_the_first_popup_that_closes_on_its_own_is_closed(self) -> None:
        held = self._popup(auto_dismiss=False)
        closes = self._popup(auto_dismiss=True)

        assert self._press([object(), held, closes]) is True

        held.dismiss.assert_not_called()
        closes.dismiss.assert_called_once_with()

    def test_with_no_such_popup_the_key_is_left_alone(self) -> None:
        assert self._press([object(), self._popup(auto_dismiss=False)]) is False

    def test_another_key_is_left_alone(self) -> None:
        popup = self._popup(auto_dismiss=True)
        assert self._press([popup], key=self.ALT_KEY + 1) is False
        popup.dismiss.assert_not_called()


class TestSwapTransitionWorkaround:
    """Kivy 2.3.1's SwapTransition ends by calling a canvas method that does not exist.

    The app patches it in build(): that one AttributeError is caught and the
    transition finished by hand, and any other is raised.
    """

    @pytest.fixture
    def patched(self) -> Iterator[MagicMock]:
        """Run build() just as far as installing the patch, over a failing original.

        Returns the original on_complete the patch wraps; Kivy's own is put back after.
        """
        had_flag = _WORKAROUND_FLAG in SwapTransition.__dict__
        if had_flag:
            delattr(SwapTransition, _WORKAROUND_FLAG)

        class _StopBuildError(Exception):
            pass

        original = MagicMock(name="SwapTransition.on_complete")
        app = _app(_initialize_settings_and_db=MagicMock(side_effect=_StopBuildError))
        try:
            with (
                patch.object(SwapTransition, "on_complete", original),
                patch.object(app_module, "apply_text_input_remove_group_patch"),
            ):
                with pytest.raises(_StopBuildError):
                    BarksReaderApp.build(app)
                assert SwapTransition.on_complete is not original
                yield original
        finally:
            if had_flag:
                setattr(SwapTransition, _WORKAROUND_FLAG, True)
            elif _WORKAROUND_FLAG in SwapTransition.__dict__:
                delattr(SwapTransition, _WORKAROUND_FLAG)

    @staticmethod
    def _transition() -> SwapTransition:
        transition = SwapTransition()
        transition.screen_in = Screen()
        transition.screen_out = Screen()
        return transition

    def test_the_missing_canvas_method_is_worked_around(self, patched: MagicMock) -> None:
        patched.side_effect = AttributeError("'Canvas' object has no attribute '_remove_group'")
        transition = self._transition()

        with patch.object(TransitionBase, "on_complete") as finish:
            transition.on_complete()

        patched.assert_called_once_with(transition)
        finish.assert_called_once_with()

    def test_any_other_attribute_error_is_raised(self, patched: MagicMock) -> None:
        patched.side_effect = AttributeError("something else")
        with pytest.raises(AttributeError, match="something else"):
            self._transition().on_complete()

    def test_without_an_error_the_original_does_it_all(self, patched: MagicMock) -> None:
        transition = self._transition()
        with patch.object(TransitionBase, "on_complete") as finish:
            transition.on_complete()
        patched.assert_called_once_with(transition)
        finish.assert_not_called()


class TestAppFailure:
    def test_an_uncaught_error_shows_the_apps_error_popup(self) -> None:
        config_info = MagicMock()
        error = ValueError("boom")
        with patch.object(app_module, "handle_app_fail_with_traceback") as fail:
            app_module._handle_app_exception(config_info, ValueError, error, None)

        args = fail.call_args
        assert args.args == ("app", "Barks Reader", ValueError, error, None)
        assert args.kwargs == {
            "log_path": str(config_info.app_log_path),
            "log_the_error": False,
            "background_image_file": config_info.error_background_path,
        }

    def test_an_error_while_running_is_logged_and_handled(self, loguru_sink: list[str]) -> None:
        config_info = MagicMock()
        with (
            patch.object(app_module, "log_screen_metrics", side_effect=RuntimeError("no screen")),
            patch.object(app_module, "_handle_app_exception") as handle,
            patch.object(app_module, "Window"),
        ):
            app_module.reader_main(config_info)

        handled_config, exc_type, exc_value, _ = handle.call_args.args
        assert handled_config is config_info
        assert exc_type is RuntimeError
        assert str(exc_value) == "no screen"
        assert any(
            line.startswith("There's been a program error - the Barks reader app is terminating")
            for line in loguru_sink
        )


class TestOnStop:
    """Closing saves the main screen's and the wiki's state, whichever of them exists."""

    @pytest.mark.parametrize("has_main", [False, True])
    @pytest.mark.parametrize("has_wiki", [False, True])
    def test_whatever_screens_were_built_are_saved_once(
        self, has_main: bool, has_wiki: bool
    ) -> None:
        main = MagicMock() if has_main else None
        wiki = MagicMock() if has_wiki else None
        app = _app(
            _on_stop_done=False,
            _window_geometry=MagicMock(),
            _main_screen=main,
            _wiki_reader_screen=wiki,
        )
        BarksReaderApp.on_stop(app)
        BarksReaderApp.on_stop(app)

        app._window_geometry.stop_polling.assert_called_once_with()
        if main is not None:
            main.app_closing.assert_called_once_with()
        if wiki is not None:
            wiki.save_session.assert_called_once_with()


def test_a_second_build_leaves_the_swap_transition_patch_alone() -> None:
    class _StopBuildError(Exception):
        pass

    original = MagicMock(name="SwapTransition.on_complete")
    app = _app(_initialize_settings_and_db=MagicMock(side_effect=_StopBuildError))
    with (
        patch.object(SwapTransition, _WORKAROUND_FLAG, True, create=True),  # noqa: FBT003
        patch.object(SwapTransition, "on_complete", original),
        patch.object(app_module, "apply_text_input_remove_group_patch"),
    ):
        with pytest.raises(_StopBuildError):
            BarksReaderApp.build(app)
        assert SwapTransition.on_complete is original


# Everything _build_screens makes before the wiki screen, stood in for.
_BUILT_BEFORE_THE_WIKI = (
    "UserErrorHandler",
    "FilteredTitleLists",
    "ReaderTreeBuilderEventDispatcher",
    "TreeViewScreen",
    "BottomTitleViewScreen",
    "FunImageViewScreen",
    "MainIndexScreen",
    "SpeechIndexScreen",
    "EntityIndexScreen",
    "StatisticsScreen",
    "HistoryScreen",
    "SearchScreen",
    "WindowManager",
    "ScreenBundle",
    "MainScreen",
    "get_barks_comic_reader_screen",
    "get_document_reader_screen",
)


class TestWikiSessionMigration:
    """At build, a wiki session kept beside the app data is copied into the profile."""

    class _StopBuildError(Exception):
        pass

    def _build_to_the_wiki(self, bundle: Path | None, migrated: Path | None) -> MagicMock:
        app = _app(
            reader_settings=MagicMock(wiki_bundle_dir=bundle),
            font_manager=MagicMock(),
            _reader_screen_manager=MagicMock(),
            _screen_switchers=MagicMock(),
            _comics_database=MagicMock(),
            _config_info=SimpleNamespace(app_config_dir="/profile", app_data_dir="/data"),
            _set_custom_title_bar=MagicMock(),
            _main_screen=None,
        )
        with ExitStack() as stack:
            for name in _BUILT_BEFORE_THE_WIKI:
                stack.enter_context(patch.object(app_module, name))
            stack.enter_context(patch.object(app_module.Config, "getint", return_value=1000))
            migrate = stack.enter_context(
                patch.object(app_module, "migrate_wiki_session", return_value=migrated)
            )
            stack.enter_context(
                patch.object(app_module, "get_wiki_reader_screen", side_effect=self._StopBuildError)
            )
            with pytest.raises(self._StopBuildError):
                BarksReaderApp._build_screens(app)
        return migrate

    def test_a_session_found_is_copied_and_said(self, loguru_sink: list[str]) -> None:
        migrate = self._build_to_the_wiki(Path("/bundle"), Path("/profile/wiki-session.json"))
        migrate.assert_called_once_with(Path("/data"), Path("/profile"), Path("/bundle"))
        assert (
            f'Copied the wiki session into the profile: "{Path("/profile/wiki-session.json")}".'
            in loguru_sink
        )

    def test_none_found_is_not_said(self, loguru_sink: list[str]) -> None:
        self._build_to_the_wiki(Path("/bundle"), None)
        assert not any("Copied the wiki session" in line for line in loguru_sink)

    def test_with_no_wiki_bundle_nothing_is_looked_for(self) -> None:
        migrate = self._build_to_the_wiki(None, None)
        migrate.assert_not_called()
