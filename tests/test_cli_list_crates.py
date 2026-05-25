"""CLI tests for list-crates command."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.cli.main import main
from app.core.domain import SeratoCrate, SeratoLibrary
from app.services.crate_service import CrateListResult


def test_list_crates_json_output() -> None:
    """list-crates --json prints valid JSON."""
    library = SeratoLibrary(
        mount_path=Path("/mnt/usb"),
        serato_root=Path("/mnt/usb/_Serato_"),
        database_path=Path("/mnt/usb/_Serato_/database V2"),
        database_track_count=793,
    )
    contents_crate = SeratoCrate(
        name="Contents",
        path=Path("/mnt/usb/_Serato_/Subcrates/Contents.crate"),
        track_count=793,
    )
    result = CrateListResult(library=library, crates=(contents_crate,))
    with patch("app.cli.main.list_serato_crates", return_value=result):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(["list-crates", "--mount", "/mnt/usb", "--json"])
    assert code == 0
    data = json.loads(stdout.getvalue())
    assert data["crate_count"] == 1
    assert data["crates"][0]["name"] == "Contents"
