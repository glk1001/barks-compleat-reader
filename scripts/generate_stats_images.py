#!/usr/bin/env python
# ruff: noqa: T201

"""Generate statistics PNG images for the Barks Reader Statistics screen.

Usage:
    uv run scripts/generate_stats_images.py --output-dir <path>

Optional:
    --indexes-dir <path>   Path to the Barks Reader indexes directory, required
                           only for the most-frequent-words table.

The script writes eight PNG files to the output directory:
    stories_per_year.png, pages_per_year.png, payments_per_year.png,
    payment_rate.png, stories_per_series.png, top_characters.png,
    top_locations.png, most_frequent.png (the Word Statistics menu's table)

and ``chart-data.json`` beside them: the numbers each chart was drawn from. The
numbers come from ``barks_reader.core.statistics_series``, where the unit tests
check them; the corpus validator recomputes them against the JSON, so a data edit
without a rerun of this script is reported as a stale chart. This file only draws.
"""

from __future__ import annotations

import json
from itertools import zip_longest
from pathlib import Path  # noqa: TC003  (typer resolves annotations at runtime)
from typing import TYPE_CHECKING, Annotated

# -- matplotlib must be imported before any barks_fantagraphics module that
# might trigger a Kivy import (there are none, but be safe). ----------------
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import typer
from comic_utils.cpi_calculator import get_latest_year
from matplotlib import ticker
from matplotlib.transforms import Bbox

mpl.use("Agg")  # headless backend - no display required

from barks_reader.core.statistics_series import (
    CHART_DATA_FILE,
    CHART_FILES,
    MOST_FREQUENT_FILE,
    Series,
    all_series,
    dump_series,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# -- Constants ---------------------------------------------------------------
FIG_WIDTH = 14
FIG_HEIGHT = 9
DPI = 100
BAR_COLOR = "#4477AA"
ACCENT_COLOR = "#EE6677"
GRID_COLOR = "#DDDDDD"
TITLE_FONT_SIZE = 22
AXIS_FONT_SIZE = 12

STORIES_PER_SERIES_FIG_HEIGHT_MULTIPLIER = 1.1

# --- Word Stats Pixel Configuration ---
# Adjusted widths: Make Count slightly wider for the gray background to look good
WORD_STATS_WORD_COL_PX = 100
WORD_STATS_COUNT_COL_PX = 80
WORD_STATS_ROW_HEIGHT_PX = 30
WORD_STATS_HEADER_HEIGHT_PX = 40
WORD_STATS_TITLE_HEIGHT_PX = 30  # Estimated height of the title (used for axes positioning)
WORD_STATS_TITLE_FONT_SIZE = 12
WORD_STATS_TITLE_TABLE_GAP_PX = 0  # Gap between title bottom and top of table
WORD_STATS_TOP_MARGIN_PX = 0  # Whitespace above the title in the saved image
WORD_STATS_MARGIN_PX = 20  # Whitespace left, right, and below the table in the saved image

WORD_STATS_TOP_N_ITEMS = 80


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


def _year_axes(series: Series, title: str, y_label: str) -> tuple[plt.Figure, plt.Axes]:
    """Make a figure with the per-year styling: a year tick per label, rotated."""
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    _style_ax(ax, title, "Year", y_label)
    ax.set_xticks(series.labels)
    ax.tick_params(axis="x", rotation=45)
    return fig, ax


# -- Chart plotters: each draws one Series into its PNG --------------------


def plot_stories_per_year(series: Series, output_dir: Path) -> None:
    """Bar chart: number of stories submitted per year."""
    fig, ax = _year_axes(series, "Barks Stories Submitted per Year", "Number of Stories")
    ax.bar(series.labels, series.values, color=BAR_COLOR, zorder=3)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def plot_pages_per_year(series: Series, output_dir: Path) -> None:
    """Bar chart: the stories' pages per year, from the payment ledger."""
    fig, ax = _year_axes(series, "Total Pages per Year (from Payment Records)", "Total Pages")
    ax.bar(series.labels, series.values, color=BAR_COLOR, zorder=3)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def plot_payments_per_year(series: Series, output_dir: Path) -> None:
    """Bar chart: total payment (USD) per year."""
    fig, ax = _year_axes(
        series,
        f"Total Payments per Year ({get_latest_year()} USD)",
        f"Payments ({get_latest_year()} USD)",
    )
    ax.bar(series.labels, series.values, color=BAR_COLOR, zorder=3)
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def plot_payment_rate(series: Series, output_dir: Path) -> None:
    """Line chart: average payment rate ($/page) per year."""
    fig, ax = _year_axes(
        series,
        f"Per Page Payment Rate ({get_latest_year()} USD per Page) per Year",
        f"{get_latest_year()} USD / Page",
    )
    ax.plot(
        series.labels,
        series.values,
        color=ACCENT_COLOR,
        linewidth=2,
        marker="o",
        markersize=5,
        zorder=3,
    )
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:.0f}"))
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def plot_stories_per_series(series: Series, output_dir: Path) -> None:
    """Horizontal bar chart: story count per Fantagraphics series."""
    fig, ax = plt.subplots(
        figsize=(
            FIG_WIDTH,
            max(5, round(len(series.labels) * STORIES_PER_SERIES_FIG_HEIGHT_MULTIPLIER)),
        )
    )
    y_pos = np.arange(len(series.labels))
    ax.barh(y_pos, series.values, color=BAR_COLOR, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([str(label) for label in series.labels], fontsize=9)
    ax.invert_yaxis()
    _style_ax(ax, "Stories per Fantagraphics Series", x_label="Number of Stories")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.xaxis.grid(visible=True, color=GRID_COLOR, linewidth=0.8, zorder=0)
    ax.yaxis.grid(visible=False)
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def _plot_top_tags(series: Series, output_dir: Path, title: str, color: str) -> None:
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    x_pos = np.arange(len(series.labels))
    ax.bar(x_pos, series.values, color=color, zorder=3)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([str(label) for label in series.labels], rotation=45, ha="right", fontsize=9)
    _style_ax(ax, title, y_label="Number of Stories")
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, output_dir, CHART_FILES[series.name])


