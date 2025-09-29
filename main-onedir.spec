# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['src/barks_reader/src', 'src/comic-utils/src', 'src/barks-fantagraphics/src', 'src/barks-build-comic-images/src'],
    binaries=[],
    datas= [ ('src/barks_reader/src/barks_reader', 'barks_reader'),
             ('src/barks-fantagraphics', 'barks-fantagraphics'),
             ('src/comic-utils', 'comic-utils'),
           ],
    hiddenimports=['comic_utils.loguru_setup'],
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
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
