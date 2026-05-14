from pathlib import Path

import cv2 as cv  # ty: ignore[unresolved-import]


def get_bw_image_from_alpha(rgba_file: Path) -> cv.typing.MatLike:
    return cv.imread(str(rgba_file), cv.IMREAD_GRAYSCALE)
