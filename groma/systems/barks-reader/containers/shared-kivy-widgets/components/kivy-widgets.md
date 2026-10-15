---
type: C4 Component
title: Scroll pane, page viewer and Kivy patches
status: stable
groma:
  id: kivy-widgets
  parent: shared-kivy-widgets
  code:
    - scanner: python
      file: src/barks-kivy-ui/src/barks_kivy_ui/scrolling.py
    - scanner: python
      file: src/barks-kivy-ui/src/barks_kivy_ui/page_viewer.py
    - scanner: python
      file: src/barks-kivy-ui/src/barks_kivy_ui/kivy_patches.py
    - scanner: python
      file: src/barks-kivy-ui/src/barks_kivy_ui/__init__.py
---
