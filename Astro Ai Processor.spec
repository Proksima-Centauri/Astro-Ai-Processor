# -*- mode: python ; coding: utf-8 -*-

import sys

from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['Astro Ai Processor.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('favicon-32.png', '.'),
        ('loading.png', '.'),
        ('3d_fly_help.md', '.'),
    ],
    hiddenimports=collect_submodules('processing'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

is_windows = sys.platform == 'win32'
exe_options = dict(
    name='Astro AI Processor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    icon='favicon-32.png',
    console=sys.platform != 'win32',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if is_windows:
    # Bundle the interpreter and application assets into one Windows executable.
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_options)
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Astro AI Processor',
    )
