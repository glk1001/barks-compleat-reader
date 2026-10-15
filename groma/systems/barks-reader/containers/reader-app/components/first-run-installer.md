---
type: C4 Component
title: First-run installer
status: stable
groma:
  id: first-run-installer
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/first_run_installer.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/first_run_installer_show_message.py
  group: core
---