def plot_top_characters(series: Series, output_dir: Path) -> None:
    """Bar chart: the characters tagged in the most stories."""
    title = f"Top {len(series.labels)} Characters by Story Appearances"
    _plot_top_tags(series, output_dir, title, BAR_COLOR)


def plot_top_locations(series: Series, output_dir: Path) -> None:
    """Bar chart: the places tagged in the most stories."""
    title = f"Top {len(series.labels)} Locations by Story Appearances"
    _plot_top_tags(series, output_dir, title, ACCENT_COLOR)


PLOTTERS: dict[str, Callable[[Series, Path], None]] = {
    "stories_per_year": plot_stories_per_year,
    "pages_per_year": plot_pages_per_year,
    "payments_per_year": plot_payments_per_year,
    "payment_rate": plot_payment_rate,
    "stories_per_series": plot_stories_per_series,
    "top_characters": plot_top_characters,
    "top_locations": plot_top_locations,
}
assert PLOTTERS.keys() == CHART_FILES.keys()


def gen_word_statistics(output_dir: Path, indexes_dir: Path | None) -> None:  # noqa: PLR0915
    """Table image: top words from the search engine term list.

    Args:
        output_dir: Directory to write the output PNG.
        indexes_dir: Path to the Barks Reader Indexes directory that contains
                     ``most-common-terms.json``. If None this chart is skipped.

    """
    # --- LOAD DATA ---
    if indexes_dir is None:
        return
    most_common_terms_file = indexes_dir / "most-common-unstemmed-terms.json"
    if not most_common_terms_file.is_file():
        return
    terms: list[tuple[str, int]] = json.loads(most_common_terms_file.read_text())

    top = terms[:WORD_STATS_TOP_N_ITEMS]
    if not top:
        return

    # --- 3. PREPARE COLUMNS ---
    n = len(top)
    chunk_size = (n + 3) // 4

    s1 = top[0:chunk_size]
    s2 = top[chunk_size : chunk_size * 2]
    s3 = top[chunk_size * 2 : chunk_size * 3]
    s4 = top[chunk_size * 3 :]

    table_data = []
    for c1, c2, c3, c4 in zip_longest(s1, s2, s3, s4, fillvalue=("", "")):
        table_data.append([c1[0], c1[1], c2[0], c2[1], c3[0], c3[1], c4[0], c4[1]])

    col_labels = ["Word", "Count", "Word", "Count", "Word", "Count", "Word", "Count"]

    # --- 4. CALCULATE EXACT DIMENSIONS ---
    total_width_px = (WORD_STATS_WORD_COL_PX + WORD_STATS_COUNT_COL_PX) * 4

    # Figure height only needs to be large enough to hold the content; the actual
    # saved image dimensions are determined by measuring rendered bboxes (section 9).
    total_height_px = (
        WORD_STATS_TITLE_HEIGHT_PX
        + WORD_STATS_TITLE_TABLE_GAP_PX
        + WORD_STATS_HEADER_HEIGHT_PX
        + (len(table_data) * WORD_STATS_ROW_HEIGHT_PX)
    )

    fig_width_inch = total_width_px / DPI
    fig_height_inch = total_height_px / DPI

    rel_w_word = WORD_STATS_WORD_COL_PX / total_width_px
    rel_w_count = WORD_STATS_COUNT_COL_PX / total_width_px
    column_widths = [rel_w_word, rel_w_count] * 4

    # --- SETUP PLOT ---
    fig, ax = plt.subplots(figsize=(fig_width_inch, fig_height_inch), dpi=DPI)
    ax.axis("off")
    fig.set_facecolor("white")

    # --- POSITIONING ---

    # Title sits at the figure top; WORD_STATS_TOP_MARGIN_PX is applied only when computing the
    # saved-image bbox (section 9) and does not affect the table position.
    title_y_pos = 1.0

    # Axes starts below the title text + gap; WORD_STATS_TOP_MARGIN_PX is intentionally excluded
    # so that TITLE_TABLE_GAP_PX is the sole control for that spacing.
    header_start_px = WORD_STATS_TITLE_HEIGHT_PX + WORD_STATS_TITLE_TABLE_GAP_PX
    axes_top_pos = 1.0 - (header_start_px / total_height_px)

    # Manually constrain the Axes to the bottom section
    plt.subplots_adjust(left=0, right=1, bottom=0, top=axes_top_pos)

    # --- CONTENT ---

    # Title (Anchor to top); save reference for bbox measurement below.
    title_text = fig.text(
        x=0.5,
        y=title_y_pos,
        s="Most Frequently Used Barksian Words",
        fontsize=WORD_STATS_TITLE_FONT_SIZE,
        fontweight="bold",
        ha="center",
        va="top",  # Text grows downwards from the y-point
    )

    # Table (Anchor to the top of the Axes area we defined)
    # noinspection PyArgumentList
    tbl = ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="upper center",
        cellLoc="left",
        colWidths=column_widths,
    )

    # --- 8. STYLING ---
    tbl.auto_set_font_size(value=False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.2)

    # Style Header
    for col_idx in range(8):
        cell = tbl[0, col_idx]
        cell.set_facecolor("#4477AA")
        cell.set_text_props(color="white", fontweight="bold")
        cell.set_edgecolor("white")
        cell.set_linewidth(1)

    # Style Rows
    for row_idx in range(1, len(table_data) + 1):
        for col_idx in range(8):
            cell = tbl[row_idx, col_idx]
            if col_idx % 2 != 0:
                cell.set_facecolor("#EAEAEA")
                cell.set_text_props(ha="center")
            else:
                cell.set_facecolor("white")
                cell.set_text_props(ha="left", fontweight="bold")
            cell.set_edgecolor("#cccccc")

    # --- SAVE ---
    # bbox_inches='tight' does not reliably detect ax.table() extents (the axes extent
    # is used instead of the table cells). Measure the actual rendered positions directly.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()  # ty:ignore[unresolved-attribute]

    tbl_px = tbl.get_window_extent(renderer=renderer)
    title_px = title_text.get_window_extent(renderer=renderer)

    # Union bounding box of title + table in display pixels (origin = figure bottom-left).
    # Apply margins independently: WORD_STATS_TOP_MARGIN_PX above the title, WORD_STATS_MARGIN_PX on
    # the other three sides.  TITLE_TABLE_GAP_PX controls the gap between them (via
    # axes positioning in section 6) and is not involved here.
    x0 = min(tbl_px.x0, title_px.x0)
    y0 = min(tbl_px.y0, title_px.y0)
    x1 = max(tbl_px.x1, title_px.x1)
    y1 = max(tbl_px.y1, title_px.y1)

    m = WORD_STATS_MARGIN_PX
    bbox_inch = Bbox(
        [
            [(x0 - m) / DPI, (y0 - m) / DPI],
            [(x1 + m) / DPI, (y1 + WORD_STATS_TOP_MARGIN_PX) / DPI],
        ]
    )

    path = output_dir / MOST_FREQUENT_FILE
    fig.savefig(path, dpi=DPI, bbox_inches=bbox_inch, facecolor="white")
    plt.close(fig)
    print(f"  Wrote {path}")


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

    series = all_series()
    for chart in series:
        PLOTTERS[chart.name](chart, output_dir)
    sidecar = output_dir / CHART_DATA_FILE
    sidecar.write_text(dump_series(series) + "\n", encoding="utf-8")
    print(f"  Wrote {sidecar}")

    gen_word_statistics(output_dir, indexes_dir)

    print("Done.")


if __name__ == "__main__":
    typer.run(main)
