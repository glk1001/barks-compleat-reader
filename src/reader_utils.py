from datetime import datetime
from pathlib import Path
from random import randrange
from typing import Tuple

from cpi import inflate

from barks_fantagraphics.barks_payments import PaymentInfo
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.pages import CleanPage
from reader_consts_and_types import Color

EMPTY_PAGE_KEY = "empty_page"


def prob_rand_less_equal(percent: int) -> bool:
    return randrange(1, 101) < percent


def get_rand_int(min_max: Tuple[int, int]) -> int:
    return randrange(min_max[0], min_max[1] + 1)


def is_title_page(page: CleanPage) -> bool:
    return (Path(page.page_filename).stem == EMPTY_PAGE_KEY) and (page.page_type == PageType.TITLE)


def is_blank_page(page_filename: str, page_type: PageType) -> bool:
    return (Path(page_filename).stem == EMPTY_PAGE_KEY) and (page_type != PageType.TITLE)


def get_formatted_color(color: Color) -> str:
    color_strings = [f"{c:04.2f}" for c in color]
    return f'({", ".join(color_strings)})'


def get_formatted_payment_info(payment_info: PaymentInfo) -> str:
    current_year = datetime.now().year
    cpi_adjusted_payment = inflate(payment_info.payment, payment_info.accepted_year)

    return (
        f"${payment_info.payment:.0f} (${cpi_adjusted_payment:.0f} in {current_year})"
        #        f" ({get_formatted_day(payment_info.accepted_day)}"
        #        f" {MONTH_AS_SHORT_STR[payment_info.accepted_month]}"
        #        f" {payment_info.accepted_year})"
    )
