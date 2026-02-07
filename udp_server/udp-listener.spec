# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_submodules, collect_data_files

a = Analysis(
    ['udp_listener.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('tzdata'),
    hiddenimports=(
        collect_submodules('requests')
        + collect_submodules('dotenv')
        + ['tzdata']
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='udp-listener',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='udp-listener',
)
