"""Tests for the `barks_reader.ui.view_states` re-export shim.

Node-text and article lookups previously lived in this module; they moved to
`barks_reader.core.navigation` (and are tested via `NavigationModel` destinations).
This file now only guards the back-compat re-export.
"""

from __future__ import annotations

from barks_reader.core.navigation.view_states import ViewStates as CoreViewStates
from barks_reader.ui.view_states import ViewStates as UiViewStates


def test_view_states_reexport_identity() -> None:
    """`ui.view_states.ViewStates` must be the same enum object as the core one."""
    assert UiViewStates is CoreViewStates
