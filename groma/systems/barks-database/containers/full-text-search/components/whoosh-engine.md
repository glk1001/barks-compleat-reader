---
type: C4 Component
title: Whoosh engine
status: stable
groma:
  id: whoosh-engine
  parent: full-text-search
  code:
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/whoosh_search_engine.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/whoosh_barks_terms.py
    - scanner: python
      file: src/barks-fantagraphics/src/barks_fantagraphics/whoosh_punct_tokenizer.py
---
