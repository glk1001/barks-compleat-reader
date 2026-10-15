---
type: C4 Component
title: Navigation model
status: stable
groma:
  id: navigation-model
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/navigation/navigation_model.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/navigation/destinations.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/navigation/tree_spec.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/navigation/view_states.py
      symbol: ViewStates
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/filtered_title_lists.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/playlists.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_tree_view_utils.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/navigation/__init__.py
  group: core
---
