# ruff: noqa: T201, ERA001

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, NUM_TITLES


def get_top_title_lengths() -> list[tuple[int, str]]:
    # if title in NON_COMIC_TITLES:
    #     continue
    sorted_by_len = sorted(ENUM_TO_STR_TITLE, key=lambda x: len(x), reverse=True)
    return [(len(t), t) for t in sorted_by_len[:10]]


if __name__ == "__main__":
    top_ten = get_top_title_lengths()

    for title in top_ten:
        print(f'Len title: {title[0]}, "{title[1]}".')

    print()
    print(f"Num titles: {NUM_TITLES} (len(ENUM_TO_STR_TITLE) = {len(ENUM_TO_STR_TITLE)}).")
