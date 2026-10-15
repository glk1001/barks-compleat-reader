---
type: C4 Component
title: Ports and adapters
status: stable
groma:
  id: ports-and-adapters
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/scheduler.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/cursor.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/color_source.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/snapshot_sink.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/comic_reader.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/adapters/kivy_scheduler.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/adapters/kivy_cursor.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/ports/__init__.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/adapters/__init__.py
  group: core
---
