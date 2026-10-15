---
type: C4 Component
title: Errors and crash reporting
status: stable
groma:
  id: errors
  parent: reader-app
  code:
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/user_error_types.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/core/user_error_messages.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/user_error_handler.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/error_handling.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/kivy_standalone_error_popup.py
    - scanner: python
      file: src/barks-reader/src/barks_reader/ui/kivy_standalone_show_message.py
  group: core
---
