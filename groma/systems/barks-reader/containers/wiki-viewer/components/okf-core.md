---
type: C4 Component
title: Bundle model, rendering, search and session
status: stable
groma:
  id: okf-core
  parent: wiki-viewer
  code:
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/render.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/search.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/session.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/backgrounds.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/actions.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/theme.py
      symbol: ViewerThemeSpec
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/top_bar.py
      symbol: TopBarSpec
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/log_markers.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/__init__.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/__init__.py
    - scanner: python
      file: src/okf-reader/src/okf_reader/core/bundle.py
---
