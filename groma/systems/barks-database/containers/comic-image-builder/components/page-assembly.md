---
type: C4 Component
title: Page assembly
status: stable
groma:
  id: page-assembly
  parent: comic-image-builder
  code:
    - scanner: python
      file: src/barks-build-comic-images/src/barks_build_comic_images/build_comic_images.py
    - scanner: python
      file: src/barks-build-comic-images/src/barks_build_comic_images/image_io.py
      symbol: open_image_for_reading
    - scanner: python
      file: src/barks-build-comic-images/src/barks_build_comic_images/consts.py
    - scanner: python
      file: src/barks-build-comic-images/src/barks_build_comic_images/__init__.py
---
