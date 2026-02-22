# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'

# Strip debug symbols on Linux/macOS (saves ~10-20% binary size)
do_strip = not is_windows
# Disable UPX on Windows (causes antivirus false positives)
do_upx = not is_windows

# Collect tukuy and prompture (editable installs that PyInstaller can't trace)
tukuy_datas, tukuy_binaries, tukuy_hiddenimports = collect_all('tukuy')
prompture_datas, prompture_binaries, prompture_hiddenimports = collect_all('prompture')

# Collect all cachibot submodules (adapters, webhooks, telemetry, etc.)
cachibot_submodules = collect_submodules('cachibot')

# Copy cachibot metadata so importlib.metadata.version("cachibot") works
cachibot_metadata = copy_metadata('cachibot')

# Platform-aware path separator
sep = os.sep

a = Analysis(
    [f'desktop{sep}pyinstaller-server.py'],
    pathex=[],
    binaries=tukuy_binaries + prompture_binaries,
    datas=[
        ('cachibot', 'cachibot'),
        (f'frontend{sep}dist', f'cachibot{sep}frontend_dist'),
        ('VERSION', 'cachibot'),
    ] + tukuy_datas + prompture_datas + cachibot_metadata,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'asyncpg',
        'aiosqlite',
        'sqlite_vec',
        'fastembed',
        'cachibot.api.routes',
        'cachibot.plugins',
        'cachibot.services',
        'cachibot.storage',
    ] + tukuy_hiddenimports + prompture_hiddenimports + cachibot_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'scipy',
        'playwright',
        'gunicorn',
        'setuptools',
        'pip',
        'pytest',
        '_pytest',
        'fontTools',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='cachibot-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=do_strip,
    upx=do_upx,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64' if is_macos else None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=do_strip,
    upx=do_upx,
    upx_exclude=[],
    name='cachibot-server',
)
