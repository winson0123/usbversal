"""Library screen: playlist tree on the left, track preview on the right.

Arrow keys move, space toggles selection (a folder toggles every descendant
playlist at once), "^a" selects or clears the whole library, "e" expands or
collapses the highlighted folder, enter confirms and, with at least one
playlist selected, starts the sync (step 4, the Progress screen).
Highlighting a playlist fills the right pane. Coming back here after a
sync (Done -> enter -> pop_screen) re-reads sync state from disk rather
than showing whatever was true when the screen first loaded.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from rich.cells import cell_len
from rich.style import Style
from rich.text import Text
from textual._segment_tools import line_pad
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import CenterMiddle, Horizontal, Vertical
from textual.screen import Screen
from textual.strip import Strip
from textual.widgets import DataTable, Footer, Static, Tree
from textual.widgets.tree import TreeNode

from app.core.domain import SyncState
from app.services.library import UsbLibrary
from app.services.sync_service import (
    PlaylistTreeSyncState,
    playlist_tree_sync_states,
)
from app.services.track_preview import TrackPreview, preview_playlist_tracks
from app.tui.palette import ACCENT
from app.tui.screens.progress import ProgressScreen
from app.tui.widgets.scan_bar import ScanBar

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
_HEADER_ID = "header"
_LEGEND_ID = "sync-legend"
_TRACK_SCAN_WRAP_ID = "track-scan-wrap"
_TRACK_SCAN_ID = "track-scan"
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
    """Whatever one tree row needs to render and toggle, a playlist or folder."""

    name: str
    state: SyncState
    synced: int
    total: int
    ids: tuple[int, ...]
    is_folder: bool


class PlaylistTree(Tree[_Row]):
    """
    Playlist tree whose guide lines follow the cursor.

    Textual only lights guides under a selected folder. A crate under the
    cursor also lights the path back to the root. A selected folder still
    lights every child.
    """

    def watch_cursor_line(self, previous_line: int, line: int) -> None:
        """Repaint every visible row so path guides stay in sync with the cursor."""
        super().watch_cursor_line(previous_line, line)
        self.refresh()

    def watch_hover_line(self, previous_hover_line: int, hover_line: int) -> None:
        """Repaint every visible row so path guides stay in sync with the pointer."""
        super().watch_hover_line(previous_hover_line, hover_line)
        self.refresh()

    def _lit_path(self) -> set[TreeNode[_Row]]:
        """
        Nodes from the root down to the cursor, and to the hovered node.

        Returns:
            The union of those two ancestor chains.
        """
        nodes: set[TreeNode[_Row]] = set()
        hover = self._get_node(self.hover_line) if self.hover_line >= 0 else None
        for start in (self.cursor_node, hover):
            node = start
            while node is not None:
                nodes.add(node)
                node = node.parent
        return nodes

    def _guide_glyphs(self, style: Style, hidden: bool) -> tuple[str, str, str, str]:
        """
        Space, vertical, terminator, and cross glyphs for one indent step.

        Args:
            style: Guide style; bold or underline2 pick a heavier line set.
            hidden: True to emit blank guides.

        Returns:
            Four guide strings sized to ``guide_depth``.
        """
        lines: tuple[Iterable[str], Iterable[str], Iterable[str], Iterable[str]]
        if self.show_guides and not hidden:
            lines = self.LINES["default"]
            if style.bold:
                lines = self.LINES["bold"]
            elif style.underline2:
                lines = self.LINES["double"]
        else:
            lines = ("  ", "  ", "  ", "  ")
        extra = max(0, self.guide_depth - 2)
        return cast(
            "tuple[str, str, str, str]",
            tuple(f"{chars[0]}{chars[1] * extra} " for chars in lines),
        )

    def _render_line(self, y: int, x1: int, x2: int, base_style: Style) -> Strip:
        """
        Render one tree row, lighting guides on the cursor path and under a folder.

        Args:
            y: Absolute tree line, including scroll.
            x1: Left crop cell.
            x2: Right crop cell.
            base_style: Widget style behind the row.

        Returns:
            The cropped strip for this row.
        """
        tree_lines = self._tree_lines
        width = self.size.width
        if y >= len(tree_lines):
            return Strip.blank(width, base_style)

        line = tree_lines[y]
        is_hover = self.hover_line >= 0 and any(node._hover for node in line.path)
        lit_path = self._lit_path()
        cache_key = (
            y,
            is_hover,
            width,
            self._updates,
            self._pseudo_class_state,
            id(self.cursor_node),
            self.hover_line,
            tuple(node._updates for node in line.path),
        )
        if cache_key in self._line_cache:
            strip = self._line_cache[cache_key]
        else:
            base_hidden = self.get_component_styles("tree--guides").color.a == 0
            hover_hidden = self.get_component_styles("tree--guides-hover").color.a == 0
            selected_hidden = self.get_component_styles("tree--guides-selected").color.a == 0
            base_guide_style = self.get_component_rich_style("tree--guides", partial=True)
            guide_hover_style = base_guide_style + self.get_component_rich_style(
                "tree--guides-hover", partial=True
            )
            guide_selected_style = base_guide_style + self.get_component_rich_style(
                "tree--guides-selected", partial=True
            )
            hover = line.path[0]._hover
            selected = line.path[0]._selected and self.has_focus
            line_style = (
                self.get_component_rich_style("tree--highlight-line") if is_hover else base_style
            )
            line_style += Style(meta={"line": y})
            guides = Text(style=line_style)
            guide_style = base_guide_style
            hidden = True
            for node in line.path[1:]:
                guide_style = base_guide_style
                hidden = base_hidden
                if hover:
                    guide_style = guide_hover_style
                    hidden = hover_hidden
                if (selected or node in lit_path) and self.has_focus:
                    guide_style = guide_selected_style
                    hidden = selected_hidden
                space, vertical, _, _ = self._guide_glyphs(guide_style, hidden)
                if node != line.path[-1]:
                    guides.append(space if node.is_last else vertical, style=guide_style)
                hover = hover or node._hover
                selected = (selected or node._selected) and self.has_focus
            if len(line.path) > 1:
                _, _, terminator, cross = self._guide_glyphs(guide_style, hidden)
                guides.append(terminator if line.last else cross, style=guide_style)
            label_style = self.get_component_rich_style("tree--label", partial=True)
            if self.hover_line == y:
                label_style += self.get_component_rich_style("tree--highlight", partial=True)
            if self.cursor_line == y:
                label_style += self.get_component_rich_style("tree--cursor", partial=False)
            label = self.render_label(line.path[-1], line_style, label_style).copy()
            label.stylize(Style(meta={"node": line.node._id}))
            guides.append(label)
            segments = list(guides.render(self.app.console))
            pad_width = max(self.virtual_size.width, width)
            segments = line_pad(segments, 0, pad_width - guides.cell_len, line_style)
            strip = self._line_cache[cache_key] = Strip(segments)
        return strip.crop(x1, x2)


class LibraryScreen(Screen):
    """
    Playlist folder tree with a per-node sync state and multi-select.

    Space is bound here as a **priority** binding, which is what lets it win
    over Tree's own default space-toggles-expand binding on the focused
    widget. Space selects playlists to sync, and expand/collapse moves
    to "e" so both actions stay reachable.
    """

    BINDINGS = [
        Binding("space", "toggle_selection", "Select", show=True, priority=True),
        Binding("ctrl+a", "select_all", "Select All", show=True, key_display="^a"),
        Binding("e", "toggle_expand", "Expand/collapse", show=True),
    ]

    DEFAULT_CSS = f"""
    LibraryScreen #header {{
        height: auto;
        padding: 0 1;
    }}
    LibraryScreen #mount-info {{
        text-style: dim;
        width: 1fr;
        height: auto;
    }}
    LibraryScreen #selection-status {{
        width: auto;
        height: auto;
        text-align: right;
    }}
    LibraryScreen #panes {{
        height: 1fr;
    }}
    LibraryScreen #playlist-pane {{
        width: 2fr;
        min-width: 48;
        height: 1fr;
        border: round {ACCENT};
        border-title-color: {ACCENT};
        padding: 0 1;
    }}
    LibraryScreen #track-pane {{
        width: 3fr;
        height: 1fr;
        border: round {ACCENT};
        border-title-color: {ACCENT};
        padding: 0 1;
    }}
    LibraryScreen #playlist-tree {{
        height: 1fr;
        overflow-x: hidden;
        scrollbar-visibility: hidden;
        scrollbar-size-vertical: 0;
        scrollbar-size-horizontal: 0;
    }}
    LibraryScreen #playlist-tree > .tree--guides,
    LibraryScreen #playlist-tree > .tree--guides-hover {{
        color: ansi_bright_black;
    }}
    LibraryScreen #playlist-tree > .tree--guides-selected,
    LibraryScreen #playlist-tree:focus > .tree--guides-selected {{
        color: ansi_default;
    }}
    LibraryScreen #track-scan-wrap {{
        width: 100%;
        height: 1fr;
    }}
    LibraryScreen #track-scan {{
        width: auto;
        text-align: center;
    }}
    LibraryScreen #track-table {{
        height: 1fr;
        overflow-x: hidden;
        background: transparent;
        color: ansi_default;
    }}
    LibraryScreen #track-table > .datatable--header,
    LibraryScreen #track-table:ansi > .datatable--header {{
        background: transparent;
        color: ansi_default;
    }}
    LibraryScreen #track-table > .datatable--even-row {{
        background: transparent;
    }}
    LibraryScreen #sync-legend {{
        dock: bottom;
        height: auto;
        border-top: solid;
        margin: 0;
        padding: 0;
    }}
    """

    def __init__(
        self,
        library: UsbLibrary,
        states: tuple[PlaylistTreeSyncState, ...] | None = None,
    ) -> None:
        """
        Args:
            library: Opened session handle to read playlists and sync state from.
            states: Tree already computed on Home, used for the first paint
                so this screen does not repeat the analysis wait.
        """
        super().__init__()
        self.library = library
        self._selected: set[int] = set()
        self._all_ids: tuple[int, ...] = ()
        self._sort_key: str | None = None
        self._sort_reverse = False
        self._refreshing = False
        self._initial_states = states
        self._tracks_load_id = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id=_HEADER_ID):
            yield Static(f"Mounted: {self.library.mount}", id=_MOUNT_ID)
            yield Static("", id=_STATUS_ID)
        with Horizontal(id="panes"):
            playlist_pane = Vertical(id="playlist-pane")
            playlist_pane.border_title = "Playlists"
            with playlist_pane:
                tree: PlaylistTree = PlaylistTree("Playlists", id="playlist-tree")
                tree.show_root = False
                yield tree
                yield Static(_legend_text(), id=_LEGEND_ID)
            track_pane = Vertical(id="track-pane")
            track_pane.border_title = "Tracks"
            with track_pane:
                with CenterMiddle(id=_TRACK_SCAN_WRAP_ID):
                    yield ScanBar(id=_TRACK_SCAN_ID)
                table: DataTable[str] = DataTable(id="track-table")
                table.cursor_type = "row"
                table.zebra_stripes = False
                table.show_horizontal_scrollbar = False
                table.display = False
                yield table
        yield Footer()

    def on_screen_resume(self) -> None:
        """
        Schedule a tree rebuild every time this screen becomes active.

        Must return before any USB work: awaiting ANLZ and tag reads here
        kept Home on screen with a frozen scan bar. Fires on the first
        activation as well as later resumes (Textual gives no separate
        first-time signal), so this is the one place the tree is built.
        """
        if self._initial_states is not None:
            states = self._initial_states
            self._initial_states = None
            self._apply_states(states, busy=None)
            return
        if self._refreshing:
            return
        self._refreshing = True
        self._set_status("Reading library…")
        self.run_worker(
            self._refresh(), exclusive=True, group="library-refresh", name="library-refresh"
        )

    async def _refresh(self) -> None:
        """
        Rebuild the tree from disk after this screen becomes active again.

        First open from Home already ships full analysis states, so this
        path is the post-sync resume. Keep the existing colours on screen
        and replace them only when the full ANLZ/tag pass finishes — a
        crate-only intermediate paint would flash every playlist as
        ``0/N`` / not synced.

        Returns:
            None.
        """
        try:
            if self._all_ids:
                self._set_status("Checking analysis…")
                await self._rebuild(check_analysis=True, busy=None)
            else:
                await self._rebuild(check_analysis=False, busy="Checking analysis…")
                await self._rebuild(check_analysis=True, busy=None)
        finally:
            self._refreshing = False

    async def _rebuild(self, *, check_analysis: bool, busy: str | None) -> None:
        """
        Replace the tree from one ``playlist_tree_sync_states`` pass.

        Args:
            check_analysis: When False, skip ANLZ and tag reads.
            busy: Status text while a later pass is still running, or
                None to show the selection count.

        Returns:
            None.
        """
        # playlist_tree_sync_states reads through library.rekordbox, which
        # must stay on the app's one dedicated thread. See
        # UsbversalApp.run_rekordbox.
        try:
            states = await self.app.run_rekordbox(
                playlist_tree_sync_states, self.library, check_analysis=check_analysis
            )
        except Exception:
            # Keep the existing tree. A Diesel/rbox failure must not tear
            # down the screen or drop PyOneLibrary on the UI thread.
            if busy is None:
                self._update_status()
            return
        self._apply_states(states, busy=busy)

    def _apply_states(self, states: tuple[PlaylistTreeSyncState, ...], *, busy: str | None) -> None:
        """
        Mirror tree-sync states into the widget, keeping the current selection.

        Args:
            states: Root-level nodes from ``playlist_tree_sync_states``.
            busy: Status text when a later pass is still running, or None.

        Returns:
            None.
        """
        tree = self.query_one(Tree)
        cursor = tree.cursor_line
        kept = set(self._selected)
        tree.clear()
        self._selected.clear()
        self._all_ids = tuple(i for state in states for i in state.leaf_ids)
        for state in states:
            self._add_node(tree.root, state, depth=0)
        self._selected = {i for i in kept if i in self._all_ids}

        tree.root.expand()
        if tree.root.children:
            tree.cursor_line = cursor
            tree.focus()
        self._refresh_labels(tree.root, depth=0)
        self._set_tracks_loading(True)
        self._clear_table()
        self._apply_column_widths()
        if busy is not None:
            self._set_status(busy)
        else:
            self._update_status()

    def _set_status(self, message: str) -> None:
        """
        Write the header status line.

        Args:
            message: Text to show beside the mount path.

        Returns:
            None.
        """
        self.query_one(f"#{_STATUS_ID}", Static).update(message)

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
        at this depth, matched empirically against Tree's rendering
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
        The numerator counts green tracks only. The count colour is the
        playlist's rolled-up state.

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
        """Expand or collapse the highlighted folder."""
        node = self.query_one(Tree).cursor_node
        if node is not None and node.allow_expand:
            node.toggle()

    def action_select_all(self) -> None:
        """Select every playlist, or clear the selection if all are already selected."""
        if not self._all_ids:
            return
        if all(i in self._selected for i in self._all_ids):
            self._selected.clear()
        else:
            self._selected.update(self._all_ids)
        self._refresh_labels(self.query_one(Tree).root, depth=0)
        self._update_status()

    def action_toggle_selection(self) -> None:
        """Toggle the highlighted row; a folder toggles every playlist it covers."""
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
        top-level playlists at depth 0.

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
        """
        Show how many playlists are selected, beside the mount path.

        Returns:
            None.
        """
        count = len(self._selected)
        message = f"{count} playlist{'s' if count != 1 else ''} selected"
        if count:
            message += ", press enter to sync"
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
            self._tracks_load_id += 1
            self._set_tracks_loading(False)
            self._clear_table()
            return
        self._tracks_load_id += 1
        token = self._tracks_load_id
        self._set_tracks_loading(True)
        self.run_worker(self._show_tracks(row.ids[0], token), exclusive=True, group="track-preview")

    async def _show_tracks(self, playlist_id: int, token: int) -> None:
        """
        Load preview rows on the Rekordbox thread and paint the table.

        A stale token means a later highlight owns the pane, so this
        pass must not hide the scan bar or overwrite the table.

        Args:
            playlist_id: Highlighted leaf playlist id.
            token: ``_tracks_load_id`` at the time this load was started.
        """
        try:
            tracks = await self.app.run_rekordbox(
                preview_playlist_tracks, self.library, playlist_id
            )
        except Exception:
            # Keep the pane alive. Re-raising here crashes the worker and
            # can drop PyOneLibrary on the UI thread during teardown.
            if token == self._tracks_load_id:
                self._set_tracks_loading(False)
                self._clear_table()
            return
        if token != self._tracks_load_id:
            return
        self._set_tracks_loading(False)
        self._fill_table(tracks)

    def _set_tracks_loading(self, loading: bool) -> None:
        """
        Show the Home scan bar in the Tracks pane, or the table.

        Args:
            loading: True while preview rows are not ready yet.
        """
        self.query_one(f"#{_TRACK_SCAN_WRAP_ID}").display = loading
        self.query_one("#track-table", DataTable).display = not loading

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

        Uses the Tracks pane when the table is hidden (scan bar up),
        because a hidden table reports a width too small to clip against.

        Returns:
            At least 8 cells so a truncated title still reads.
        """
        table = self.query_one("#track-table", DataTable)
        width = table.size.width
        if width < 16:
            pane = self.query_one("#track-pane")
            width = max(0, pane.size.width - 4)
        leftover = width - _GENRE_WIDTH - _KEY_WIDTH - _BPM_WIDTH - _TABLE_GUTTER
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
        Three lines: coloured dot and matching word for each sync state.
    """
    line = Text()
    line.append("• synced\n", style="green")
    line.append("• partial\n", style="yellow")
    line.append("• not synced", style="red")
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
