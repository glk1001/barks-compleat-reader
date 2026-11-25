"""What the navigation coordinator asks of the main screen's widgets. Kivy-free.

Each port lists only the members the coordinator uses. The production
implementations are the widgets and managers in `ui`: `ViewRenderer`
(`TitleRenderer`), `BottomTitleViewScreen` (`TitleViewPort`), `TreeViewManager`
(`TreePort`), `ButtonTreeViewNode` (`GroupNodePort`) and `ScreenSwitchers`
(`ScreenSwitcherPort`). The user error handler's port is
`core.user_error_types.UserErrorHandlerPort`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from comic_utils.comic_consts import PanelPath

    from barks_reader.core.goto_page import GotoPageOffer
    from barks_reader.core.navigation.view_states import ViewStates

# A node of the tree, as the tree's own widgets know it: the coordinator hands nodes
# from one tree call to the next and looks inside none but a `GroupNodePort`.
type TreeNode = Any


@dataclass(frozen=True, slots=True)
class TitleViewChoices:
    """What the reader has chosen on the title view, as it stands now."""

    goto_page_active: bool
    goto_page_num: str
    tagged_pages: tuple[str, ...]
    use_overrides_active: bool


class TitleRenderer(Protocol):
    """Render a view state, or the view of a title."""

    def render_state(self, view_state: ViewStates, *, preserve_top_view: bool = False) -> None:
        """Render `view_state`, a state that carries nothing with it."""
        ...

    def render_title(
        self,
        fanta_info: FantaComicBookInfo,
        *,
        title_image_file: PanelPath | None = None,
        preserve_top_view: bool = False,
    ) -> None:
        """Render the title view for `fanta_info`."""
        ...


class TitleViewPort(Protocol):
    """The title view's goto-page and use-overrides rows."""

    def show_goto_page(self, offer: GotoPageOffer) -> None:
        """Show `offer` on the goto-page row."""
        ...

    def set_overrides_state(self, description: str = "", active: bool = True) -> None:
        """Set the use-overrides row for the title in view."""
        ...

    def choices(self) -> TitleViewChoices:
        """Return what the two rows hold now."""
        ...


class GroupNodePort(Protocol):
    """A tree node that title rows sit under, made on its first opening."""

    nodes: list[Any]

    def ensure_populated(self) -> None:
        """Make the node's rows now if they have not been made yet."""
        ...


class TreePort(Protocol):
    """The tree: closing it, opening a node, and going to one."""

    def deselect_and_close_open_nodes(self) -> None:
        """Close every open node and clear the selection."""
        ...

    def open_node_and_parent_nodes(self, node: TreeNode) -> None:
        """Open `node` and every node above it."""
        ...

    def goto_node(self, node: TreeNode, *, scroll_to: bool = False) -> None:
        """Select `node`, scrolling to it if asked."""
        ...


class SwitchToDocumentReader(Protocol):
    """Open a folder of page images in the document reader.

    With `resume` it opens at its last page; with `single_page` it shows one page at a
    time on the two-page spread as well.
    """

    def __call__(
        self, doc_dir: Path, title: str, *, resume: bool = False, single_page: bool = False
    ) -> None:
        """Open the folder `doc_dir` under `title`."""
        ...


class ScreenSwitcherPort(Protocol):
    """The full-window screens the coordinator opens over the main screen."""

    @property
    def switch_to_document_reader(self) -> SwitchToDocumentReader:
        """Open a folder of page images."""
        ...

    @property
    def switch_to_wiki_reader(self) -> Callable[[Path, Path | None], None]:
        """Open the wiki bundle, at a page of it or where it was left."""
        ...

    @property
    def switch_to_corpus_stats(self) -> Callable[[], None]:
        """Open "By the Numbers"."""
        ...
