---
type: C4 Component
title: Settings
status: stable
groma:
  id: settings
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_settings.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/settings_notifier.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/reader_settings_buildable.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/settings_fix.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/settings_keyboard_nav.py
  group: core
---
