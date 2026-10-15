---
type: C4 Component
title: App shell and screen manager
status: stable
groma:
  id: app-shell
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/barks_reader_app.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/app_initializer.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/reader_screens.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/screen_bundle.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/main_screen.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/main_screen_components.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/main_screen_nav.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/__init__.py
  group: ui
---
