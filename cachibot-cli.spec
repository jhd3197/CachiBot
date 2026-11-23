# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the standalone `cachi` CLI binary (terminal only).
# Built with the core package only (pip install -e .) — no server extras.
# Output: dist/cachi/cachi(.exe)

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

# Collect all cachibot submodules (CLI, agent, telemetry, etc.)
cachibot_submodules = collect_submodules('cachibot')

# Copy cachibot metadata so importlib.metadata.version("cachibot") works
cachibot_metadata = copy_metadata('cachibot')

# Platform-aware path separator
sep = os.sep

a = Analysis(
    [f'desktop{sep}pyinstaller-cli.py'],
    pathex=[],
    binaries=tukuy_binaries + prompture_binaries,
    datas=[
        ('cachibot', 'cachibot'),
        ('VERSION', 'cachibot'),
    ] + tukuy_datas + prompture_datas + cachibot_metadata,
    hiddenimports=[] + tukuy_hiddenimports + prompture_hiddenimports + cachibot_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Server-only dependencies (not installed with the core package)
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'aiosqlite',
        'asyncpg',
        'alembic',
        'pgvector',
        'websockets',
        'aiofiles',
        'multipart',
        'croniter',
        'bcrypt',
        'jwt',
        'cryptography',
        'numpy',
        'fastembed',
        'pymupdf',
        'fitz',
        'docx',
        'aiogram',
        'discord',
        'slack',
        'slack_sdk',
        'slack_bolt',
        'botbuilder',
        'aiohttp',
        # Heavy/irrelevant packages
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
    name='cachi',
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
    name='cachi',
)
