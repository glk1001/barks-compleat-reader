---
type: C4 Component
title: Boot and configuration
status: stable
groma:
  id: boot-and-config
  parent: reader-app
  code:
    - scanner: python
      file: main.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/config_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/minimal_config_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/platform_info.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/screen_metrics.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_setup.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/system_file_paths.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/linux_desktop_entry.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/reader_utils.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/__init__.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/__init__.py
  group: core
---
