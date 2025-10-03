# ruff: noqa: ERA001

import json
from dataclasses import dataclass
from pathlib import Path

PANEL_BOUNDS_WORK_FILE_SUFFIX = "_panel_bounds.txt"


@dataclass
class BoundingBox:
    x_min: int = -1
    y_min: int = -1
    x_max: int = -1
    y_max: int = -1

    def get_box(self) -> tuple[int, int, int, int]:
        return self.x_min, self.y_min, self.x_max, self.y_max

    def get_width(self) -> int:
        return (self.x_max - self.x_min) + 1

    def get_height(self) -> int:
        return (self.y_max - self.y_min) + 1


def get_panels_bounding_box_from_file(panels_segments_file: Path) -> BoundingBox:
    with panels_segments_file.open() as f:
        segment_info = json.load(f)

    x_min, y_min, x_max, y_max = segment_info["overall_bounds"]

    # logger.debug(
    #     f'Using panels segment info file "{get_abbrev_path(panels_segments_file)}".'
    #     f" Overall bounding box: {x_min}, {y_min}, {x_max}, {y_max}."
    # )

    return BoundingBox(x_min, y_min, x_max, y_max)


# TODO: Put this in examples show bounds
# def __dump_panels_bounding_box(
#     self, page_filename: str, x_min: int, y_min: int, x_max: int, y_max: int
# ):
#     bounds_filename = os.path.join(
#         self.__work_dir,
#         os.path.splitext(os.path.basename(page_filename))[0] + PANEL_BOUNDS_WORK_FILE_SUFFIX,
#     )
#     logger.debug(f'Saving panel bounds to work file "{bounds_filename}".')
#     with open(bounds_filename, "w") as f:
#         f.write(f"{x_min}, {y_min}, {x_max}, {y_max}\n")
#
#     # Draw the panel bounds on page image.
#     page_image = open_image_for_reading(page_filename)
#     draw = ImageDraw.Draw(page_image)
#     draw.line([(x_min, y_min), (x_max, y_min)], width=3, fill=(256, 0, 0))
#     draw.line([(x_max, y_min), (x_max, y_max)], width=3, fill=(256, 0, 0))
#     draw.line([(x_max, y_max), (x_min, y_max)], width=3, fill=(256, 0, 0))
#     draw.line([(x_min, y_max), (x_min, y_min)], width=3, fill=(256, 0, 0))
#
#     marked_image_filename = os.path.join(
#         self.__work_dir,
#         os.path.splitext(os.path.basename(page_filename))[0] + "-panel-bounds-marked.jpg",
#     )
#     logger.debug(f'Saving panel bounds image to work file "{marked_image_filename}".')
#     page_image = page_image.convert("RGB")
#     page_image.save(marked_image_filename, optimize=True, compress_level=5)
