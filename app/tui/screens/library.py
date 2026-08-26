"""Library screen: step 3 of the target flow -- the playlist tree.

Arrow keys move, space toggles selection (a folder toggles every descendant
playlist at once), enter confirms and, with at least one playlist selected,
starts the sync (step 4, the Progress screen). Coming back here after a sync
(Done -> enter -> pop_screen) re-reads sync state from disk rather than
showing whatever was true when the screen first loaded -- a track this
screen doesn't reload for stays looking unsynced until the whole app
restarts, which is exactly the bug this refresh-on-resume exists to avoid.
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
from app.tui.screens.progress import ProgressScreen

_MARKER = {
    SyncState.SYNCED: ("green", "synced"),
    SyncState.PARTIAL: ("yellow", "partial"),
    SyncState.NOT_SYNCED: ("red", "not synced"),
}
_SELECTED = "✓"
_UNSELECTED = "·"
_PARTIAL_SELECTED = "~"
_STATUS_ID = "selection-status"

# Fixed-width columns so the count and state sit in roughly the same place on
# every row regardless of name length or nesting depth -- a real table would
# align perfectly, but Tree has no column model, and a fixed-width label
# gets close enough without giving up the folder hierarchy a table can't show.
_NAME_WIDTH = 30
_COUNT_WIDTH = 7
_STATE_WIDTH = 10


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
        states = await self.app.run_rekordbox(playlist_tree_sync_states, self._library)
        for state in states:
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
        name = f"{checkbox} {state.node.playlist.name}"
        counts = f"{state.synced}/{state.total}"
        colour, word = _MARKER[state.state]
        return (
            f"{name:<{_NAME_WIDTH}} {counts:>{_COUNT_WIDTH}}  "
            f"[{colour}]{word:>{_STATE_WIDTH}}[/{colour}]"
        )

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
            message += " -- press enter to sync"
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a node: with a selection, start the sync."""
        event.stop()
        if not self._selected:
            self._update_status()
            return
        self.app.push_screen(ProgressScreen(self._library, sorted(self._selected)))
