# Release Workflow

**Status:** implemented (Linux one-file build via PyInstaller)

## Steps

1. Bump version in `pyproject.toml` if needed
2. Run full verification workflow (`pytest`, `ruff`)
3. Build Linux binary: `./scripts/build-release.sh`
4. Smoke test: `./dist/usbversal` launches the TUI
5. Attach `dist/usbversal` to GitHub release (Windows build on native runner when available)
6. Update `repository-state.json` `packaging.readiness`

## Build

```bash
./scripts/setup-dev.sh
./scripts/build-release.sh
```

Produces a one-file executable at `dist/usbversal` (~16 MB on Linux; excludes unused serato-tools/librosa stack).

Spec: [packaging/usbversal.spec](../packaging/usbversal.spec)

## Automated smoke tests

| Test | When it runs |
|------|----------------|
| `test_packaging_spec_exists` | Always |
| `test_usbversal_binary_help` | When `dist/usbversal` exists (after build) |
| `test_pyinstaller_build_and_help` | When `USBVERSAL_PACKAGING_BUILD=1` (full CI release job) |

## Pre-release gates

- [x] Backup/rollback integration tests pass
- [x] No writes without backup in migration paths
- [x] README CLI section matches commands
- [ ] Windows artifact built and smoke-tested (manual / CI matrix)

## Related

- [../decisions/0003-use-pyinstaller.md](../decisions/0003-use-pyinstaller.md)
