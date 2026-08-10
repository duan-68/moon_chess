# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 月亮棋联机对战

使用方法:
    pyinstaller MoonChess.spec
    或运行 build_exe.bat
"""

import os
import sys

# 项目根目录 — 使用当前工作目录
_ROOT = os.getcwd()

a = Analysis(
    [os.path.join(_ROOT, "moon_chess", "__main__.py")],
    pathex=[_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "websockets",
        "websockets.legacy",
        "websockets.legacy.client",
        "websockets.legacy.server",
        "pygame",
    ],
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
    a.binaries,
    a.datas,
    [],
    name="MoonChess",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可添加 .ico 图标路径
)
