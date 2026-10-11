# -*- mode: python ; coding: utf-8 -*-

import importlib.util
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


llama_binaries = []
llama_hiddenimports = []
if importlib.util.find_spec('llama_cpp') is not None:
    llama_binaries = collect_dynamic_libs('llama_cpp')
    llama_hiddenimports = collect_submodules('llama_cpp')


a = Analysis(
    ['Astro Ai Processor.py'],
    pathex=[],
    binaries=llama_binaries,
    datas=[
        ('assets', 'assets'),
        ('favicon-32.png', '.'),
        ('3d_fly_help.md', '.'),
    ],
    hiddenimports=collect_submodules('processing') + llama_hiddenimports,
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Astro AI Processor',
)
