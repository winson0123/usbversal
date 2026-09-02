# Release

A `v*` tag on `main` is the release. The
[Release](../../.github/workflows/release.yml) workflow builds a native
PyInstaller binary on Windows, macOS, and Linux and attaches them to a
GitHub Release. PyInstaller cannot cross-compile, so each artifact is
built on that OS.

Every push and pull request to `main` runs
[CI](../../.github/workflows/ci.yml) (`ruff` and `pytest`), including
the version-parity test.

## Version files

These two must stay identical. `tests/test_version.py` fails the build
if they drift.

| File | Field |
|------|-------|
| `pyproject.toml` | `project.version` |
| `app/__init__.py` | `__version__` |

## Cut a version

`main` must be clean and at the commit you want to ship.

1. Set both version files to the same `X.Y.Z`.
2. Commit on `main`. `[TASK-…] Release X.Y.Z.`
3. Tag and push:

```bash
git tag -a vX.Y.Z -m "Usbversal X.Y.Z"
git push origin main
git push origin vX.Y.Z
```

4. The Release workflow runs `ruff` and `pytest` on Ubuntu, then
   PyInstaller on `ubuntu-latest`, `windows-latest`, and
   `macos-latest`, then creates `vX.Y.Z` (or updates its assets if it
   already exists).
5. The GitHub Release should have:

| Artifact | Built on |
|----------|----------|
| `usbversal-linux-x86_64` | Ubuntu x86_64 |
| `usbversal-windows-x86_64.exe` | Windows x86_64 |
| `usbversal-macos-arm64` | macOS Apple Silicon |

Do not move a tag onto a later commit. If the build fails, fix on
`main` and tag the next patch. Leave old tags alone.

Release from `main` only.

## Local build

```bash
./scripts/setup-dev.sh
./scripts/build-release.sh
```

Writes `dist/usbversal` on Linux and macOS, `dist/usbversal.exe` on
Windows. Launch it. The TUI should open.

Opt-in packaging test:
`USBVERSAL_PACKAGING_BUILD=1 pytest tests/test_packaging_smoke.py`.

See [0003-use-pyinstaller.md](../decisions/0003-use-pyinstaller.md) and
[verification-workflow.md](verification-workflow.md).
