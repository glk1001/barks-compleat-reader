"""Pure panel-bounding-box geometry.

Given source-page box sizes and target page parameters, compute the target
dimensions and positions for a destination layout. This module is intentionally
free of I/O, logging, and page-type semantics — it operates on primitive ints
and tuples so the arithmetic can be reasoned about and tested in isolation.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """An axis-aligned rectangle with inclusive min/max pixel coordinates."""

    x_min: int = -1
    y_min: int = -1
    x_max: int = -1
    y_max: int = -1

    def get_box(self) -> tuple[int, int, int, int]:
        """Return the (x_min, y_min, x_max, y_max) tuple."""
        return self.x_min, self.y_min, self.x_max, self.y_max

    def get_width(self) -> int:
        """Return the inclusive pixel width."""
        return (self.x_max - self.x_min) + 1

    def get_height(self) -> int:
        """Return the inclusive pixel height."""
        return (self.y_max - self.y_min) + 1


@dataclass(frozen=True, slots=True)
class BoxSizeStats:
    """Min/max/average width and height over a set of boxes."""

    min_width: int
    max_width: int
    min_height: int
    max_height: int
    avg_width: int
    avg_height: int


def scale_height(target_width: int, source_width: int, source_height: int) -> int:
    """Scale a box height proportionally to a new width.

    Args:
        target_width: The new width the box will be scaled to.
        source_width: The original box width.
        source_height: The original box height.

    Returns:
        The rounded height that preserves the source aspect ratio at ``target_width``.

    """
    return round((source_height * target_width) / source_width)


def compute_box_size_stats(
    sizes: list[tuple[int, int]],
    height_similarity_margin: int,
) -> BoxSizeStats:
    """Compute min/max/average width and height across boxes.

    The average only includes boxes whose height is within
    ``height_similarity_margin`` of the maximum height — short outliers (e.g.
    splash-panel pages with unusually small content areas) do not skew the mean.

    Args:
        sizes: Non-empty list of (width, height) pairs in pixels.
        height_similarity_margin: Pixels below ``max_height`` that a box's height
            may fall and still count toward the average.

    Returns:
        Per-dimension min/max/average statistics.

    Raises:
        ValueError: If ``sizes`` is empty or no boxes qualify for the average.

    """
    if not sizes:
        msg = "Cannot compute box stats from an empty list of sizes."
        raise ValueError(msg)

    widths = [w for w, _ in sizes]
    heights = [h for _, h in sizes]

    max_h = max(heights)
    min_h = min(heights)
    max_w = max(widths)
    min_w = min(widths)

    avg_threshold = max_h - height_similarity_margin
    avg_pairs = [(w, h) for w, h in sizes if h >= avg_threshold]
    if not avg_pairs:
        msg = "No boxes qualify for the average — cannot compute average dimensions."
        raise ValueError(msg)

    avg_w = round(sum(w for w, _ in avg_pairs) / len(avg_pairs))
    avg_h = round(sum(h for _, h in avg_pairs) / len(avg_pairs))

    return BoxSizeStats(min_w, max_w, min_h, max_h, avg_w, avg_h)


def compute_required_panels_bbox_size(
    avg_box_width: int,
    avg_box_height: int,
    target_page_width: int,
    target_x_margin: int,
) -> tuple[int, int]:
    """Compute the required panels-bbox size on the target page.

    Width is the target page width minus symmetric horizontal margins. Height
    scales proportionally from the average source box so the target aspect
    ratio matches the average source aspect ratio.

    Args:
        avg_box_width: Average source panels-bbox width.
        avg_box_height: Average source panels-bbox height.
        target_page_width: Width of the destination page in pixels.
        target_x_margin: Left/right margin in pixels.

    Returns:
        ``(required_width, required_height)`` in pixels.

    """
    required_width = target_page_width - (2 * target_x_margin)
    required_height = scale_height(required_width, avg_box_width, avg_box_height)
    return required_width, required_height


def compute_page_num_y_bottom(
    target_page_height: int,
    required_panels_height: int,
    page_num_height: int,
) -> int:
    """Return the y-bottom pixel for the page-number text.

    The page number is centred vertically within the top half of the top margin
    (the empty strip above the centred panels bbox).
    """
    y_centre = round(0.5 * (0.5 * (target_page_height - required_panels_height)))
    return int(y_centre - (page_num_height / 2))


def centered_bbox(
    target_page_width: int,
    target_page_height: int,
    bbox_width: int,
    bbox_height: int,
    x_margin: int,
) -> BoundingBox:
    """Build a bounding box placed with symmetric x margins and centred vertically.

    Args:
        target_page_width: Destination page width in pixels. Used only to validate
            that ``bbox_width + 2*x_margin <= target_page_width``.
        target_page_height: Destination page height in pixels.
        bbox_width: Width of the box to place.
        bbox_height: Height of the box to place.
        x_margin: Left/right margin in pixels.

    Returns:
        A :class:`BoundingBox` with inclusive min/max coordinates.

    """
    assert bbox_width + (2 * x_margin) <= target_page_width
    x_min = x_margin
    y_min = int(0.5 * (target_page_height - bbox_height))
    x_max = x_min + (bbox_width - 1)
    y_max = y_min + (bbox_height - 1)
    return BoundingBox(x_min, y_min, x_max, y_max)
