# -*- mode: python ; coding: utf-8 -*-
"""Build independente do Fluxora para Windows 64 bits."""
from pathlib import Path
import shutil

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
node = shutil.which('node')
if not node:
    raise SystemExit('Node.js 22+ não encontrado. Instale-o antes de gerar a distribuição.')

datas = [(str(root / 'assets'), 'assets'), (str(root / 'THIRD_PARTY_NOTICES.txt'), '.')]
binaries = [(node, 'runtime')]
hiddenimports = []

for package in ('yt_dlp', 'yt_dlp_ejs', 'imageio_ffmpeg'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    ['main.py'],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Fluxora',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    icon=str(root / 'assets' / 'Fluxora.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Fluxora',
)
