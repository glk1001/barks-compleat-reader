---
type: C4 Component
title: Reading progress and history
status: stable
groma:
  id: reading-progress
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/last_read_page_tracker.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/saved_page_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reading_history.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/json_settings_manager.py
  group: core
---
