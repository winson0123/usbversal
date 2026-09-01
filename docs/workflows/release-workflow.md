# Release

A `v*` tag on `main` is the release. GitHub Actions builds a native
PyInstaller binary on Windows, macOS, and Linux and attaches them to a
GitHub Release. PyInstaller cannot cross-compile, so each artifact is
built on that OS.

There is no remote yet. Add one before the first tag.

```bash
git remote add origin git@github.com:<org>/usbversal.git
git push -u origin main
```

## Cut v1.0.0

`main` must be clean and at the commit you want to ship.

1. Set `version = "1.0.0"` in `pyproject.toml`.
2. Commit that bump on `main`. `[TASK-…] Release 1.0.0.`
3. Tag and push:

```bash
git tag -a v1.0.0 -m "Usbversal 1.0.0"
git push origin main
git push origin v1.0.0
```

4. The [Release](../../.github/workflows/release.yml) workflow runs
   `ruff` and `pytest` on Ubuntu, then PyInstaller on
   `ubuntu-latest`, `windows-latest`, and `macos-latest`, then
   `gh release create v1.0.0`.
5. The GitHub Release should have:

| Artifact | Built on |
|----------|----------|
| `usbversal-linux-x86_64` | Ubuntu x86_64 |
| `usbversal-windows-x86_64.exe` | Windows x86_64 |
| `usbversal-macos-arm64` | macOS Apple Silicon |

Do not move a tag onto a later commit. If the build fails, delete the
GitHub Release, fix on `main`, and tag `v1.0.1`. Leave the old tag
alone.

## Local build

```bash
./scripts/setup-dev.sh
./scripts/build-release.sh
```

Writes `dist/usbversal` on Linux and macOS, `dist/usbversal.exe` on
Windows. Launch it. The TUI should open.

Opt-in packaging test:
`USBVERSAL_PACKAGING_BUILD=1 pytest tests/test_packaging_smoke.py`.

## Later versions

Bump `pyproject.toml`, commit, tag `vX.Y.Z`, push the tag. Release
from `main` only.

See [0003-use-pyinstaller.md](../decisions/0003-use-pyinstaller.md) and
[verification-workflow.md](verification-workflow.md).
