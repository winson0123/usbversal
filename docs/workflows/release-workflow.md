# Release Workflow

**Status:** Linux one-file build via PyInstaller. Windows / macOS artifacts
are not built yet.

## Steps

1. Bump version in `pyproject.toml` if needed
2. Run verification (`pytest`, `ruff`)
3. Build: `./scripts/build-release.sh`
4. Smoke test: `./dist/usbversal` launches the TUI
5. Update `repository-state.json` `packaging.readiness`

## Build

```bash
./scripts/setup-dev.sh
./scripts/build-release.sh
```

Produces a one-file executable at `dist/usbversal` (about 43 MB on Linux).

Spec: [packaging/usbversal.spec](../../packaging/usbversal.spec)

## Automated smoke tests

| Test | When it runs |
|------|----------------|
| `test_pyinstaller_build` | When `USBVERSAL_PACKAGING_BUILD=1` |

## Pre-release gates

- [x] `ruff` and `pytest` pass
- [x] Linux one-file binary launches the TUI
- [ ] Windows artifact built and smoke-tested
- [ ] macOS artifact built and smoke-tested

## Related

- [../decisions/0003-use-pyinstaller.md](../decisions/0003-use-pyinstaller.md)
