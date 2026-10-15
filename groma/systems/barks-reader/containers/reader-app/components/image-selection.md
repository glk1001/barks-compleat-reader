---
type: C4 Component
title: Image selection and panel loading
status: stable
groma:
  id: image-selection
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/image_selector.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/image_pipeline.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/panel_image_loader.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_file_paths.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_file_paths_resolver.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/special_overrides_handler.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/panel_texture_loader.py
  group: core
---
