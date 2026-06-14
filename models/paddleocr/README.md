# PaddleOCR ONNX 模型目录

请将导出的 PaddleOCR ONNX 模型放在本目录，默认文件名：

- `det.onnx`：文本检测模型
- `rec.onnx`：文本识别模型
- `cls.onnx`：方向分类模型（可选，取决于 onnxocr 版本）

OCR 封装位于 `gameocr/ocr.py`，会通过 `onnxocr` 加载模型，并优先配置 OpenVINO Execution Provider/后端参数。