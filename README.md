# CheckPilot

CheckPilot 是一个面向 ADB 设备自动化测试的本地工作台，覆盖设备连接、即时指令执行、Excel 用例驱动、图片校验、ASR 语音校验、按键监听和客制化按键方案管理。项目以 FastAPI 提供后端 API，以 Vue 3 + Vite 提供前端工作台，也支持打包为 Windows 可执行程序。

## 核心能力

- 设备管理：自动发现在线 ADB 设备，持久化当前控制目标。
- 命令执行：支持按 `KEY/REPEAT/DELAY` 格式即时发送指令序列。
- Excel 工作区：将 Excel 执行拆分为图片校验执行和 ASR 校验执行两个入口。
- 图片校验执行：基于 Excel 行驱动设备操作、截图采集和校验图比对。
- ASR 校验执行：支持录音、转写、参考文本比对，以及 TTS 标记驱动的录音窗口。
- 按键监听：采集遥控器或设备按键序列，并支持纠正映射持久化。
- 客制化配置：按方案维护合法按键集合与 ADB keycode 映射。
- 打包运行：支持将前后端打包为单文件 exe，在运行目录直接工作。

## 技术栈

- 后端：FastAPI、Pydantic、Uvicorn
- 前端：Vue 3、Vue Router、Vite、Tailwind CSS
- 数据处理：pandas、openpyxl、numpy
- 图像处理：opencv-python-headless
- 设备控制：Android Debug Bridge (ADB)
- 可选 ASR：torch（CPU 版）、qwen-asr、transformers、sounddevice、librosa 等（已并入 requirements.txt，见下文）

## 项目结构

```text
.
├─ backend/                     FastAPI 后端
│  ├─ app/
│  │  ├─ api/                   设备、Excel、执行、ASR、客制化接口
│  │  ├─ services/              Excel、图像、ASR 服务
│  │  └─ utils/                 ADB、路径、校验工具
│  ├─ requirements.txt
│  ├─ main.py                   API 入口与前端静态资源挂载
│  └─ run.py                    开发模式后端启动脚本（端口 8003）
├─ frontend/                    Vue 3 + Vite 前端
│  ├─ src/views/                页面与 Excel 工作区
│  ├─ package.json
│  └─ vite.config.js            开发端口 3000，代理 /api 到 8003
├─ test_cases/                  运行期 Excel / 图片资源目录
├─ screenshots/                 图片校验截图输出目录
├─ asr_models/                  运行时导入的 ASR 模型目录
├─ Project/
│  ├─ Qwen/                     旧 ASR 原型模型资源
│  └─ voice_recorder_compare/   ASR 参考文本、录音和结果目录
├─ run_app.py                   一体化本地启动脚本
├─ build_exe.bat                一键打包脚本
└─ AutoDeck.spec              PyInstaller 配置
```

## 环境要求

- Python：建议 3.10 及以上；若需要稳定使用 ASR，推荐单独准备 Python 3.12 环境
- Node.js：建议 18+
- npm：建议 9+
- ADB：确保 `adb` 已安装并可在命令行直接使用
- Windows：打包和 exe 运行场景主要面向 Windows

## 安装依赖

### 1. 安装基础依赖

后端依赖：

```bash
pip install -r backend/requirements.txt
```

前端依赖：

```bash
cd frontend
npm install
```

### 2. 安装 ASR 依赖（已并入 requirements.txt）

ASR 录音与推理所需依赖已加入 `backend/requirements.txt`（`sounddevice` 起至 `tqdm` 止的段落）。其中 `torch` 需先从官方 CPU 源单独安装，否则 `pip install -r` 会从 PyPI 拉取体积巨大的 CUDA 版：

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r backend/requirements.txt
```

建议在 Python 3.12 环境中安装。`qwen-asr` 与 `transformers` + `librosa` 分别对应 Qwen3-ASR 和 Cohere Transcribe 两种模型后端，只使用一种后端时可删去另一种，以精简环境。ASR 页面会根据后端实际环境自动检测依赖状态，并在缺失时给出安装提示。安装完成后需要重启后端，再回到页面点击“刷新状态”。

## 启动方式

### 开发模式

1. 启动后端：

```bash
python backend/run.py
```

后端默认运行在 `http://localhost:8003`。

