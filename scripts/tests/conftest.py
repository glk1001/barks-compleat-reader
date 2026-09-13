"""Make the scripts directory importable, so its modules can be unit-tested.

The scripts are standalone files rather than a package - they are run directly,
not imported by the app - so there is no installed module path to import them by.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
