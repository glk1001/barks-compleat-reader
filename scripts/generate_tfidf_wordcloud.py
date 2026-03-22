#!/usr/bin/env python
# ruff: noqa: T201

"""Generate a TF-IDF word cloud and ranked word list from Barks comic speech text.

Usage:
    uv run python scripts/generate_tfidf_wordcloud.py \
        --indexes-dir <path> --output-dir <path>

Optional:
    --start-year INT   First year to include (default 1942)
    --end-year   INT   Last year to include (default 1966)

Output files:
    tfidf_wordcloud.png    — word cloud image
    tfidf_ranked_words.txt — ranked word list with TF-IDF scores
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path  # noqa: TC003
from typing import Annotated

import matplotlib as mpl
import matplotlib.pyplot as plt
import typer
from sklearn.feature_extraction.text import TfidfVectorizer
from wordcloud import WordCloud

mpl.use("Agg")

from barks_fantagraphics.barks_titles import BARKS_TITLE_INFO
from barks_fantagraphics.whoosh_search_engine import SearchEngine

# -- Constants ---------------------------------------------------------------
WORDCLOUD_WIDTH = 1668
WORDCLOUD_HEIGHT = 1176
WORDCLOUD_MAX_WORDS = 200
WORDCLOUD_BG_COLOR = "white"
FIG_DPI = 100


# -- Helpers -----------------------------------------------------------------


def _get_titles_in_year_range(start_year: int, end_year: int) -> set[str]:
    """Return title strings for Barks titles whose submitted_year is in range."""
    return {
        info.get_title_str()
        for info in BARKS_TITLE_INFO
        if info.is_barks_title and start_year <= info.submitted_year <= end_year
    }


def _collect_title_texts(engine: SearchEngine, allowed_titles: set[str]) -> dict[str, str]:
    """Group raw speech text by title, keeping only allowed titles.

    Each title's concatenated text becomes one TF-IDF document.
    """
    texts: dict[str, list[str]] = defaultdict(list)
    for fields in engine.iter_all_stored_fields():
        title = fields.get("title", "")
        if title in allowed_titles:
            content = fields.get("content_raw", "")
            if content:
                texts[title].append(content)

    return {title: " ".join(parts) for title, parts in texts.items()}


def _compute_tfidf(title_texts: dict[str, str]) -> list[tuple[str, float]]:
    """Compute mean TF-IDF scores across all title documents.

    Returns a list of (word, score) sorted descending by score.
    """
    documents = list(title_texts.values())
    # Token pattern: match normal words plus apostrophe-prefixed contractions like 'em, 'twas, 'til
    vectorizer = TfidfVectorizer(
        stop_words="english",
        min_df=2,
        max_df=0.85,
        token_pattern=r"(?u)(?:'\w+|\b\w\w+\b)",  # noqa: S106
    )
    tfidf_matrix = vectorizer.fit_transform(documents)
    feature_names = vectorizer.get_feature_names_out()

    # Mean TF-IDF across all documents for each word
    mean_scores = tfidf_matrix.mean(axis=0).A1

    word_scores = list(zip(feature_names, mean_scores, strict=True))
    word_scores.sort(key=lambda x: x[1], reverse=True)
    return [(word, float(score)) for word, score in word_scores]


def _generate_word_cloud(
    word_scores: list[tuple[str, float]], output_path: Path, title: str = ""
) -> None:
    """Render a word cloud from TF-IDF scores and save as PNG."""
    freq = dict(word_scores[:WORDCLOUD_MAX_WORDS])
    wc = WordCloud(
        width=WORDCLOUD_WIDTH,
        height=WORDCLOUD_HEIGHT,
        max_words=WORDCLOUD_MAX_WORDS,
        background_color=WORDCLOUD_BG_COLOR,
    ).generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(WORDCLOUD_WIDTH / FIG_DPI, WORDCLOUD_HEIGHT / FIG_DPI))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    if title:
        ax.text(
            0.99,
            0.002,
            title,
            transform=ax.transAxes,
            fontsize=12,
            fontweight="bold",
            fontstyle="italic",
            color="red",
            ha="right",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "none"},
        )
    fig.tight_layout(pad=0)
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Wrote {output_path}")


def _write_ranked_words(
    word_scores: list[tuple[str, float]], output_path: Path, top_n: int = 200
) -> None:
    """Write a ranked word list with TF-IDF scores to a text file."""
    lines = [f"{'Rank':<6} {'Word':<30} {'TF-IDF Score':<12}"]
    lines.append("-" * 50)
    for rank, (word, score) in enumerate(word_scores[:top_n], start=1):
        lines.append(f"{rank:<6} {word:<30} {score:.6f}")
    output_path.write_text("\n".join(lines) + "\n")
    print(f"  Wrote {output_path}")


# -- CLI entry point ---------------------------------------------------------


def main(
    indexes_dir: Annotated[
        Path,
        typer.Option(help="Path to the Whoosh index directory."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory to write output files (created if absent)."),
    ],
    start_year: Annotated[
        int,
        typer.Option(help="First submission year to include."),
    ] = 1942,
    end_year: Annotated[
        int,
        typer.Option(help="Last submission year to include."),
    ] = 1966,
) -> None:
    """Generate a TF-IDF word cloud from Barks comic speech bubble text."""
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Year range: {start_year}-{end_year}")

    # 1. Filter titles by year range
    allowed_titles = _get_titles_in_year_range(start_year, end_year)
    print(f"Barks titles in range: {len(allowed_titles)}")

    # 2. Collect speech text per title from the Whoosh index
    engine = SearchEngine(indexes_dir)
    title_texts = _collect_title_texts(engine, allowed_titles)
    print(f"Titles with indexed text: {len(title_texts)}")

    if not title_texts:
        print("No text found - nothing to generate.")
        raise typer.Exit(code=1)

    # Diagnostic: total words and per-title stats
    word_counts = {title: len(text.split()) for title, text in title_texts.items()}
    total_words = sum(word_counts.values())
    avg_words = total_words / len(word_counts)
    min_title = min(word_counts, key=word_counts.get)  # type: ignore[arg-type]
    max_title = max(word_counts, key=word_counts.get)  # type: ignore[arg-type]
    print(f"Total words: {total_words:,}")
    print(f"Avg words/title: {avg_words:,.0f}")
    print(f"Min: {word_counts[min_title]:,} words ({min_title})")
    print(f"Max: {word_counts[max_title]:,} words ({max_title})")

    # 3. Compute TF-IDF
    word_scores = _compute_tfidf(title_texts)
    print(f"Unique terms after TF-IDF: {len(word_scores)}")

    # 4. Generate outputs
    year_suffix = f"{start_year}-{end_year % 100:02d}"
    _generate_word_cloud(
        word_scores,
        output_dir / f"tfidf_wordcloud_{year_suffix}.png",
        title=f"Carl Barks TF-IDF Word Cloud ({start_year}\u2013{end_year})",
    )
    _write_ranked_words(word_scores, output_dir / f"tfidf_ranked_words_{year_suffix}.txt")

    print("Done.")


if __name__ == "__main__":
    typer.run(main)
