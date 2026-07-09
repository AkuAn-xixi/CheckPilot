# ADBControl Lite (精简版)

## 打包大小对比

| 版本 | 大小 | 包含内容 |
|------|------|----------|
| **原版** | ~405 MB | 完整功能 |
| **精简版** | ~150 MB | 核心功能 |

## 功能对比

| 功能 | 原版 | 精简版 |
|------|------|--------|
| 采集卡录屏 | ✅ | ✅ |
| OpenCV 图像比对 | ✅ | ✅ |
| DINOv2 图像比对 | ✅ | ❌ |
| ASR 语音识别 | ✅ | ❌ |
| Excel 执行 | ✅ | ✅ |
| ADB 控制 | ✅ | ✅ |
| 报告生成 | ✅ | ✅ |

## 移除的依赖

| 包名 | 大小 | 说明 |
|------|------|------|
| PyTorch | 491.80 MB | 深度学习框架 |
| Transformers | 102.02 MB | HuggingFace 模型库 |
| SciPy | 110.58 MB | 科学计算 |
| llvmlite | 103.04 MB | LLVM 绑定 |
| SymPy | 59.08 MB | 符号计算 |
| nagisa | 45.38 MB | 日语 NLP |
| Gradio | 40.21 MB | Web UI |
| scikit-learn | 39.18 MB | 机器学习 |
| numba | 25.52 MB | JIT 编译 |
| NetworkX | 14.80 MB | 图计算 |
| librosa | 4.19 MB | 音频处理 |
| **合计** | **~1035 MB** | 压缩后节省 ~255 MB |

## 打包命令

```bash
# 精简版打包
build_exe_lite.bat

# 原版打包
build_exe.bat
```

## 输出文件

- 精简版：`dist/ADBControl_lite.exe`
- 原版：`dist/ADBControl.exe`

## 注意事项

1. **精简版不支持 DINOv2 图像比对**
   - 如果需要 DINOv2，请使用原版
   - 精简版仅支持 OpenCV 图像比对

2. **精简版不支持 ASR 语音识别**
   - 如果需要 ASR，请使用原版
   - 精简版无法执行语音识别相关功能

3. **前端 UI 仍然显示 DINOv2/ASR 选项**
   - 这些选项在精简版中不可用
   - 选择后会提示依赖缺失

## 适用场景

精简版适合以下场景：

- ✅ 只使用 OpenCV 进行图像比对
- ✅ 不需要语音识别功能
- ✅ 需要更小的打包体积
- ✅ 快速部署和分发
