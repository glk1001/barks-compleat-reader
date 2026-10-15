---
type: C4 Component
title: Window management
status: stable
groma:
  id: window-management
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/platform_window_utils.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/platform_window_win32.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/app_window_geometry.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/main_screen_window.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/x11_wm_class.py
  group: ui
---
