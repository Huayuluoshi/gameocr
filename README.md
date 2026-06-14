# 游戏屏幕 OCR 实时翻译工具

基于 Python + PyQt5 的游戏画面 OCR 实时翻译工具。项目按需求拆分为 OCR/OpenVINO、翻译后端、全局热键、截图选区、半透明悬浮窗、实时循环与 GUI 配置持久化等模块。

## 已实现能力

- 单一全局触发热键：默认 `F1`
- GUI 中使用单选框选择翻译范围：整页/全屏 OCR 或选区 OCR，默认整页翻译
- GUI 中使用单选框选择执行模式：实时循环翻译或单次翻译，默认实时翻译
- PyQt5 可视化配置面板
- 系统托盘后台常驻
- 置顶、无边框、半透明、不抢焦点译文悬浮窗，默认显示在原文字正下方，宽度按译文内容自适应，尽量展开但不超过原文框宽度
- 配置 JSON 持久化：`%USERPROFILE%\.gameocr\config.json`
- OCR 模型启动时加载一次，运行期复用
- 多线程执行截图、OCR、翻译，避免阻塞 GUI
- 可选目标游戏窗口截图：通过 Windows `PrintWindow` 后台截取指定窗口，实时刷新时无需临时隐藏译文悬浮窗，可减少闪烁
- 翻译抽象层，支持以下后端：
  - 谷歌翻译（默认）
  - 百度翻译 API
  - 腾讯翻译君/腾讯云机器翻译 API
  - OpenAI 兼容格式 LLM API
  - Ollama 本地大模型

## 安装

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## PaddleOCR ONNX 模型目录

默认读取：

```text
models/paddleocr/
  det.onnx
  rec.onnx
  cls.onnx
```

`onnxocr` 不同发行版的类名和构造参数存在差异，本项目的 `gameocr/ocr.py` 已做运行时适配，会优先尝试 OpenVINO/ONNXRuntime OpenVINO Provider。若你的 `onnxocr` 包要求其他模型文件名，请调整 `gameocr/config.py` 中的 `OCRConfig.model_dir` 或 `OCRProcessor._instantiate_engine()`。

## 运行

```bat
python -m gameocr.main
```

首次启动会加载 OCR 模型并注册全局热键。

## 使用说明

1. 在 GUI 中选择翻译引擎与源/目标语言。
2. 按需填写 API 密钥或接口配置。
3. 如需减少实时翻译闪烁，可在“截图目标设置”中点击“刷新窗口列表”，选择目标游戏窗口后保存；保持默认则使用桌面全屏截图。部分游戏窗口没有标准标题，会以 `[无标题] 类名 #窗口句柄` 的形式出现在列表中。
4. 在“快捷键与执行模式”中设置单一触发热键，并通过单选框选择翻译范围（默认整页）与执行模式（默认实时）。
5. 点击“保存配置”，热键即时生效。
6. 游戏中按触发热键（默认 `F1`）：
   - 翻译范围为“整页/全屏”时，执行全屏 OCR 翻译。
   - 翻译范围为“选区”时，首次触发进入鼠标框选；实时模式会复用上次选区循环刷新。
   - 再次按触发热键会停止当前任务并清空悬浮窗。
7. 若选择实时模式，触发后会按设定间隔循环刷新。

## 翻译引擎配置提示

### 谷歌翻译

无需密钥，无需在程序内填写代理；但需要当前网络环境能够访问 Google 翻译服务才能使用。

如果已经通过 V2RayN 系统代理、TUN 模式、全局代理或其他网络方式访问 Google，程序会直接使用当前网络环境。若当前网络无法访问 Google 翻译，请先在系统或网络层面配置可用访问环境。

### 百度翻译 API

填写百度翻译开放平台的 APP ID 和密钥。

申请/控制台地址：

```text
https://fanyi-api.baidu.com/
```

### 腾讯翻译 API

填写腾讯云 SecretId、SecretKey 和 Region（默认 `ap-shanghai`）。

产品/控制台入口：

```text
https://cloud.tencent.com/product/tmt
```

### OpenAI 兼容 API

接口地址默认使用 Chat Completions 格式，例如：

```text
https://api.openai.com/v1/chat/completions
```

兼容中转、自建服务、LiteLLM、One API 等 OpenAI 风格接口。

### Ollama

官网地址：

```text
https://ollama.com/
```

默认服务地址：

```text
http://127.0.0.1:11434
```

默认模型：`gemma4:31b-cloud`

本地部署示例：

```bat
ollama pull gemma4:31b-cloud
ollama serve
```

## 打包 EXE

安装依赖后执行：

```bat
pyinstaller gameocr.spec
```

输出目录：

```text
dist/GameOCRTranslator.exe
```

如需内置模型，请将 ONNX 模型放入 `models/paddleocr` 后再打包。程序图标位于 `assets/gameocr.ico`，打包时会自动作为 EXE 图标并内置到运行资源中；`assets/gameocr_icon.png` 可用于预览或文档展示。图标采用圆角背景设计，如需重新生成可执行 `python tools\generate_icon.py`。

## 开发/验证

```bat
python -m compileall gameocr tests
pytest
```

## 注意事项

- 全屏独占游戏可能限制普通桌面截图和覆盖层显示；建议优先使用无边框窗口或窗口化全屏。
- 目标窗口截图依赖 Windows `PrintWindow` 与 `pywin32`。部分 DirectX/Vulkan 游戏、受保护窗口或最小化窗口可能返回黑屏/失败，此时请改用默认桌面截图或窗口化/无边框窗口模式。
- 如果“刷新窗口列表”显示可选窗口为 0，请确认游戏没有最小化、`pywin32` 已正确安装；若游戏以管理员权限运行，也需要以管理员权限启动本程序。无标题游戏窗口会按窗口类名和句柄列出，游戏重启后句柄可能变化，需要重新选择并保存。
- 高频刷新会增加 OCR 与翻译后端压力，建议从默认 `0.5s` 开始调优。
- API 错误、网络超时、无文字、空选区、Ollama 未启动等异常会写入日志，不会中断主程序。