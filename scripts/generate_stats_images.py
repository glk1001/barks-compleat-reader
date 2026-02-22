#!/usr/bin/env python
# ruff: noqa: T201
"""Generate statistics PNG images for the Barks Reader Statistics screen.

Usage:
    uv run python scripts/generate_stats_images.py --output-dir <path>

Optional:
    --indexes-dir <path>   Path to the Barks Reader indexes directory, required
                           only for the Word Statistics chart.

The script writes eight PNG files to the output directory:
    stories_per_year.png, pages_per_year.png, payments_per_year.png,
    payment_rate.png, stories_per_series.png, top_characters.png,
    top_locations.png, word_statistics.png
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path  # noqa: TC003  (typer resolves annotations at runtime)
from typing import Annotated

# -- matplotlib must be imported before any barks_fantagraphics module that
# might trigger a Kivy import (there are none, but be safe). ----------------
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import typer
from matplotlib import ticker

mpl.use("Agg")  # headless backend - no display required

# -- barks_fantagraphics imports ---------------------------------------------
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_TITLES,
    TagCategories,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO

# -- Constants ---------------------------------------------------------------
FIG_WIDTH = 14
FIG_HEIGHT = 7
DPI = 120
BAR_COLOR = "#4477AA"
ACCENT_COLOR = "#EE6677"
GRID_COLOR = "#DDDDDD"
TITLE_FONT_SIZE = 14
AXIS_FONT_SIZE = 10


# -- Helpers -----------------------------------------------------------------


def _save(fig: plt.Figure, output_dir: Path, filename: str) -> None:
    path = output_dir / filename
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Wrote {path}")


def _style_ax(ax: plt.Axes, title: str, x_label: str = "", y_label: str = "") -> None:
    ax.set_title(title, fontsize=TITLE_FONT_SIZE, fontweight="bold", pad=12)
    if x_label:
        ax.set_xlabel(x_label, fontsize=AXIS_FONT_SIZE)
    if y_label:
        ax.set_ylabel(y_label, fontsize=AXIS_FONT_SIZE)
    ax.yaxis.grid(visible=True, color=GRID_COLOR, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _get_all_tags_in_category(category: TagCategories) -> list[Tags]:
    """Recursively flatten a tag category into individual Tags (no TagGroups)."""
    result: list[Tags] = []
    for item in BARKS_TAG_CATEGORIES[category]:
        if isinstance(item, Tags):
            result.append(item)
        elif isinstance(item, TagGroups):
            result.extend(_flatten_tag_group(item))
    return result


def _flatten_tag_group(group: TagGroups) -> list[Tags]:
    result: list[Tags] = []
    for item in BARKS_TAG_GROUPS[group]:
        if isinstance(item, Tags):
            result.append(item)
        elif isinstance(item, TagGroups):
            result.extend(_flatten_tag_group(item))
    return result


# -- Chart generators --------------------------------------------------------


def gen_stories_per_year(output_dir: Path) -> None:
    """Bar chart: number of stories accepted per year."""
    counts: dict[int, int] = defaultdict(int)
    for info in BARKS_TITLE_INFO:
        if info.is_barks_title:
            counts[info.submitted_year] += 1

    years = sorted(counts)
    values = [counts[y] for y in years]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.bar(years, values, color=BAR_COLOR, zorder=3)
    _style_ax(ax, "Barks Stories Accepted per Year", "Year", "Number of Stories")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, "stories_per_year.png")


def gen_pages_per_year(output_dir: Path) -> None:
    """Bar chart: total pages per year from payment records."""
    totals: dict[int, int] = defaultdict(int)
    for info in BARKS_PAYMENTS.values():
        totals[info.accepted_year] += info.num_pages

    years = sorted(totals)
    values = [totals[y] for y in years]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.bar(years, values, color=BAR_COLOR, zorder=3)
    _style_ax(ax, "Total Pages per Year (from Payment Records)", "Year", "Total Pages")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, "pages_per_year.png")


def gen_payments_per_year(output_dir: Path) -> None:
    """Bar chart: total payment (USD) per year."""
    totals: dict[int, float] = defaultdict(float)
    for info in BARKS_PAYMENTS.values():
        totals[info.accepted_year] += info.payment

    years = sorted(totals)
    values = [totals[y] for y in years]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.bar(years, values, color=BAR_COLOR, zorder=3)
    _style_ax(ax, "Total Payment per Year (USD)", "Year", "Payment (USD)")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    fig.tight_layout()
    _save(fig, output_dir, "payments_per_year.png")


def gen_payment_rate(output_dir: Path) -> None:
    """Line chart: average payment rate ($/page) per year."""
    pages: dict[int, int] = defaultdict(int)
    payments: dict[int, float] = defaultdict(float)
    for info in BARKS_PAYMENTS.values():
        pages[info.accepted_year] += info.num_pages
        payments[info.accepted_year] += info.payment

    years = sorted(pages)
    rates = [payments[y] / pages[y] if pages[y] else 0.0 for y in years]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.plot(years, rates, color=ACCENT_COLOR, linewidth=2, marker="o", markersize=5, zorder=3)
    _style_ax(ax, "Payment Rate (USD per Page) per Year", "Year", "USD / Page")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:.2f}"))
    fig.tight_layout()
    _save(fig, output_dir, "payment_rate.png")


def gen_stories_per_series(output_dir: Path) -> None:
    """Horizontal bar chart: story count per Fantagraphics series."""
    counts: dict[str, int] = defaultdict(int)
    for info in ALL_FANTA_COMIC_BOOK_INFO.values():
        series = info.series_name or "Unknown"
        counts[series] += 1

    # Sort by count descending
    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    series_names = [kv[0] for kv in sorted_items]
    values = [kv[1] for kv in sorted_items]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, max(5, round(len(series_names) * 0.55))))
    y_pos = np.arange(len(series_names))
    ax.barh(y_pos, values, color=BAR_COLOR, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(series_names, fontsize=9)
    ax.invert_yaxis()
    _style_ax(ax, "Stories per Fantagraphics Series", x_label="Number of Stories")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.xaxis.grid(visible=True, color=GRID_COLOR, linewidth=0.8, zorder=0)
    ax.yaxis.grid(visible=False)
    fig.tight_layout()
    _save(fig, output_dir, "stories_per_series.png")


def gen_top_characters(output_dir: Path, top_n: int = 20) -> None:
    """Bar chart: top N characters by story appearance count."""
    char_tags = _get_all_tags_in_category(TagCategories.CHARACTERS)
    counts: dict[str, int] = {}
    for tag in char_tags:
        titles = BARKS_TAGGED_TITLES.get(tag, [])
        if titles:
            counts[tag.value] = len(titles)

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    if not sorted_items:
        print("  No character data found; skipping top_characters.png")
        return

    names = [kv[0] for kv in sorted_items]
    values = [kv[1] for kv in sorted_items]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    x_pos = np.arange(len(names))
    ax.bar(x_pos, values, color=BAR_COLOR, zorder=3)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=9)
    _style_ax(ax, f"Top {top_n} Characters by Story Appearances", y_label="Number of Stories")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, "top_characters.png")


def gen_top_locations(output_dir: Path, top_n: int = 20) -> None:
    """Bar chart: top N locations by story appearance count."""
    place_tags = _get_all_tags_in_category(TagCategories.PLACES)
    counts: dict[str, int] = {}
    for tag in place_tags:
        titles = BARKS_TAGGED_TITLES.get(tag, [])
        if titles:
            counts[tag.value] = len(titles)

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    if not sorted_items:
        print("  No location data found; skipping top_locations.png")
        return

    names = [kv[0] for kv in sorted_items]
    values = [kv[1] for kv in sorted_items]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    x_pos = np.arange(len(names))
    ax.bar(x_pos, values, color=ACCENT_COLOR, zorder=3)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=9)
    _style_ax(ax, f"Top {top_n} Locations by Story Appearances", y_label="Number of Stories")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, "top_locations.png")


def gen_word_statistics(output_dir: Path, indexes_dir: Path | None) -> None:
    """Table image: top words from the search engine term list.

    Args:
        output_dir: Directory to write the output PNG.
        indexes_dir: Path to the Barks Reader Indexes directory that contains
                     ``cleaned-unstemmed-terms.json``. If None this chart is skipped.

    """
    if indexes_dir is None:
        print("  --indexes-dir not provided; skipping word_statistics.png")
        return

    terms_file = indexes_dir / "cleaned-unstemmed-terms.json"
    if not terms_file.is_file():
        print(f"  Terms file not found: {terms_file}; skipping word_statistics.png")
        return

    terms: list[str] = json.loads(terms_file.read_text())
    # Build frequency count from the flat list (each occurrence is one entry)
    freq: dict[str, int] = defaultdict(int)
    for word in terms:
        if word:
            freq[word.lower()] += 1

    top = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:40]
    if not top:
        print("  No word data found; skipping word_statistics.png")
        return

    words = [kv[0] for kv in top]
    counts = [kv[1] for kv in top]

    # Two-column table layout
    n = len(top)
    half = (n + 1) // 2
    col1 = [(words[i], counts[i]) for i in range(half)]
    col2 = [(words[i], counts[i]) for i in range(half, n)]

    # Pad col2 if shorter
    while len(col2) < len(col1):
        # noinspection PyTypeChecker
        col2.append(("", ""))

    table_data = [[c1[0], c1[1], c2[0], c2[1]] for c1, c2 in zip(col1, col2, strict=False)]
    col_labels = ["Word", "Count", "Word", "Count"]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, max(5, round(half * 0.4) + 2)))
    ax.axis("off")
    # noinspection PyArgumentList
    tbl = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc="left",
        loc="center",
    )
    tbl.auto_set_font_size(value=False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.3)
    # Style header cells
    for col_idx in range(len(col_labels)):
        tbl[0, col_idx].set_facecolor("#4477AA")
        tbl[0, col_idx].set_text_props(color="white", fontweight="bold")
    ax.set_title(
        "Top Words in Comic Script (cleaned unstemmed terms)",
        fontsize=TITLE_FONT_SIZE,
        fontweight="bold",
        pad=12,
    )
    fig.tight_layout()
    _save(fig, output_dir, "word_statistics.png")


# -- CLI entry point ---------------------------------------------------------


def main(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory to write the PNG files (will be created if absent)."),
    ],
    indexes_dir: Annotated[
        Path | None,
        typer.Option(
            help=(
                "Path to the Barks Reader Indexes directory containing"
                " cleaned-unstemmed-terms.json. Required only for the Word Statistics chart."
            )
        ),
    ] = None,
) -> None:
    """Generate pre-rendered statistics PNG images for the Barks Reader."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating statistics PNGs in: {output_dir}")

    gen_stories_per_year(output_dir)
    gen_pages_per_year(output_dir)
    gen_payments_per_year(output_dir)
    gen_payment_rate(output_dir)
    gen_stories_per_series(output_dir)
    gen_top_characters(output_dir)
    gen_top_locations(output_dir)
    gen_word_statistics(output_dir, indexes_dir)

    print("Done.")


if __name__ == "__main__":
    typer.run(main)
