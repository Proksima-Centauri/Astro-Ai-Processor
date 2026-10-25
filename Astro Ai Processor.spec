# -*- mode: python ; coding: utf-8 -*-

import sys
import tempfile
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
_skyshot_build_temp = tempfile.TemporaryDirectory(prefix="astro-skyshot-build-")
sys.path.insert(0, str(PROJECT_ROOT / "packaging"))
from build_skyshot import build_skyshot

skyshot_binary, skyshot_binary_notices = build_skyshot(PROJECT_ROOT, Path(_skyshot_build_temp.name))

a = Analysis(
    ['Astro Ai Processor.py'],
    pathex=[],
    binaries=[(str(skyshot_binary), ".")],
    datas=[
        ('assets', 'assets'),
        ('favicon-32.png', '.'),
        ('loading.png', '.'),
        ('NOTICE', '.'),
        ('LICENSE', '.'),
        ('docs/LICENSE-Skyshot-Apache-2.0.txt', 'licenses'),
        ('docs/NOTICE-Skyshot.txt', 'licenses'),
        ('third_party/skyshot/LICENSE', 'licenses/skyshot'),
        ('third_party/skyshot/NOTICE', 'licenses/skyshot'),
        ('third_party/skyshot/THIRD_PARTY_NOTICES.md', 'licenses/skyshot'),
        ('third_party/skyshot/docs/DATA.md', 'licenses/skyshot/data'),
        ('third_party/skyshot/docs/DATA-INSTALL.md', 'licenses/skyshot/data'),
        ('third_party/skyshot/docs/DATA-PROVENANCE.md', 'licenses/skyshot/data'),
        ('third_party/skyshot/docs/DATA-RELEASE.md', 'licenses/skyshot/data'),
        (str(skyshot_binary_notices), 'licenses/skyshot/third_party'),
        ('third_party/skyshot/tools/fetch_data.py', 'skyshot_runtime/tools'),
        ('third_party/skyshot/tools/data_bundle.py', 'skyshot_runtime/tools'),
        ('third_party/skyshot/tools/install_data.py', 'skyshot_runtime/tools'),
        ('third_party/skyshot/tools/model_bundle.py', 'skyshot_runtime/tools'),
        ('third_party/skyshot/tools/archive_utils.py', 'skyshot_runtime/tools'),
        ('third_party/skyshot/provenance/data-releases/2026.10.17.2/release.json',
         'skyshot_runtime/provenance/data-releases/2026.10.17.2'),
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
