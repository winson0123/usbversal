"""CLI tests for list-playlists command."""

import json
from io import StringIO
from unittest.mock import patch

from app.cli.main import main
from app.core.domain import Playlist, RekordboxDbFormat, RekordboxLibrary
from app.services.playlist_service import PlaylistListResult


def test_list_playlists_json_output() -> None:
    """list-playlists --json prints valid JSON."""
    library = RekordboxLibrary(
        mount_path=__import__("pathlib").Path("/mnt/usb"),
        database_path=__import__("pathlib").Path("/mnt/usb/PIONEER/rekordbox/exportLibrary.db"),
        db_format=RekordboxDbFormat.ONE_LIBRARY,
    )
    result = PlaylistListResult(
        library=library,
        playlists=(
            Playlist(id=18, name="House", parent_id=17, is_folder=False, track_count=3),
        ),
    )
    with patch("app.cli.main.list_rekordbox_playlists", return_value=result):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(["list-playlists", "--mount", "/mnt/usb", "--json"])
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert data["count"] == 1
    assert data["playlists"][0]["name"] == "House"
