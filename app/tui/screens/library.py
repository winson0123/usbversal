"""Library screen: playlist tree on the left, track preview on the right.

Arrow keys move, space toggles selection (a folder toggles every descendant
playlist at once, and the "All playlists" row at the very top -- a real,
collapsible container for everything else, not just a sibling summary --
toggles the whole library), "e" expands or collapses the highlighted folder,
enter confirms and, with at least one playlist selected, starts the sync
(step 4, the Progress screen). Highlighting a playlist fills the right
pane. Coming back here after a sync (Done -> enter -> pop_screen) re-reads
sync state from disk rather than showing whatever was true when the screen
first loaded.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, Tree
from textual.widgets.tree import TreeNode

from app.core.domain import SyncState
from app.services.library import UsbLibrary
from app.services.sync_service import (
    PlaylistTreeSyncState,
    combine_sync_states,
    playlist_tree_sync_states,
)
from app.services.track_preview import TrackPreview, preview_playlist_tracks
from app.tui.screens.progress import ProgressScreen

_COUNT_COLOUR = {
    SyncState.SYNCED: "green",
    SyncState.PARTIAL: "yellow",
    SyncState.NOT_SYNCED: "red",
}
# Plain ASCII, not a unicode checkmark/dot: those have ambiguous terminal
# cell width depending on font, which was throwing the columns below off by
# a cell on exactly the rows that used them. Unselected is a space, not "-".
_SELECTED = "x"
_UNSELECTED = " "
_PARTIAL_SELECTED = "~"
_STATUS_ID = "selection-status"
_MOUNT_ID = "mount-info"
_LEGEND_ID = "sync-legend"
_ALL_NAME = "All playlists"
_COLUMNS = ("Title", "Genre", "Key", "BPM")

# Fixed-width columns so the count sits in the same place on every row.
# Tree has no column model, so this is a label string padded with knowledge
# of exactly how many cells Tree's own guide lines and expand icon consume
# before the label starts at a given depth (see _prefix_width).
_COUNT_WIDTH = 7
_TREE_GUTTER = 2
_GENRE_WIDTH = 12
_KEY_WIDTH = 6
_BPM_WIDTH = 6
_TABLE_GUTTER = 8


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
        margin: 0 0 0 1;
        height: auto;
    }
    LibraryScreen #panes {
        height: 1fr;
    }
    LibraryScreen #playlist-pane {
        width: 2fr;
        min-width: 48;
        height: 1fr;
        border: round;
        padding: 0 1;
    }
    LibraryScreen #track-pane {
        width: 3fr;
        height: 1fr;
        border: round;
        padding: 0 1;
    }
    LibraryScreen #playlist-tree,
    LibraryScreen #track-table {
        height: 1fr;
    }
    LibraryScreen #track-table {
        overflow-x: hidden;
    }
    LibraryScreen #sync-legend {
        dock: bottom;
        height: auto;
        border-top: solid;
        padding: 1 0 0 0;
    }
    LibraryScreen #selection-status {
        height: auto;
        margin: 0 1;
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
        self._sort_key: str | None = None
        self._sort_reverse = False

    def compose(self) -> ComposeResult:
        yield Static(f"Mounted: {self.library.mount}", id=_MOUNT_ID)
        with Horizontal(id="panes"):
            playlist_pane = Vertical(id="playlist-pane")
            playlist_pane.border_title = "Playlists"
            with playlist_pane:
                tree: Tree[_Row] = Tree("Playlists", id="playlist-tree")
                tree.show_root = False
                yield tree
                yield Static(_legend_text(), id=_LEGEND_ID)
            track_pane = Vertical(id="track-pane")
            track_pane.border_title = "Tracks"
            with track_pane:
                table: DataTable[str] = DataTable(id="track-table")
                table.cursor_type = "row"
                table.zebra_stripes = True
                table.show_horizontal_scrollbar = False
                yield table
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
        self._refresh_labels(tree.root, depth=0)
        self._clear_table()
        self._apply_column_widths()
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
        Build one tree-row label with a coloured ``x/y`` count.

        Playlist names are arbitrary user data, so the count colour is a
        ``Text`` style, not a markup tag that a ``[`` in the name could break.
        Only the numerator is green when the row is fully synced.

        Args:
            row: Row data to render.
            depth: Nesting depth, used to pad the name around Tree guides.

        Returns:
            Label text with the count styled red/yellow/green.
        """
        selected_count = sum(1 for i in row.ids if i in self._selected)
        if selected_count == 0:
            checkbox = _UNSELECTED
        elif selected_count == len(row.ids):
            checkbox = _SELECTED
        else:
            checkbox = _PARTIAL_SELECTED
        name_field = max(8, self._name_column_width() - self._prefix_width(depth, row.is_folder))
        name = f"{checkbox} {_clip(row.name, max(4, name_field - 2))}"
        padded_name = name + " " * max(0, name_field - cell_len(name))

        colour = _COUNT_COLOUR[row.state]
        counts = f"{row.synced}/{row.total}"
        label = Text(padded_name)
        label.append(f"{counts:>{_COUNT_WIDTH}}", style=colour)
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
        """
        Rewrite every label so checkbox, clip width, and count stay in sync.

        The hidden Tree root has no ``_Row``. Its children start at ``depth``
        rather than ``depth + 1``, matching how ``_refresh`` labels
        ``All playlists`` at depth 0.

        Args:
            node: Node to refresh, then walk into.
            depth: Nesting depth of ``node`` when it has row data; for the
                hidden root this is the depth its children should use.
        """
        child_depth = depth
        if node.data is not None:
            node.set_label(self._label(node.data, depth))
            child_depth = depth + 1
        for child in node.children:
            self._refresh_labels(child, child_depth)

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

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[_Row]) -> None:
        """Fill the track table from the highlighted playlist."""
        row = event.node.data
        if row is None or row.is_folder or len(row.ids) != 1:
            self._clear_table()
            return
        self.run_worker(self._show_tracks(row.ids[0]), exclusive=True)

    async def _show_tracks(self, playlist_id: int) -> None:
        """
        Load preview rows on the Rekordbox thread and paint the table.

        Args:
            playlist_id: Highlighted leaf playlist id.
        """
        tracks = await self.app.run_rekordbox(preview_playlist_tracks, self.library, playlist_id)
        self._fill_table(tracks)

    def _clear_table(self) -> None:
        """Empty the preview table and restore the default columns."""
        table = self.query_one("#track-table", DataTable)
        table.clear(columns=True)
        table.add_columns(*_COLUMNS)
        self._apply_column_widths()
        self._sort_key = None
        self._sort_reverse = False

    def _fill_table(self, tracks: list[TrackPreview]) -> None:
        """
        Replace the preview table with one row per track.

        Titles are clipped to the Title column so Genre / Key / BPM stay
        on screen without a horizontal scroll.

        Args:
            tracks: Playlist order from ``preview_playlist_tracks``.
        """
        table = self.query_one("#track-table", DataTable)
        table.clear(columns=True)
        table.add_columns(*_COLUMNS)
        title_width = self._title_column_width()
        for track in tracks:
            colour = _COUNT_COLOUR[track.state]
            table.add_row(
                Text(_clip(track.title, title_width), style=colour),
                Text(_clip(track.genre, _GENRE_WIDTH), style=colour),
                Text(_clip(track.key, _KEY_WIDTH), style=colour),
                Text(_clip(track.bpm, _BPM_WIDTH), style=colour),
            )
        self._apply_column_widths()
        self._sort_key = None
        self._sort_reverse = False

    def on_resize(self) -> None:
        """Reflow tree names and table columns when the window changes."""
        if self.query("#playlist-tree"):
            self._refresh_labels(self.query_one(Tree).root, depth=0)
        if self.query("#track-table"):
            self._apply_column_widths()

    def _name_column_width(self) -> int:
        """
        Cells available for the playlist name plus checkbox, before ``x/y``.

        Uses the live tree width so nested rows still have room to read.
        A fixed 16-cell column left depth-3 folders as a single letter.

        Returns:
            At least 24 cells so a three-level name is still a word.
        """
        tree = self.query_one(Tree)
        return max(24, tree.size.width - _COUNT_WIDTH - _TREE_GUTTER)

    def _title_column_width(self) -> int:
        """
        Cells left for Title after Genre, Key, BPM, and table chrome.

        Returns:
            At least 8 cells so a truncated title still reads.
        """
        table = self.query_one("#track-table", DataTable)
        leftover = table.size.width - _GENRE_WIDTH - _KEY_WIDTH - _BPM_WIDTH - _TABLE_GUTTER
        return max(8, leftover)

    def _apply_column_widths(self) -> None:
        """
        Pin every preview column so the table does not scroll sideways.

        Returns:
            None.
        """
        table = self.query_one("#track-table", DataTable)
        if not table.columns:
            return
        widths = (self._title_column_width(), _GENRE_WIDTH, _KEY_WIDTH, _BPM_WIDTH)
        for key, width in zip(table.columns, widths, strict=True):
            column = table.columns[key]
            column.width = width
            column.auto_width = False
        table.refresh()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort the preview by the clicked column; click again reverses."""
        key = str(event.column_key)
        reverse = self._sort_key == key and not self._sort_reverse
        self._sort_key = key
        self._sort_reverse = reverse
        event.data_table.sort(event.column_key, reverse=reverse)


def _legend_text() -> Text:
    """
    Traffic-light key under the playlist tree.

    Returns:
        Three lines: coloured dot plus synced / partial / not synced.
    """
    line = Text()
    line.append("•", style="green")
    line.append(" synced\n")
    line.append("•", style="yellow")
    line.append(" partial\n")
    line.append("•", style="red")
    line.append(" not synced")
    return line


def _clip(text: str, width: int) -> str:
    """
    Fit ``text`` into ``width`` cells, with an ellipsis when it overflows.

    Args:
        text: Display string, possibly longer than the column.
        width: Maximum cells to occupy.

    Returns:
        ``text``, or a truncated prefix ending in ``...``.
    """
    if width <= 0:
        return ""
    if cell_len(text) <= width:
        return text
    if width <= 3:
        clipped = ""
        for char in text:
            if cell_len(clipped + char) >= width:
                break
            clipped += char
        return clipped
    budget = width - 3
    clipped = ""
    for char in text:
        if cell_len(clipped + char) > budget:
            break
        clipped += char
    return clipped + "..."
