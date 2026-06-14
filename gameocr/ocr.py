from __future__ import annotations

import importlib
import inspect
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np
from PIL import Image

from .config import OCRConfig


@dataclass
class OCRItem:
    text: str
    box: Tuple[int, int, int, int]
    confidence: float = 1.0


@dataclass
class OCRRunInfo:
    items: List[OCRItem]
    elapsed_ms: float
    backend: str
    error: Optional[str] = None


class OCRProcessor:
    """PaddleOCR ONNX wrapper with OpenVINO acceleration.

    The Python package named `onnxocr` has had several public APIs across
    releases/forks. This wrapper detects common class names and constructor
    signatures at runtime, so the GUI/business layer stays stable.

    OCR model is loaded once at application startup and reused for all frames.
    """

    _shared: Optional["OCRProcessor"] = None
    _shared_lock = threading.Lock()

    def __init__(self, config: OCRConfig):
        self.config = config
        self.engine: Any = None
        self.backend_name = "unloaded"
        self.openvino_devices: List[str] = []
        self.load_error: Optional[str] = None
        self._load()

    @classmethod
    def shared(cls, config: OCRConfig) -> "OCRProcessor":
        # QThreadPool workers may race during the first OCR trigger if startup
        # preloading failed/was skipped. Guard creation so the OpenVINO/PaddleOCR
        # model is still loaded exactly once and then reused for every frame.
        if cls._shared is None:
            with cls._shared_lock:
                if cls._shared is None:
                    cls._shared = cls(config)
        return cls._shared

    def _load(self) -> None:
        if self.config.use_openvino:
            os.environ.setdefault("ORT_OPENVINO_DEVICE_TYPE", self.config.device)
            os.environ.setdefault("ORT_OPENVINO_ENABLE_VPU_FAST_COMPILE", "1")
            try:
                try:
                    from openvino.runtime import Core  # type: ignore
                except Exception:
                    from openvino import Core  # type: ignore
                self.openvino_devices = list(Core().available_devices)
            except Exception:
                self.openvino_devices = []

        model_dir = Path(self.config.model_dir)
        candidates = [
            ("onnxocr.onnx_paddleocr", "ONNXPaddleOcr"),
            ("onnxocr.onnx_paddleocr", "PaddleOcrONNX"),
            ("onnxocr.paddleocr", "ONNXPaddleOcr"),
            ("onnxocr", "ONNXPaddleOcr"),
            ("onnxocr", "PaddleOcrONNX"),
            ("onnxocr", "OCR"),
        ]

        errors: List[str] = []
        for module_name, class_name in candidates:
            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                self.engine = self._instantiate_engine(cls, model_dir)
                ov_suffix = f" + OpenVINO({','.join(self.openvino_devices) or self.config.device})" if self.config.use_openvino else ""
                self.backend_name = f"{module_name}.{class_name}{ov_suffix}"
                return
            except Exception as exc:  # noqa: BLE001 - try next compatible public API
                errors.append(f"{module_name}.{class_name}: {exc}")

        self.load_error = (
            "无法加载 onnxocr PaddleOCR 模型。请确认 models/paddleocr 下存在 ONNX 模型，"
            "且 onnxocr 版本暴露 ONNXPaddleOcr/PaddleOcrONNX/OCR 类。\n"
            + "\n".join(errors[-4:])
        )
        self.backend_name = "load_failed"

    def _instantiate_engine(self, cls: type, model_dir: Path) -> Any:
        signature = inspect.signature(cls)
        params = signature.parameters

        kwargs = {}
        if "model_dir" in params:
            kwargs["model_dir"] = str(model_dir)
        if "det_model" in params:
            kwargs["det_model"] = str(model_dir / "det.onnx")
        if "rec_model" in params:
            kwargs["rec_model"] = str(model_dir / "rec.onnx")
        if "cls_model" in params:
            kwargs["cls_model"] = str(model_dir / "cls.onnx")
        if "use_angle_cls" in params:
            kwargs["use_angle_cls"] = True
        if "backend" in params:
            kwargs["backend"] = "openvino" if self.config.use_openvino else "onnxruntime"
        if "provider" in params:
            kwargs["provider"] = "OpenVINOExecutionProvider" if self.config.use_openvino else "CPUExecutionProvider"
        if "providers" in params:
            kwargs["providers"] = ["OpenVINOExecutionProvider"] if self.config.use_openvino else ["CPUExecutionProvider"]
        if "device" in params:
            kwargs["device"] = self.config.device if self.config.use_openvino else "CPU"

        if kwargs:
            return cls(**kwargs)

        # Last-resort constructors used by lightweight wrappers.
        try:
            return cls(str(model_dir))
        except TypeError:
            return cls()

    def recognize(self, image: Image.Image | np.ndarray, offset: Tuple[int, int] = (0, 0)) -> OCRRunInfo:
        start = time.perf_counter()
        if self.engine is None:
            return OCRRunInfo([], 0.0, self.backend_name, self.load_error or "OCR 引擎未加载")

        try:
            np_image = self._to_numpy(image)
            raw = self._call_engine(np_image)
            items = self._normalize_result(raw, offset)
            items = [item for item in items if item.text and item.confidence >= self.config.min_confidence]
            elapsed_ms = (time.perf_counter() - start) * 1000
            return OCRRunInfo(items, elapsed_ms, self.backend_name)
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start) * 1000
            return OCRRunInfo([], elapsed_ms, self.backend_name, f"OCR 推理失败: {exc}")

    def _call_engine(self, np_image: np.ndarray) -> Any:
        for method_name in ("ocr", "recognize", "infer", "predict", "__call__"):
            method = self.engine if method_name == "__call__" else getattr(self.engine, method_name, None)
            if callable(method):
                try:
                    if method_name == "ocr":
                        return method(np_image, cls=True)
                    return method(np_image)
                except TypeError:
                    return method(np_image)
        raise RuntimeError("onnxocr 对象未提供 ocr/recognize/infer/predict 调用接口")

    def _to_numpy(self, image: Image.Image | np.ndarray) -> np.ndarray:
        if isinstance(image, np.ndarray):
            array = image
            if array.ndim == 3 and array.shape[2] > 3:
                array = array[:, :, :3]
            if array.dtype != np.uint8:
                array = array.astype(np.uint8, copy=False)
            return np.ascontiguousarray(array)

        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.uint8)

    def _normalize_result(self, raw: Any, offset: Tuple[int, int]) -> List[OCRItem]:
        rows = self._flatten_rows(raw)
        result: List[OCRItem] = []
        for row in rows:
            parsed = self._parse_row(row, offset)
            if parsed:
                result.append(parsed)
        return result

    def _flatten_rows(self, raw: Any) -> List[Any]:
        if raw is None:
            return []
        if isinstance(raw, dict):
            if "results" in raw:
                return self._flatten_rows(raw["results"])
            if "data" in raw:
                return self._flatten_rows(raw["data"])
            if {"text", "box"}.issubset(raw.keys()):
                return [raw]
            return []
        if isinstance(raw, tuple):
            raw = list(raw)
        if not isinstance(raw, list):
            return []

        # PaddleOCR often returns [[line1, line2, ...]] for one image.
        if len(raw) == 1 and isinstance(raw[0], list) and raw[0] and self._looks_like_row(raw[0][0]):
            return raw[0]
        if raw and self._looks_like_row(raw[0]):
            return raw
        flattened: List[Any] = []
        for item in raw:
            if isinstance(item, list):
                flattened.extend(self._flatten_rows(item))
        return flattened

    def _looks_like_row(self, value: Any) -> bool:
        if isinstance(value, dict) and ("text" in value or "transcription" in value):
            return True
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return True
        return False

    def _parse_row(self, row: Any, offset: Tuple[int, int]) -> Optional[OCRItem]:
        ox, oy = offset
        if isinstance(row, dict):
            text = str(row.get("text") or row.get("transcription") or row.get("label") or "").strip()
            confidence = float(row.get("confidence") or row.get("score") or 1.0)
            box_raw = row.get("box") or row.get("points") or row.get("bbox")
            box = self._box_to_rect(box_raw, ox, oy)
            return OCRItem(text, box, confidence) if text and box else None

        if isinstance(row, (list, tuple)) and len(row) >= 2:
            box_raw = row[0]
            text_part = row[1]
            if isinstance(text_part, (list, tuple)):
                text = str(text_part[0]).strip() if text_part else ""
                confidence = float(text_part[1]) if len(text_part) > 1 else 1.0
            elif isinstance(text_part, dict):
                text = str(text_part.get("text") or text_part.get("transcription") or "").strip()
                confidence = float(text_part.get("confidence") or text_part.get("score") or 1.0)
            else:
                text = str(text_part).strip()
                confidence = float(row[2]) if len(row) > 2 and _is_number(row[2]) else 1.0
            box = self._box_to_rect(box_raw, ox, oy)
            return OCRItem(text, box, confidence) if text and box else None
        return None

    def _box_to_rect(self, box_raw: Any, ox: int, oy: int) -> Optional[Tuple[int, int, int, int]]:
        if box_raw is None:
            return None
        try:
            arr = np.array(box_raw, dtype=float)
            if arr.ndim == 1 and arr.size >= 4:
                values = arr.flatten().tolist()
                x1, y1, x2, y2 = values[:4]
                if x2 < x1 or y2 < y1:
                    xs = values[0::2]
                    ys = values[1::2]
                    x1, x2 = min(xs), max(xs)
                    y1, y2 = min(ys), max(ys)
            else:
                points = arr.reshape(-1, 2)
                x1, y1 = points.min(axis=0)
                x2, y2 = points.max(axis=0)
            return int(x1 + ox), int(y1 + oy), int(x2 + ox), int(y2 + oy)
        except Exception:
            return None


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False