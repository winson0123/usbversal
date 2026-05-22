# Release Workflow

**Status:** placeholder — PyInstaller not configured.

## Planned Steps

1. Bump version in `pyproject.toml`
2. Run full verification workflow
3. Build PyInstaller artifacts per platform
4. Smoke test binaries (`usbversal --help`)
5. Attach artifacts to GitHub release
6. Update `repository-state.json` `packaging.readiness`

## Build Commands (Future)

```bash
# Linux
pyinstaller packaging/usbversal.spec

# Windows (cross-build or native runner)
pyinstaller packaging/usbversal.spec
```

## Pre-Release Gates

- [ ] All ADR constraints satisfied
- [ ] Backup/rollback integration tests pass
- [ ] No writes without backup in code paths
- [ ] README CLI section matches actual commands

## Related

- [../decisions/0003-use-pyinstaller.md](../decisions/0003-use-pyinstaller.md)
