"""Unit tests for session persistence (``okf_reader.core.session``).

These pin the tolerant load/save contract: a missing, corrupt, or stale state
file yields None; saves are best-effort and bundle-bounded.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from okf_reader.core.session import SessionState, load_session_state, save_session_state

if TYPE_CHECKING:
    from pathlib import Path


def _make_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "concept").mkdir(parents=True)
    (bundle / "concept" / "a.md").write_text("---\ntype: x\n---\nA", encoding="utf-8")
    return bundle


class TestRoundTrip:
    def test_save_then_load(self, tmp_path: Path) -> None:
        """A saved session restores the same page and scroll offset."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "state" / "session.json"  # parent dirs are created
        save_session_state(state_path, bundle, bundle / "concept" / "a.md", 0.25)
        assert load_session_state(state_path, bundle) == SessionState(
            (bundle / "concept" / "a.md").resolve(), 0.25
        )

    def test_page_stored_bundle_relative(self, tmp_path: Path) -> None:
        """The file records a bundle-relative POSIX path, so the bundle can move."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        save_session_state(state_path, bundle, bundle / "concept" / "a.md", 1.0)
        data = json.loads(state_path.read_text(encoding="utf-8"))
        assert data["page"] == "concept/a.md"

    def test_save_clamps_scroll(self, tmp_path: Path) -> None:
        """An out-of-range scroll offset (mid-overscroll) is clamped, not stored raw."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        save_session_state(state_path, bundle, bundle / "concept" / "a.md", 1.7)
        loaded = load_session_state(state_path, bundle)
        assert loaded is not None
        assert loaded.scroll_y == 1.0

    def test_save_outside_bundle_is_dropped(self, tmp_path: Path) -> None:
        """A page outside the bundle is not restorable state — nothing is written."""
        bundle = _make_bundle(tmp_path)
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x", encoding="utf-8")
        state_path = tmp_path / "session.json"
        save_session_state(state_path, bundle, outside, 1.0)
        assert not state_path.exists()


class TestLoadTolerance:
    def test_missing_file(self, tmp_path: Path) -> None:
        """No state file yet is a normal first run, not an error."""
        assert load_session_state(tmp_path / "nowhere.json", _make_bundle(tmp_path)) is None

    def test_corrupt_json(self, tmp_path: Path) -> None:
        """A corrupt state file degrades to no session."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        state_path.write_text("{not json", encoding="utf-8")
        assert load_session_state(state_path, bundle) is None

    def test_non_mapping_json(self, tmp_path: Path) -> None:
        """Valid JSON that isn't an object degrades to no session."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        state_path.write_text('["concept/a.md"]', encoding="utf-8")
        assert load_session_state(state_path, bundle) is None

    def test_stale_page(self, tmp_path: Path) -> None:
        """A recorded page deleted since (wiki regenerated) invalidates the session."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        state_path.write_text(json.dumps({"page": "concept/gone.md"}), encoding="utf-8")
        assert load_session_state(state_path, bundle) is None

    def test_page_escaping_bundle_rejected(self, tmp_path: Path) -> None:
        """A crafted traversal path never resolves outside the bundle."""
        bundle = _make_bundle(tmp_path)
        outside = tmp_path / "evil.md"
        outside.write_text("x", encoding="utf-8")
        state_path = tmp_path / "session.json"
        state_path.write_text(json.dumps({"page": "../evil.md"}), encoding="utf-8")
        assert load_session_state(state_path, bundle) is None

    def test_bad_scroll_degrades_to_top(self, tmp_path: Path) -> None:
        """A malformed or out-of-range scroll keeps the page, opened at the top."""
        bundle = _make_bundle(tmp_path)
        state_path = tmp_path / "session.json"
        for bad in ("nope", -0.5, 2.0, None):
            state_path.write_text(
                json.dumps({"page": "concept/a.md", "scroll_y": bad}), encoding="utf-8"
            )
            loaded = load_session_state(state_path, bundle)
            assert loaded is not None
            assert loaded.scroll_y == 1.0