2. 启动前端：

```bash
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:3000`，并通过 Vite 代理将 `/api` 请求转发到 `http://localhost:8003`。

### 一体化本地运行

如果希望像打包版一样直接由后端提供前端静态页面：

1. 先构建前端：

```bash
cd frontend
npm run build
```

2. 回到项目根目录启动：

```bash
python run_app.py
```

脚本会自动寻找 8000 到 8010 之间的空闲端口，启动服务并打开浏览器。

## 功能入口

### 首页

- 展示当前设备状态和推荐入口。
- 若已选中设备，可直接进入 Excel 工作区。

### 设备管理

- 获取在线 ADB 设备列表。
- 选择当前控制设备。
- 当前设备断开后，系统会自动清理失效状态，避免继续返回陈旧设备信息。
- 设备列表在 1.5 秒内复用上一次的扫描结果：首页、设备页、Excel 页会同时拉取设备列表，连点刷新也常见，合并后只跑一次 `adb devices`。代价是刚拔插设备后立刻刷新，最多 1.5 秒后才反映变化。

### 命令执行

- 直接输入并执行命令序列。
- 基本格式：`KEYNAME/REPEAT/DELAY,KEYNAME/REPEAT/DELAY`
- `REPEAT` 支持随机次数：`X:(A:B)` 随机 A~B 次（A 下限、B 上限，A、B 均为 0 时本次跳过该指令，随机结果为 0 同样跳过）；`X:N` 为兼容写法，随机 1~N 次；仅 `X` 随机 1~DELAY 次（DELAY 取整，至少 1 次）。
- 示例：`HOME/1/1,DOWN/2/0.5,OK/1/1`，`OK/X:5/1`，`DOWN/X/3`

### Excel 工作区

- `/excel`：功能目录页，用于选择具体执行模块。
- `/excel/cases`：图片校验执行。
- `/excel/asr`：ASR 校验执行。

#### 图片校验执行

- 读取 Excel 文件并分析有效用例行。
- 驱动设备执行指令、保存截图、进行校验图比对。
- 支持结果回看与用例字段编辑。
- 校验占位指令：`Assert/1/1` 在当前位置截图校验，匹配即 PASS；`NotAssert/1/1` 为反向断言，截图**不匹配**目标图标才算 PASS（如确认弹窗/应用已关闭）。

#### ASR 校验执行

- 复用 Excel 文件分析和逐行执行能力。
- 支持导入运行时 ASR 模型并切换当前模型。
- 执行过程中可录音、转写、保存文本结果并做相似度比对。
- 支持“执行单行”“批量执行已选”“执行全部用例”。
- 支持 TTS 标记：当 Excel 指令中出现独立的 `TTS` 时，系统会在该标记处开始录音，并把下一条命令作为录音窗口内的触发命令。
- 当同名参考文本缺失或为空时，系统会回退为“识别文本 vs 捕获到的 TTS 文本”比对，而不是直接报错退出。
- 一行用例可含多个 `TTS` 段，行级结论为“全过才 PASS”：任一段 FAIL 即整行 FAIL。无法判定的段（缺参考文本、录音静音、识别复读热词）不参与判定，一行里只有这类段时记“无法判定”。界面徽标、Excel `testResult` 回填、批量报告三处同一口径。

### 按键监听

- 监听设备按键序列。
- 将监听到的错误 token 映射到合法按键后，映射关系会持久化，下次监听可直接输出纠正后的结果。

### 客制化配置

- 按方案维护合法按键名称集合。
- 按方案维护 keycode 映射覆盖。
- 激活方案会在运行时参与 Excel 校验与监听结果处理。

