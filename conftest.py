"""Session-wide pytest configuration.

Registers the Hypothesis settings profiles used across the workspace. Pick one
with the ``HYPOTHESIS_PROFILE`` env var (default ``dev``); CI sets ``ci`` (see
``.github/workflows/ci.yml``).
"""

from __future__ import annotations

import os

from hypothesis import settings

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
