# AutoDeck TTS (ASR/TTS 专用版)

## 版本对比

| 版本 | 大小 | 主要功能 |
|------|------|----------|
| **原版** | ~405 MB | 完整功能 |
| **精简版** | ~108 MB | 采集卡、OpenCV 比对 |
| **TTS 版** | ~600 MB | ASR 语音识别、TTS |

## 包含的依赖

| 包名 | 大小 | 用途 |
|------|------|------|
| **PyTorch** | ~492 MB | 深度学习框架 |
| **Transformers** | ~102 MB | HuggingFace 模型库 |
| **qwen-asr** | ~50 MB | Qwen 语音识别 |
| **SciPy** | ~110 MB | 科学计算、音频重采样 |
| **librosa** | ~4 MB | 音频处理 |
| **nagisa** | ~45 MB | 日语 NLP |
| **soynlp** | ~10 MB | 韩语 NLP |
| **OpenCV** | ~108 MB | 图像处理 |
| **Pandas** | ~60 MB | Excel 处理 |

## 功能特性

### ✅ 支持的功能

- ASR 语音识别（Qwen3-ASR、Cohere Transcribe）
- TTS 文本捕获（从设备 logcat）
- 音频录制和处理
- 多语言支持（中英日韩）
- Excel 数据处理
- 报告生成

### ❌ 不支持的功能

- DINOv2 图像比对（已移除）
- FFmpeg 视频转换（已移除）
- 采集卡录屏（已移除）

## 打包命令

```powershell
# PowerShell 运行
.\build_tts.ps1

# 或使用批处理
build_tts.bat
```

## 输出文件

```
dist\AutoDeck_tts.exe (~600 MB)
```

## 运行要求

### 硬件要求

- **内存**: 8GB+（推荐 16GB）
- **存储**: 2GB+ 可用空间
- **CPU**: 支持 AVX2 的现代处理器

### 模型文件

需要下载 ASR 模型到 `asr_models/` 目录：

```bash
# 模型目录结构
asr_models/
├── Qwen3-ASR/          # Qwen 语音识别模型
│   ├── config.json
│   ├── model.bin
│   └── tokenizer.json
└── Cohere-Transcribe/  # Cohere 转录模型
    ├── config.json
    ├── model.bin
    └── preprocessor_config.json
```

## 使用方法

### 1. 启动应用

```bash
dist\AutoDeck_tts.exe
```

### 2. 访问界面

```
http://localhost:8000
```

### 3. 配置 ASR

1. 进入 "ASR 自动化" 页面
2. 选择 ASR 后端（Qwen3-ASR 或 Cohere）
3. 配置语言和参数
4. 上传测试音频或实时录制

### 4. 执行测试

1. 上传 Excel 测试用例
2. 选择需要执行的用例
3. 点击 "开始执行"
4. 查看识别结果和报告

## ASR 命令格式

### Excel 中的 TTS 标记

```
| testID | commands                          |
|--------|-----------------------------------|
| TC001  | HOME/1/1,TTS,OK/1/1               |
| TC002  | HOME/1/1,TTS,RIGHT/1/1,TTS,OK/1/1 |
```

- `TTS` 标记表示在此处等待设备 TTS 输出
- 系统会自动捕获 TTS 文本用于比对

### 命令格式

```
KEYNAME/REPEAT/DELAY
```

- `KEYNAME`: 按键名称（HOME、OK、BACK 等）
- `REPEAT`: 重复次数；支持随机值，`X:(A:B)` 随机 A~B 次（A、B 均为 0 时跳过该指令），`X:N` 随机 1~N 次，仅 `X` 随机 1~DELAY 次（DELAY 取整，至少 1 次）
- `DELAY`: 延迟时间（秒）

## 常见问题

### Q: 模型下载失败？

```bash
# 使用镜像源
export HF_ENDPOINT=https://hf-mirror.com
# 或
export HF_ENDPOINT=https://huggingface.sukaka.top
```

### Q: 内存不足？

```bash
# 使用较小的模型
# 或减少 batch_size
```

### Q: 识别不准确？

1. 检查音频质量（16kHz、单声道）
2. 调整语言参数
3. 使用更精确的模型

## 相关链接

- [Qwen3-ASR 文档](https://github.com/QwenLM/Qwen3-ASR)
- [Transformers 文档](https://huggingface.co/docs/transformers)
- [PyTorch 文档](https://pytorch.org/docs)