## Excel 与资源约定

### Excel 文件来源

- 支持 `.xlsx` 和 `.xls`。
- 可以通过页面上传。
- 也可以直接放在运行目录相关位置，由页面自动扫描。

### SmartTV 模板支持

当前实现重点兼容 SmartTV 风格 Excel：

- `runOption` 为 `Y` 的行才会进入执行链。
- 指令通常来自 `oriStep` 和 `preScript`。
- 命令格式为 `KEYNAME/REPEAT/DELAY`，多条命令以逗号分隔。
- 对空值/NaN 会在解析阶段做归一化处理，避免把 `nan` 当作真实命令执行。

### 指令别名（oriStep 工作表）

同一工作簿里可以额外放一张名为 `oriStep` 的工作表，把一段常用按键序列起个别名：

| oriStep | Key | DESCRIBE |
| --- | --- | --- |
| `OPENSETTING` | `HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1` | 打开Setting |
| `OPENHDMI2` | `HOME/1/5,SOURCE/1/1,DOWN/2/1,OK/1/1` | 打开HDMI2 |

- 表头列名必须是 `oriStep`（别名）与 `Key`（按键串），大小写与首尾空格不敏感；多出的列（如 `DESCRIBE`）会被忽略。
- `OSDCASE` 的 `oriStep` / `preScript` 列即可直接写别名，执行前自动展开成 `Key` 列的按键串。
- 支持逐段混写：`OPENSETTING,DOWN/1/1` 会展开成 4 条导航命令再追加一条 `DOWN/1/1`。
- 支持别名指向另一个别名（最多 5 层）；发现循环引用时保留原文并打告警日志，不会死循环。
- 别名匹配不区分大小写；`Key` 列的值保持原样（`X:(0:3)` 这类写法不受影响）。
- 逻辑名照这一列的写法补上次数/时间（`OPENCHILDCODE/1/3`）时后缀是**有含义**的：次数 = 整段按键串重复几遍，时间 = 整段跑完后、执行下一条命令前等多少秒。`OPENCHILDCODE/1/3` 即「跑一遍该导航，结束再等 3 秒」，展开为 `HOME/1/5,SETTING/1/1,DOWN/9/1,OK/1/1,DOWN/6/3`——秒数落在末条命令的延迟位上，因为对 `KEY/次数/延迟` 而言那一位本就是「发完这条之后等多久」，而末条发完正是整段结束的时刻。不写后缀则完全不影响展开结果。
- 后缀只认正整数次数与非负数字延迟：`X:(1:3)` 这类随机次数对「整段导航」没有明确定义，此时保留原文并记告警日志，交给既有的「未知按键 / 命令格式错误」报错路径；展开结果的末条若是不带延迟位的写法（如裸 `TTS`），秒数无处安放，同样记告警并忽略。
- 逻辑名与真实按键同名时以别名为准，后缀也照样生效（字典里若有 `HOME`，用例里的 `HOME/1/5` 会变成 `OK/1/5`），所以别名字典里不要出现与按键同名的逻辑名。
- **用例列表里的指令 chips 显示的是你写进 Excel 的原文**——逻辑名就显示成 `OPENCHILDCODE/1/3`，不会撑开成它展开后的那一串按键；鼠标悬停可以看到真正会发出去的命令。展开只发生在执行链路，Excel 文件、编辑弹窗回显、写回 Excel 都始终是原文，不会被改写成按键串。
- 执行中的高亮照旧按设备真正收到的按键名推进：一条逻辑名在展开序列里占连续几条，因此它内部任意一步跑到，整条 chip 都亮着并显示 `3/5` 这样的子步进度，而不是整条干亮着。
- 字典里没有的名字**不做特殊处理**，仍按原有的「未知按键 / 命令格式错误」报错。
- 找不到该工作表时功能自动关闭，老的用例文件行为完全不变。

### 图片校验资源

