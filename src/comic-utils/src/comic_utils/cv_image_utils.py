from pathlib import Path

import cv2 as cv  # ty: ignore[unresolved-import]

# A valid Barks page is BW with a (near-)white background and black ink.  An all-
# black PNG (alpha-extraction gone wrong on an upstream restoration step) has
# max == 0 and silently corrupts every downstream OCR/annotation step, so reject
# anything whose brightest pixel is below this threshold.
_MIN_VALID_PAGE_MAX_BRIGHTNESS = 50


def get_bw_image_from_alpha(rgba_file: Path) -> cv.typing.MatLike:
    return cv.imread(str(rgba_file), cv.IMREAD_GRAYSCALE)


def validate_page_bw_image(bw_image: cv.typing.MatLike | None, png_file: Path) -> None:
    """Raise ``RuntimeError`` if ``bw_image`` is missing, empty, or all-black.

    Args:
        bw_image: Grayscale ``cv2`` MatLike returned by ``get_bw_image_from_alpha``
            (or equivalent). ``None`` is treated as a decode failure.
        png_file: Source path, included in the error message so the caller can
            locate the bad file.

    Raises:
        RuntimeError: ``bw_image`` is ``None``, has zero size, or is so dark
            (``max < 50``) that it cannot be a real Barks restored page.

    """
    if bw_image is None or getattr(bw_image, "size", 0) == 0:
        msg = f'Could not decode page PNG: "{png_file}".'
        raise RuntimeError(msg)
    max_brightness = int(bw_image.max())
    if max_brightness < _MIN_VALID_PAGE_MAX_BRIGHTNESS:
        msg = (
            f"Invalid page PNG (max brightness={max_brightness}, expected ~255 for a "
            f'BW page): "{png_file}". The PNG may be all-black — check the upstream '
            f"alpha-extraction/restoration step."
        )
        raise RuntimeError(msg)
