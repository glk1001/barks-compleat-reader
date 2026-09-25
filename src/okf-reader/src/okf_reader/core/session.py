"""Session persistence: the page and scroll offset the reader was left at.

Kivy-free so the policy is testable — the UI only decides *when* to load and
save. State lives in a caller-chosen JSON file; everything here is best-effort
and tolerant (the SPEC §9 spirit): a missing, corrupt, or stale state file
yields None rather than an error, and a failed save is silently dropped —
losing a resume point must never break reading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class SessionState:
    """Where the reader was left: a page inside the bundle and its scroll offset."""

    page: Path  # absolute, verified to be a concept document inside the bundle
    scroll_y: float = 1.0  # the ScrollView convention: 1.0 == top


def load_session_state(state_path: Path, bundle: Path) -> SessionState | None:
    """Read the saved session, or None if it is missing, corrupt, or stale.

    Stale means the recorded page no longer resolves to a ``.md`` document
    inside ``bundle`` — the wiki may have been regenerated since the last run.
    An out-of-range or malformed scroll offset degrades to the top of the page
    rather than invalidating the whole state.
    """
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    rel = data.get("page")
    if not isinstance(rel, str):
        return None
    page = (bundle / rel).resolve()
    try:
        page.relative_to(bundle.resolve())
    except ValueError:
        return None  # bounds check, as in resolve_link: never escape the bundle
    if page.suffix != ".md" or not page.is_file():
        return None
    scroll_y = data.get("scroll_y")
    if not isinstance(scroll_y, int | float) or not 0.0 <= scroll_y <= 1.0:
        scroll_y = 1.0
    return SessionState(page, float(scroll_y))


def resolve_start_page(
    bundle: Path, start_page: Path | None, state_path: Path | None
) -> tuple[Path, float]:
    """Choose the page a viewer opens on, and the scroll offset to open it at.

    A caller-chosen page wins, at the top. Otherwise the saved session's page
    and offset, when a state file says where and it still resolves. Otherwise
    the bundle's home page: a viewer must always open onto something, and a
    fresh profile (no session yet) or a regenerated wiki (stale session) would
    otherwise show an empty pane.
    """
    if start_page is not None:
        return start_page, 1.0
    if state_path is not None:
        saved = load_session_state(state_path, bundle)
        if saved is not None:
            return saved.page, saved.scroll_y
    return bundle / "index.md", 1.0


def save_session_state(state_path: Path, bundle: Path, page: Path, scroll_y: float) -> None:
    """Write the session file — best effort, failures are not the reader's problem."""
    try:
        rel = page.resolve().relative_to(bundle.resolve())
    except ValueError:
        return  # a page outside the bundle is not restorable state
    payload = {"page": rel.as_posix(), "scroll_y": round(min(max(scroll_y, 0.0), 1.0), 4)}
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        return
