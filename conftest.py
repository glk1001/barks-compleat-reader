"""Session-wide pytest configuration.

Registers the Hypothesis settings profiles used across the workspace. Pick one
with the ``HYPOTHESIS_PROFILE`` env var (default ``dev``); CI sets ``ci`` (see
``.github/workflows/ci.yml``).
"""

# cspell:ignore softgl numprocesses xdist

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from hypothesis import settings

if TYPE_CHECKING:
    import pytest

# Where scripts/macos/softgl.c leaves its own path once it has taken itself out of
# DYLD_INSERT_LIBRARIES, so that nothing a test starts inherits it.
_SOFT_GL_LIBRARY = "BARKS_SOFT_GL_LIBRARY"
_INSERTED = "DYLD_INSERT_LIBRARIES"

# Local default: more examples than the stock 100 — cheap for the pure-logic
# targets property tests are aimed at, and finds more edge cases.
settings.register_profile("dev", max_examples=200)

# CI: reproducible and timing-tolerant.
#  - derandomize: same inputs every run, so a property test can't pass on one
#    CI run and fail on the next (no flaky, un-reproducible failures).
#  - deadline=None: the runners' variable timing must not fail a test for being
#    slow; correctness is what we assert here, not latency.
#  - print_blob: emit a @reproduce_failure blob so any failure is replayable.
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    derandomize=True,
    print_blob=True,
)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))


def pytest_configure(config: pytest.Config) -> None:
    """Hand the software-OpenGL library on to pytest's workers, on macOS.

    Under ``with-soft-gl.sh`` the library takes itself out of the environment once
    loaded, so a program a test starts never inherits it (on Apple silicon dyld kills
    one of Apple's arm64e programs asked to load it). Workers (``-n``) are Python and
    need it to open a window; this process runs no tests when it has workers, so it
    may put the library back for them, and each worker's copy takes itself out again.
    """
    library = os.environ.get(_SOFT_GL_LIBRARY)
    workers = getattr(config.option, "numprocesses", None)
    is_worker = hasattr(config, "workerinput")  # xdist's mark: a worker runs tests
    if sys.platform != "darwin" or not library or not workers or is_worker:
        return
    inserted = os.environ.get(_INSERTED)
    os.environ[_INSERTED] = f"{library}:{inserted}" if inserted else library
