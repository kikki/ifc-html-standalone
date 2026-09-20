from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
ifc_datas, ifc_binaries, ifc_hiddenimports = collect_all("ifcopenshell")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=ifc_binaries,
    datas=ifc_datas,
    hiddenimports=ifc_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

a.datas += Tree(str(ROOT / "dist"), prefix="dist")
a.datas += Tree(str(ROOT / "src" / "web"), prefix="src/web")
a.datas += Tree(str(ROOT / "src" / "node"), prefix="src/node")
a.datas += Tree(str(ROOT / "node_modules"), prefix="node_modules")

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IFC HTML Generator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="IFC HTML Generator",
)
