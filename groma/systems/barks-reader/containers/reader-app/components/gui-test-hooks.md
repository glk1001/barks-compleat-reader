---
type: C4 Component
title: GUI test hooks
status: stable
groma:
  id: gui-test-hooks
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/log_markers.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/tap_targets.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/memory_census.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/tap_targets.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/memory_census.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/frame_capture.py
  group: core
---
