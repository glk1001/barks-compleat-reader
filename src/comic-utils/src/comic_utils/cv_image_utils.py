import cv2 as cv
import numpy as np


def get_bw_image_from_alpha(rgba_file: str) -> cv.typing.MatLike:
    black_mask = cv.imread(rgba_file, -1)

    scale = 4
    black_mask = cv.resize(
        black_mask,
        (0, 0),
        fx=1.0 / scale,
        fy=1.0 / scale,
        interpolation=cv.INTER_AREA,
    )

    _, _, _, binary = cv.split(black_mask)
    binary = np.uint8(255 - binary)

    return binary  # noqa: RET504
