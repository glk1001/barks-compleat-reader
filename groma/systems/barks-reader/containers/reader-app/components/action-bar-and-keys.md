---
type: C4 Component
title: Action bar, popups and keyboard navigation
status: stable
groma:
  id: action-bar-and-keys
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/action_bar.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/action_bar_helpers.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/reader_keyboard_nav.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/popup_widgets.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/about_box.py
      symbol: show_about_box
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/alt_escape_capture_popup.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/touch_keyboard.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/ui_helpers.py
  group: ui
---
