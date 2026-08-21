"""Tests for CLI entrypoint."""

import json
from pathlib import Path

from app.cli.main import main
from tests.conftest import EMPTY_DATABASE_V2


def test_json_output_is_parseable_with_logs_on_stderr(tmp_path: Path, capsys) -> None:
    """`--json` writes only JSON to stdout; structlog output goes to stderr."""
    serato = tmp_path / "_Serato_"
    (serato / "Subcrates").mkdir(parents=True)
    (serato / "database V2").write_bytes(EMPTY_DATABASE_V2)

    code = main(["list-crates", "--mount", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["library"]["mount_path"] == str(tmp_path)


def test_unknown_command_exits_nonzero(capsys) -> None:
    """An unrecognised command does not exit 0."""
    try:
        code = main(["definitely-not-a-command"])
    except SystemExit as exc:
        code = exc.code
    assert code != 0
