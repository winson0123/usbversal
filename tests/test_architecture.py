"""Structural rules from ARCHITECTURE.md, enforced as tests."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

# Vendor libraries whose schema handling must stay behind an adapter.
VENDOR_MODULES = {"rbox", "serato_tools"}

# Layer -> packages it is allowed to import from (plus itself and stdlib/3rd-party).
ALLOWED_LAYER_IMPORTS = {
    "cli": {"jobs", "services", "core"},
    "jobs": {"services", "core", "storage", "adapters"},
    "services": {"core", "adapters", "storage"},
    "adapters": {"core", "storage"},
    "storage": {"core"},
    "core": set(),
}


def _imported_modules(path: Path) -> set[str]:
    """Return every module name imported by a Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _layer_of(path: Path) -> str:
    """Return the app layer a source file belongs to."""
    return path.relative_to(APP_ROOT).parts[0]


def _source_files() -> list[Path]:
    """Return every Python source file under app/."""
    return sorted(p for p in APP_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_vendor_libraries_only_imported_by_adapters() -> None:
    """rbox / serato-tools may only be imported inside app/adapters/."""
    offenders: list[str] = []
    for path in _source_files():
        if _layer_of(path) == "adapters":
            continue
        for module in _imported_modules(path):
            if module.split(".")[0] in VENDOR_MODULES:
                offenders.append(f"{path.relative_to(APP_ROOT.parent)} imports {module}")
    assert not offenders, "vendor imports outside app/adapters/:\n  " + "\n  ".join(offenders)


def test_layers_only_import_allowed_layers() -> None:
    """Each layer imports only the layers ARCHITECTURE.md permits."""
    offenders: list[str] = []
    for path in _source_files():
        layer = _layer_of(path)
        if layer not in ALLOWED_LAYER_IMPORTS:
            continue
        permitted = ALLOWED_LAYER_IMPORTS[layer] | {layer}
        for module in _imported_modules(path):
            parts = module.split(".")
            if parts[0] != "app" or len(parts) < 2:
                continue
            target = parts[1]
            if target not in permitted:
                offenders.append(f"{path.relative_to(APP_ROOT.parent)} ({layer}) imports {module}")
    assert not offenders, "layer violations:\n  " + "\n  ".join(offenders)


def test_no_adapter_imports_cli() -> None:
    """Adapters must never depend on the CLI."""
    for path in _source_files():
        if _layer_of(path) != "adapters":
            continue
        assert not any(m.startswith("app.cli") for m in _imported_modules(path)), path
