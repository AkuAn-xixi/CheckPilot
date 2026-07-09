# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('frontend\\dist', 'frontend\\dist'),
    ('backend\\test_cases', 'backend\\test_cases'),
]

binaries = []
hiddenimports = ['anyio', 'uvicorn', 'fastapi', 'starlette', 'pydantic', 'pandas', 'numpy', 'openpyxl', 'cv2', 'multipart']


def collect_package(package_name, required=True):
    global datas, binaries, hiddenimports
    try:
        tmp_ret = collect_all(package_name)
    except Exception as exc:
        if required:
            raise RuntimeError(f"[ADBControl.spec] required package is missing from the build environment: {package_name}") from exc
        print(f"[ADBControl.spec] optional package not collected: {package_name}")
        return

    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


for package_name in (
    'pydantic',
    'starlette',
    'pandas',
    'numpy',
    'openpyxl',
    'cv2',
    'multipart',
):
    collect_package(package_name)

# imageio + ffmpeg：采集卡录屏转换为浏览器兼容格式（H.264/VP8）
collect_package('imageio', required=True)
collect_package('imageio_ffmpeg', required=True)

# 可选：Windows 上用 pygrabber 列出 DirectShow 真实设备名
collect_package('pygrabber', required=False)
collect_package('comtypes', required=False)

datas = list(dict.fromkeys(datas))
binaries = list(dict.fromkeys(binaries))
hiddenimports = list(dict.fromkeys(hiddenimports))


a = Analysis(
    ['run_app.py'],
    pathex=['.', 'backend'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='ADBControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
