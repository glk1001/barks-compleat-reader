---
type: C4 Component
title: OCR speech data
status: stable
groma:
  id: speech-data
  parent: story-catalogue
  code:
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/ocr_file_paths.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/ocr_json_files.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/speech_groupers.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/speech_markup.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/speech_speakers.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/barks_words.py
---
