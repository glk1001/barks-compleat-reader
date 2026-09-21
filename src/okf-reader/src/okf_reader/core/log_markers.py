"""The viewer's trace lines, written in one place.

``okf_reader.ui.trace`` logs these through Kivy's logger and a host's GUI tests
wait on them (the Barks Reader routes Kivy's log into its own), so the text is
part of the viewer's contract. Templates use named ``str.format`` fields; the
host's ``barks_reader.core.log_markers.pattern`` turns one into a regex. Kivy-free,
so a test can import it without the viewer.
"""

from __future__ import annotations

from typing import Final

PREFIX: Final = "OKFViewer"

PAGE_SHOWN: Final = f"{PREFIX}: Showed page '{{page}}' (history depth {{depth}})."
FOCUS_REGION: Final = f"{PREFIX}: Focus region {{name}}."
FOCUS_RING: Final = f"{PREFIX}: Focus ring on {{widget}}."
TREE_FOCUS: Final = f"{PREFIX}: Sidebar focus on tree node '{{node}}'."
BACK_TO: Final = f"{PREFIX}: Back to '{{page}}'."
BACK_EXIT: Final = f"{PREFIX}: Back at history root; exiting."
TREE_SETTLED: Final = f"{PREFIX}: Tree settled on '{{node}}' after {{frames}} frames."
PAGE_ACTION: Final = f"{PREFIX}: Page action '{{label}}'."
