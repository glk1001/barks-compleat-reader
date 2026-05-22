from __future__ import annotations

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.reader_consts_and_types import FIRST_BODY_PAGE
from barks_reader.core.saved_page_info import SavedPageInfo


class TestJsonRoundTrip:
    def test_to_json_then_from_json_round_trips(self) -> None:
        original = SavedPageInfo(
            page_index=7,
            display_page_num="8",
            page_type=PageType.BODY,
            last_body_page="32",
        )

        restored = SavedPageInfo.from_json(original.to_json())

        assert restored == original

    def test_to_json_serializes_page_type_by_name(self) -> None:
        info = SavedPageInfo(
            page_index=0,
            display_page_num="i",
            page_type=PageType.FRONT,
            last_body_page="10",
        )

        payload = info.to_json()

        assert payload["page_type"] == "FRONT"
        assert payload["page_index"] == 0
        assert payload["display_page_num"] == "i"
        assert payload["last_body_page"] == "10"

    def test_from_json_resolves_page_type_name(self) -> None:
        restored = SavedPageInfo.from_json(
            {
                "page_index": 3,
                "display_page_num": "4",
                "page_type": "BODY",
                "last_body_page": "10",
            }
        )

        assert restored.page_type is PageType.BODY


class TestIsInsideBody:
    def test_middle_body_page_is_inside(self) -> None:
        info = SavedPageInfo(
            page_index=5,
            display_page_num="6",
            page_type=PageType.BODY,
            last_body_page="10",
        )

        assert info.is_inside_body() is True

    def test_first_body_page_is_edge(self) -> None:
        info = SavedPageInfo(
            page_index=0,
            display_page_num=FIRST_BODY_PAGE,
            page_type=PageType.BODY,
            last_body_page="10",
        )

        assert info.is_inside_body() is False

    def test_last_body_page_is_edge(self) -> None:
        info = SavedPageInfo(
            page_index=9,
            display_page_num="10",
            page_type=PageType.BODY,
            last_body_page="10",
        )

        assert info.is_inside_body() is False

    def test_non_body_page_is_not_inside(self) -> None:
        info = SavedPageInfo(
            page_index=0,
            display_page_num="iii",
            page_type=PageType.FRONT,
            last_body_page="10",
        )

        assert info.is_inside_body() is False
