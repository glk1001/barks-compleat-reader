"""Re-export shim for `ViewStates`.

`ViewStates` now lives in `barks_reader.core.navigation.view_states`. This module
exists only so existing imports (`from barks_reader.ui.view_states import ViewStates`)
keep working while call sites migrate to the core path.
"""

from __future__ import annotations

from barks_reader.core.navigation.view_states import ViewStates

__all__ = ["ViewStates"]
