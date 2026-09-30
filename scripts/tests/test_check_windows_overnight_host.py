"""Tests for the Windows overnight host check: how it reads and judges what it finds.

What it asks Windows (the registry, powercfg, tasklist) runs only there; what
is tested here, on every platform, is the parsing and the verdicts.
"""

# cspell:ignore tasklist

from __future__ import annotations

from typing import TYPE_CHECKING

import check_windows_overnight_host as ch
import pytest

if TYPE_CHECKING:
    from pathlib import Path

POWERCFG = """Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)
  Subgroup GUID: 7516b95f-f776-4464-8c53-06167f40cc99  (Display)
    Power Setting GUID: 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e  (Turn off display after)
      Possible Settings units: Seconds
    Current AC Power Setting Index: 0x00002a30
    Current DC Power Setting Index: 0x000000f0
"""


class TestAcIndex:
    def test_the_ac_value_not_the_dc_one(self) -> None:
        assert ch.ac_index(POWERCFG) == 10800  # noqa: PLR2004

    def test_no_setting(self) -> None:
        assert ch.ac_index("The system cannot find the path specified.") is None


class TestIdleCheck:
    @pytest.mark.parametrize("secs", [0, ch.MIN_IDLE_SECS, 10800])
    def test_never_or_longer_than_a_run(self, secs: int) -> None:
        assert ch.idle_check("sleep", secs)[0] == "OK"

    def test_shorter_than_a_run_warns(self) -> None:
        status, text = ch.idle_check("the non-sensor presence timeout", 240)
        assert status == "WARN"
        assert "after 4 min" in text

    def test_no_such_setting(self) -> None:
        assert ch.idle_check("sleep", None)[0] == "--"


class TestSignInCheck:
    def test_never(self) -> None:
        assert ch.sign_in_check(ch.SIGN_IN_NEVER)[0] == "OK"

    @pytest.mark.parametrize("delay", [900, 0, None])
    def test_anything_else_fails(self, delay: int | None) -> None:
        assert ch.sign_in_check(delay)[0] == "FAIL"


class TestScreenSaverCheck:
    def test_none(self) -> None:
        assert ch.screen_saver_check("", "")[0] == "OK"

    def test_with_a_password(self) -> None:
        assert ch.screen_saver_check("C:\\Windows\\system32\\Mystify.scr", "1")[0] == "FAIL"

    def test_without_one(self) -> None:
        assert ch.screen_saver_check("C:\\Windows\\system32\\Mystify.scr", "0")[0] == "OK"


class TestPresenceLockChecks:
    def test_glance_fails_whatever_its_case(self) -> None:
        (check,) = ch.presence_lock_checks({"explorer.exe", "GLANCE.EXE"})
        assert check[0] == "FAIL"
        assert "Walk Away Lock" in check[1]

    def test_none_running(self) -> None:
        assert ch.presence_lock_checks({"explorer.exe"}) == [
            ("OK", "no webcam presence-lock app running")
        ]


class TestWikiCopyChecks:
    @staticmethod
    def _wiki(tmp_path: Path, text: bytes) -> Path:
        wiki = tmp_path / ch.WIKI_SUBPATH
        wiki.mkdir(parents=True)
        (wiki / "index.md").write_bytes(text)
        return tmp_path

    def test_an_lf_copy(self, tmp_path: Path) -> None:
        assert ch.wiki_copy_checks(self._wiki(tmp_path, b"# Wiki\n\ntext\n"))[0][0] == "OK"

    def test_a_crlf_copy_warns(self, tmp_path: Path) -> None:
        (check,) = ch.wiki_copy_checks(self._wiki(tmp_path, b"# Wiki\r\n\r\ntext\r\n"))
        assert check[0] == "WARN"
        assert "CRLF" in check[1]

    def test_no_copy_fails(self, tmp_path: Path) -> None:
        assert ch.wiki_copy_checks(tmp_path)[0][0] == "FAIL"

    def test_no_data_dir_fails(self) -> None:
        assert ch.wiki_copy_checks(None)[0][0] == "FAIL"


class TestMain:
    def test_windows_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ch.sys, "platform", "linux")
        assert ch.main() == 2  # noqa: PLR2004