- 图片校验 Excel 用例一般放在 `test_cases/excel/`。
- 校验图一般放在 `test_cases/images/`。
- `verify-image` 字段支持三种来源：
	- 绝对本地路径
	- 相对 Excel 文件路径
	- 旧版 `test_cases/images/` 下的文件名
- 执行过程中的截图输出到 `screenshots/`。

### ASR 资源

- 运行时导入模型保存在 `asr_models/`。
- 当前激活模型信息写入 `asr_runtime_state.json`。
- 参考文本目录：`Project/voice_recorder_compare/references/`
- 录音输出目录：`Project/voice_recorder_compare/audio/`
- 转写和比对结果目录：`Project/voice_recorder_compare/results/`

## 打包部署

### 一键打包

在项目根目录运行：

```bat
build_exe.bat
```

脚本会自动完成：

- 通过国内镜像源安装前端依赖并执行生产构建
- 通过国内镜像源安装后端依赖和 PyInstaller
- 基于 `AutoDeck.spec` 构建单文件 exe

`build_exe.bat` 默认使用以下中国国内镜像源：

- `pip`：清华大学 PyPI 镜像 `https://pypi.tuna.tsinghua.edu.cn/simple`
- `npm`：`https://registry.npmmirror.com`
- `ADBCONTROL_PIP_INDEX_URL`：自定义 pip 镜像地址
- `ADBCONTROL_PIP_TRUSTED_HOST`：自定义 pip trusted-host
- `ADBCONTROL_NPM_REGISTRY`：自定义 npm registry

### 直接使用 PyInstaller

```bash
pyinstaller --clean --noconfirm AutoDeck.spec
```

构建产物位于：

```text
dist/AutoDeck.exe
```

### 打包后运行说明

- 启动 exe 后会自动打开浏览器。
- 前端页面由 FastAPI 直接挂载本地构建后的静态文件。
- 运行期目录默认为 exe 同级目录，以下文件会落在运行目录附近：
	- `screenshots/`
	- `test_cases/excel/`
	- `test_cases/images/`
	- `asr_models/`
	- `customization.json`
	- `monitor_key_mappings.json`
	- `runtime_state.json`
	- `asr_runtime_state.json`
	- `asr_text_substitutions.json`（ASR 文本替换规则）
	- `asr_hotwords.txt`（Qwen3-ASR 热词表，每行一词）

最后两项由 `build_exe.bat` 在打包完成后自动复制到 `dist\`。若绕过脚本直接调用 PyInstaller，需自行把它们放到 exe 同级目录：冻结后 `WORKING_DIR` 即 exe 所在目录，且读取这两个文件时没有包内回退，缺失只会静默导致规则失效（同一段录音在开发机与交付包上可能得出不同结论）。

## 常见问题

### 1. 未检测到 ADB 设备

- 确保设备已通过 USB 连接到电脑。
- 确保设备开启 USB 调试。
- 执行 `adb devices` 确认命令行已能看到设备。
- 必要时执行 `adb kill-server` 和 `adb start-server` 重启服务。

### 2. 前端能打开，但 API 请求失败

- 开发模式下请确认后端运行在 8003 端口。
- 请确认前端通过 `npm run dev` 启动，且 Vite 代理配置未被改动。

### 3. ASR 页面显示环境已就绪，但执行按钮仍被禁用

- 请先确认已选中 ADB 设备。
- 请先导入并选择一个运行时 ASR 模型。
- 如果刚安装完 ASR 依赖，请先重启后端，再回到页面点击“刷新状态”。

### 4. 运行 `run_app.py` 后页面空白

- 请先执行前端构建：`cd frontend && npm run build`。
- 一体化运行依赖 `frontend/dist` 目录被 FastAPI 挂载。

### 5. Excel 文件未显示

- 确保文件格式为 `.xlsx` 或 `.xls`。
- 可以直接通过页面上传，避免依赖手工放置路径。

## 许可证

MIT
