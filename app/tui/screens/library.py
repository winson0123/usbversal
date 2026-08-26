"""Library screen: step 3 of the target flow -- the playlist tree.

Arrow keys move, space toggles selection (a folder toggles every descendant
playlist at once), enter confirms. Confirming does not yet run a sync --
that's screens 4-5, TASK-208 -- so it reports the selection instead of acting
on it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static, Tree
from textual.widgets.tree import TreeNode

from app.core.domain import SyncState
from app.services.library import UsbLibrary
from app.services.sync_service import PlaylistTreeSyncState, playlist_tree_sync_states

_MARKER = {
    SyncState.SYNCED: ("green", "synced"),
    SyncState.PARTIAL: ("yellow", "partial"),
    SyncState.NOT_SYNCED: ("red", "not synced"),
}
_SELECTED = "✓"
_UNSELECTED = "·"
_PARTIAL_SELECTED = "~"
_STATUS_ID = "selection-status"


class LibraryScreen(Screen):
    """
    Playlist folder tree with a per-node sync state and multi-select.

    Space is bound here as a **priority** binding, which is what lets it win
    over Tree's own default space-toggles-expand binding on the focused
    widget -- every folder is expanded on load instead, so there is nothing
    left to toggle open, and space is free for selecting playlists to sync
    per the target flow (docs/planning/interactive-tui.md).
    """

    BINDINGS = [
        Binding("space", "toggle_selection", "Select", show=True, priority=True),
    ]

    def __init__(self, library: UsbLibrary) -> None:
        """
        Args:
            library: Opened session handle to read playlists and sync state from.
        """
        super().__init__()
        self._library = library
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        tree: Tree[PlaylistTreeSyncState] = Tree("Playlists", id="playlist-tree")
        tree.show_root = False
        yield tree
        yield Static("", id=_STATUS_ID)
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        for state in playlist_tree_sync_states(self._library):
            self._add_node(tree.root, state)
        tree.root.expand()
        tree.cursor_line = 0
        tree.focus()
        self._update_status()

    def _add_node(self, parent: TreeNode, state: PlaylistTreeSyncState) -> None:
        """Recursively mirror a PlaylistTreeSyncState into the Tree widget."""
        if state.node.playlist.is_folder:
            node = parent.add(self._label(state), data=state, expand=True)
        else:
            node = parent.add_leaf(self._label(state), data=state)
        for child in state.children:
            self._add_node(node, child)

    @staticmethod
    def _leaf_ids(state: PlaylistTreeSyncState) -> list[int]:
        """Playlist ids of every non-folder descendant, including itself."""
        if not state.node.playlist.is_folder:
            return [state.node.playlist.id]
        ids: list[int] = []
        for child in state.children:
            ids.extend(LibraryScreen._leaf_ids(child))
        return ids

    def _label(self, state: PlaylistTreeSyncState) -> str:
        ids = self._leaf_ids(state)
        selected_count = sum(1 for i in ids if i in self._selected)
        if not ids or selected_count == 0:
            checkbox = _UNSELECTED
        elif selected_count == len(ids):
            checkbox = _SELECTED
        else:
            checkbox = _PARTIAL_SELECTED
        colour, word = _MARKER[state.state]
        return f"{checkbox} {state.node.playlist.name}  [{colour}]{word}[/{colour}]"

    def action_toggle_selection(self) -> None:
        """Toggle the highlighted node; a folder toggles every descendant playlist."""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return
        ids = self._leaf_ids(node.data)
        if not ids:
            return
        if all(i in self._selected for i in ids):
            self._selected.difference_update(ids)
        else:
            self._selected.update(ids)
        self._refresh_labels(tree.root)
        self._update_status()

    def _refresh_labels(self, node: TreeNode) -> None:
        if node.data is not None:
            node.set_label(self._label(node.data))
        for child in node.children:
            self._refresh_labels(child)

    def _update_status(self) -> None:
        count = len(self._selected)
        message = f"{count} playlist{'s' if count != 1 else ''} selected"
        if count:
            message += " -- press enter to sync (not wired yet, TASK-208)"
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a node: report the selection. Running the sync is TASK-208."""
        event.stop()
        self._update_status()
