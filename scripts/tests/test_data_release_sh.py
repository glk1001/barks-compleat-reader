"""The release scripts' shell constants match the ones core/data_pack.py owns."""

from __future__ import annotations

import re
from pathlib import Path

from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, PACK_MEMBER

_RELEASE_SH = Path(__file__).resolve().parent.parent / "_data_release.sh"


def _shell_value(name: str) -> str:
    match = re.search(rf'^{name}="([^"]*)"$', _RELEASE_SH.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None, f"{name} is not set in {_RELEASE_SH.name}"
    return match.group(1)


def test_the_pack_names_and_the_version_member_are_the_readers() -> None:
    assert (_shell_value("DATA1_ZIP"), _shell_value("DATA2_ZIP")) == DATA_PACK_FILE_NAMES
    assert _shell_value("PACK_MEMBER") == PACK_MEMBER
