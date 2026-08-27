"""Library screen: step 3 of the target flow -- the playlist tree.

Arrow keys move, space toggles selection (a folder toggles every descendant
playlist at once, and the "All playlists" row at the very top -- a real,
collapsible container for everything else, not just a sibling summary --
toggles the whole library), "e" expands or collapses the highlighted folder,
enter confirms and, with at least one playlist selected, starts the sync
(step 4, the Progress screen). Coming back here after a sync (Done -> enter
-> pop_screen) re-reads sync state from disk rather than showing whatever
was true when the screen first loaded -- a track this screen doesn't reload
for stays looking unsynced until the whole app restarts, which is exactly
the bug this refresh-on-resume exists to avoid.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static, Tree
from textual.widgets.tree import TreeNode

from app.core.domain import SyncState
from app.services.library import UsbLibrary
from app.services.sync_service import (
    PlaylistTreeSyncState,
    combine_sync_states,
    playlist_tree_sync_states,
)
from app.tui.screens.progress import ProgressScreen

_MARKER = {
    SyncState.SYNCED: ("green", "synced"),
    SyncState.PARTIAL: ("yellow", "partial"),
    SyncState.NOT_SYNCED: ("red", "not synced"),
}
# Plain ASCII, not a unicode checkmark/dot: those have ambiguous terminal
# cell width depending on font, which was throwing the columns below off by
# a cell on exactly the rows that used them.
_SELECTED = "x"
_UNSELECTED = "-"
_PARTIAL_SELECTED = "~"
_STATUS_ID = "selection-status"
_MOUNT_ID = "mount-info"
_ALL_NAME = "All playlists"

# Fixed-width columns so the count and state sit in the same place on every
# row. Tree has no column model, so this is a label string padded with
# knowledge of exactly how many cells Tree's own guide lines and expand icon
# consume before the label starts at a given depth (see _prefix_width) --
# without that, rows at different nesting depths (or folder vs. leaf) drift
# out of alignment by however many cells their guides/icon take.
_NAME_WIDTH = 30
_COUNT_WIDTH = 7
_STATE_WIDTH = 10


@dataclass(frozen=True)
class _Row:
    """Whatever one tree row needs to render and toggle -- a real playlist,
    folder, or the synthetic "All playlists" row."""

    name: str
    state: SyncState
    synced: int
    total: int
    ids: tuple[int, ...]
    is_folder: bool


class LibraryScreen(Screen):
    """
    Playlist folder tree with a per-node sync state and multi-select.

    Space is bound here as a **priority** binding, which is what lets it win
    over Tree's own default space-toggles-expand binding on the focused
    widget -- space is for selecting playlists to sync per the target flow
    (docs/planning/interactive-tui.md), and expand/collapse moves to "e"
    instead so both actions stay reachable.
    """

    BINDINGS = [
        Binding("space", "toggle_selection", "Select", show=True, priority=True),
        Binding("e", "toggle_expand", "Expand/collapse", show=True),
    ]

    DEFAULT_CSS = """
    LibraryScreen #mount-info {
        text-style: dim;
        margin: 0 0 1 1;
    }
    """

    def __init__(self, library: UsbLibrary) -> None:
        """
        Args:
            library: Opened session handle to read playlists and sync state from.
        """
        super().__init__()
        self.library = library
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        yield Static(f"Mounted: {self.library.mount}", id=_MOUNT_ID)
        tree: Tree[_Row] = Tree("Playlists", id="playlist-tree")
        tree.show_root = False
        yield tree
        yield Static("", id=_STATUS_ID)
        yield Footer()

    async def on_screen_resume(self) -> None:
        """
        (Re)build the tree every time this screen becomes the active one.

        Fires on the screen's first activation as well as later resumes
        (confirmed empirically -- Textual gives no separate "first time"
        signal), so this is the one place the tree is built at all; there is
        no separate on_mount doing it too.
        """
        await self._refresh()

    async def _refresh(self) -> None:
        tree = self.query_one(Tree)
        tree.clear()
        self._selected.clear()
        # playlist_tree_sync_states reads through library.rekordbox, which
        # must stay on the app's one dedicated thread -- see
        # UsbversalApp.run_rekordbox.
        states = await self.app.run_rekordbox(playlist_tree_sync_states, self.library)

        all_row = _Row(
            name=_ALL_NAME,
            state=combine_sync_states([state.state for state in states]),
            synced=sum(state.synced for state in states),
            total=sum(state.total for state in states),
            ids=tuple(i for state in states for i in state.leaf_ids),
            is_folder=True,
        )
        all_node = tree.root.add(self._label(all_row, depth=0), data=all_row, expand=True)
        for state in states:
            self._add_node(all_node, state, depth=1)

        tree.root.expand()
        tree.cursor_line = 0
        tree.focus()
        self._update_status()

    def _add_node(self, parent: TreeNode, state: PlaylistTreeSyncState, depth: int) -> None:
        """Recursively mirror a PlaylistTreeSyncState into the Tree widget."""
        row = _Row(
            name=state.node.playlist.name,
            state=state.state,
            synced=state.synced,
            total=state.total,
            ids=state.leaf_ids,
            is_folder=state.node.playlist.is_folder,
        )
        if row.is_folder:
            node = parent.add(self._label(row, depth), data=row, expand=True)
        else:
            node = parent.add_leaf(self._label(row, depth), data=row)
        for child in state.children:
            self._add_node(node, child, depth + 1)

    def _prefix_width(self, depth: int, is_folder: bool) -> int:
        """
        Cells Tree's own guide lines and expand icon consume before a label
        at this depth -- matched empirically against Tree's rendering
        (``guide_depth`` cells per nesting level, plus the icon+space width
        for an expandable node), so the columns after the name line up
        regardless of depth or folder-vs-leaf.
        """
        tree = self.query_one(Tree)
        icon_width = cell_len(Tree.ICON_NODE_EXPANDED) if is_folder else 0
        return depth * tree.guide_depth + icon_width

    def _label(self, row: _Row, depth: int) -> Text:
        """
        Build one tree-row label with aligned count and coloured state.

        Playlist names are arbitrary user data, so the state colour is a
        ``Text`` style, not a markup tag that a ``[`` in the name could break.

        Args:
            row: Row data to render.
            depth: Nesting depth, used to pad the name around Tree guides.

        Returns:
            Label text with the state word styled red/yellow/green.
        """
        selected_count = sum(1 for i in row.ids if i in self._selected)
        if selected_count == 0:
            checkbox = _UNSELECTED
        elif selected_count == len(row.ids):
            checkbox = _SELECTED
        else:
            checkbox = _PARTIAL_SELECTED
        name = f"{checkbox} {row.name}"

        name_field = max(1, _NAME_WIDTH - self._prefix_width(depth, row.is_folder))
        padded_name = name + " " * max(1, name_field - cell_len(name))

        counts = f"{row.synced}/{row.total}"
        colour, word = _MARKER[row.state]
        label = Text(f"{padded_name}{counts:>{_COUNT_WIDTH}}  ")
        label.append(f"{word:>{_STATE_WIDTH}}", style=colour)
        return label

    def action_toggle_expand(self) -> None:
        """Expand or collapse the highlighted folder (including "All playlists")."""
        node = self.query_one(Tree).cursor_node
        if node is not None and node.allow_expand:
            node.toggle()

    def action_toggle_selection(self) -> None:
        """Toggle the highlighted row; a folder or "All" toggles every playlist it covers."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return
        row: _Row = node.data
        if not row.ids:
            return
        if all(i in self._selected for i in row.ids):
            self._selected.difference_update(row.ids)
        else:
            self._selected.update(row.ids)
        self._refresh_labels(tree.root, depth=0)
        self._update_status()

    def _refresh_labels(self, node: TreeNode, depth: int) -> None:
        if node.data is not None:
            node.set_label(self._label(node.data, depth))
        for child in node.children:
            self._refresh_labels(child, depth + 1)

    def _update_status(self) -> None:
        count = len(self._selected)
        message = f"{count} playlist{'s' if count != 1 else ''} selected"
        if count:
            message += " -- press enter to sync"
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a node: with a selection, start the sync."""
        event.stop()
        if not self._selected:
            self._update_status()
            return
        self.app.push_screen(ProgressScreen(self.library, sorted(self._selected)))
