# PyInstaller spec for Usbversal CLI (ADR 0003).
# Build from repo root: ./scripts/build-release.sh

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).resolve().parent
ENTRY = ROOT / "app" / "cli" / "__main__.py"

# Usbversal only uses crate + database_v2 from serato-tools (not librosa analysis tools).
hiddenimports = [
    *collect_submodules("app"),
    *collect_submodules("rbox"),
    "serato_tools.crate",
    "serato_tools.database_v2",
    "serato_tools.utils",
    "serato_tools.utils.bin_file_base",
    "serato_tools.utils.crate_base",
    "structlog",
    "structlog.dev",
    "structlog.processors",
    "structlog.stdlib",
    *collect_submodules("textual"),
]

# ADR 0009: textual loads its .tcss stylesheets as package resources, which
# PyInstaller's static import analysis does not see -- must be collected
# explicitly or a themed screen silently falls back to defaults in the
# packaged binary even though it works from source.
datas = [
    *collect_data_files("textual"),
]

excludes = [
    "librosa",
    "numba",
    "llvmlite",
    "scipy",
    "sklearn",
    "matplotlib",
    "pytest",
    "IPython",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT)],
    binaries=collect_dynamic_libs("rbox"),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="usbversal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
