---
type: C4 Component
title: Comic loading
status: stable
groma:
  id: comic-loading
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/comic_reader_manager.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/comic_book_loader.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/comic_book_loader_platform_settings.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/comic_book_page_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/comic_book_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/archive_page_image_source.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/page_image_source.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/page_info_ports.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/page_info_adapters.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/fantagraphics_volumes.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/collection_page_groups.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/display_unit.py
      symbol: DisplayUnit
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/page_placement.py
  group: core
---
