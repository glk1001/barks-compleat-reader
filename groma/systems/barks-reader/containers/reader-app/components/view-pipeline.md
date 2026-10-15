---
type: C4 Component
title: View pipeline
status: stable
groma:
  id: view-pipeline
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/view_pipeline.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/view_request.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/view_snapshot.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_colors.py
  group: core
---
