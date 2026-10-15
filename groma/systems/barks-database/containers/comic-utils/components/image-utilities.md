---
type: C4 Component
title: Image, panel and decryption utilities
status: stable
groma:
  id: image-utilities
  parent: comic-utils
  code:
    - scanner: python
      file: src/comic-utils/src/comic_utils/comic_consts.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/cv_image_utils.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/pil_image_utils.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/decryption.py
      symbol: DecryptionError
    - scanner: python
      file: src/comic-utils/src/comic_utils/panel_bounding_box_processor.py
    - scanner: python
      file: src/comic-utils/src/comic_utils/panel_segmentation.py
---
