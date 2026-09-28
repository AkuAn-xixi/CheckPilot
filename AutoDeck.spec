# -*- mode: python ; coding: utf-8 -*-
"""AutoDeck 完整版打包配置：产出 dist/AutoDeck.exe（单文件）。

包含设备控制、Excel 执行、图片校验、采集卡录屏与 ASR 语音校验所需的全部依赖。
精简版 / TTS 版配置已废弃，只保留这一份。

用法（在项目根目录执行）::

    python -m PyInstaller --clean --noconfirm AutoDeck.spec

``build_exe.bat`` 会先构建前端，再调用本文件。
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files


PROJECT_ROOT = SPECPATH
FRONTEND_DIST_DIR = os.path.join(PROJECT_ROOT, "frontend", "dist")

# 前端产物缺失时打出来的 exe 每个页面都是 404。与其产出一个启动正常、界面打不开
# 的包，不如在构建阶段直接失败。
if not os.path.isdir(FRONTEND_DIST_DIR):
    raise SystemExit(
        f"未找到前端构建产物: {FRONTEND_DIST_DIR}\n"
        "请先执行 build_exe.bat，或在 frontend 目录执行 npm install && npm run build。"
    )

datas = [(FRONTEND_DIST_DIR, "frontend/dist")]

# 样例图片用例：path_resolver 会把 _MEIPASS/backend/test_cases 作为候选目录之一
_sample_cases_dir = os.path.join(PROJECT_ROOT, "backend", "test_cases")
if os.path.isdir(_sample_cases_dir):
    datas.append((_sample_cases_dir, "backend/test_cases"))

# 本地 ASR 用例与参考音频（Project/ 属于用户数据，不随仓库分发），存在才打包
for _sub_dir in ("case", "references"):
    _source_dir = os.path.join(PROJECT_ROOT, "Project", "voice_recorder_compare", _sub_dir)
    if os.path.isdir(_source_dir):
        datas.append((_source_dir, f"Project/voice_recorder_compare/{_sub_dir}"))

binaries = []

# 运行期靠字符串或反射取用的模块，静态分析看不到，必须显式声明
hiddenimports = [
    "anyio",
    "fastapi",
    "starlette",
    "pydantic",
    "multipart",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # 推理框架：DLL、子模块与元数据由 PyInstaller 自带的 hook-torch /
    # hook-transformers 收集，这里只保证模块进入依赖图。再叠一层 collect_all
    # 会让子模块被重复收集，构建时间成倍增长且产物更大。
    "torch",
    "transformers",
]

# 接口层、数据处理与 ASR 推理依赖。qwen_asr 没有官方 hook，漏收集只会在运行时
# 才报模块缺失，所以这些包统一用 collect_all 连带数据文件和子模块一起收。
REQUIRED_PACKAGES = (
    "pydantic",
    "starlette",
    "pandas",
    "numpy",
    "openpyxl",
    "cv2",
    "multipart",
    "sounddevice",
    "noisereduce",
    "scipy",
    "librosa",
    "soundfile",
    "qwen_asr",
    "huggingface_hub",
    "tqdm",
)

# pygrabber 用于读取采集卡 DirectShow 真实设备名，缺失时设备列表回退到索引扫描，
# 不影响主流程，因此按可选处理。
OPTIONAL_PACKAGES = ("pygrabber", "comtypes")


def collect_package(package_name, required=True):
    """收集单个包的数据文件、二进制与隐藏导入。

    Args:
        package_name: 包名。
        required: 为 True 时包缺失即中断构建。静默跳过会打出一个启动后才发现
            功能残缺的 exe，排查成本远高于构建期报错。

    Returns:
        ``(datas, binaries, hiddenimports)``；可选包缺失时返回三个空列表。
    """
    try:
        return collect_all(package_name)
    except Exception as exc:
        if required:
            raise RuntimeError(
                f"[AutoDeck.spec] 打包环境缺少必需依赖: {package_name}，"
                "请先执行 pip install -r backend/requirements.txt"
            ) from exc
        print(f"[AutoDeck.spec] 可选依赖未收集: {package_name}")
        return [], [], []


for _package_name in REQUIRED_PACKAGES + OPTIONAL_PACKAGES:
    _package_datas, _package_binaries, _package_hiddenimports = collect_package(
        _package_name, required=_package_name in REQUIRED_PACKAGES
    )
    datas += _package_datas
    binaries += _package_binaries
    hiddenimports += _package_hiddenimports

# ──────────────────────────────────────────────────────────────────────────────
# nagisa：必须连同 .py 源码一起落到包内同名目录
#
# qwen_asr 的 Qwen3ForcedAligner 依赖 nagisa 做日文分词。nagisa 的模块之间用顶层
# 名互相导入（tagger.py → train.py → ``import model`` / ``import prepro``），靠
# tagger.py 在导入时把自己所在目录 append 进 sys.path 才能解析；Tagger 的词表与
# 模型同样按 ``<包目录>/data`` 定位。只进 PYZ 时磁盘上没有这个目录，两个机制同时
# 失效，运行期 ``import qwen_asr`` 抛 ``No module named 'model'``，前端据此把
# qwen_asr 判为「缺少依赖」并拒绝执行。把源码与 data 收集到包内同名目录即可还原
# 源码运行时的目录布局。
# ──────────────────────────────────────────────────────────────────────────────
_nagisa_datas = collect_data_files("nagisa", include_py_files=True)
if not _nagisa_datas:
    raise RuntimeError(
        "[AutoDeck.spec] 打包环境缺少必需依赖: nagisa，"
        "请先执行 pip install -r backend/requirements.txt"
    )
datas += _nagisa_datas

# 同一个依赖会被多个包重复带出，去重后再交给 Analysis
datas = list(dict.fromkeys(datas))
binaries = list(dict.fromkeys(binaries))
hiddenimports = list(dict.fromkeys(hiddenimports))


a = Analysis(
    [os.path.join(PROJECT_ROOT, 'run_app.py')],
    pathex=[PROJECT_ROOT, os.path.join(PROJECT_ROOT, 'backend')],
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
    name='AutoDeck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # 不用 UPX：torch / OpenCV 的 DLL 压缩后偶发加载失败，而它们占了产物体积的
    # 绝大部分，压缩收益本来也有限。
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
