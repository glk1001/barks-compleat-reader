---
type: C4 Component
title: CLI setup, logging, timing and the CPI table
status: stable
groma:
  id: cli-and-tools
  parent: comic-utils
  code:
    - scanner: python
      file: src/comic-utils/src/comic_utils/cli_setup.py
      symbol: init_logging
    - scanner: python
      file: src/comic-utils/src/comic_utils/common_typer_options.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/loguru_setup.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/timing.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/sys_utils.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/screen_utils.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/cpi_calculator.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/cpi_table.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/update_cpi_table.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/__init__.py
---
