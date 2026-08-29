"""OCR: RapidOCR is the built-in default; PaddleOCR is optional if present."""

from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass
class OcrResult:
    text: str
    engine: str


@dataclass
class OcrError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


_lock = threading.Lock()
_paddle_ocr = None
_paddle_init_error: str | None = None
_rapid = None
_rapid_init_error: str | None = None


def _prep_paddle_runtime() -> None:
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        import paddle

        paddle.set_device("cpu")
        paddle.set_flags({"FLAGS_use_mkldnn": False})
    except Exception:
        pass


def paddle_available() -> bool:
    try:
        import paddle  # noqa: F401
        import paddleocr  # noqa: F401

        return True
    except Exception:
        return False


def rapid_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except Exception:
        return False


def engine_status() -> str:
    """Status string for UI (Rapid is the shipped default)."""
    if rapid_available():
        return "rapid+paddle" if paddle_available() else "rapid"
    if paddle_available():
        return "paddle"
    return "none"


def _get_paddle():
    global _paddle_ocr, _paddle_init_error
    with _lock:
        if _paddle_ocr is not None:
            return _paddle_ocr
        if _paddle_init_error:
            raise OcrError("init_failed", _paddle_init_error)
        _prep_paddle_runtime()
        try:
            from paddleocr import PaddleOCR

            attempts = [
                {
                    "lang": "ch",
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                },
                {"lang": "ch", "use_textline_orientation": True},
                {"lang": "ch", "use_angle_cls": True},
                {"lang": "ch"},
            ]
            last_exc: Exception | None = None
            for kwargs in attempts:
                try:
                    _paddle_ocr = PaddleOCR(**kwargs)
                    return _paddle_ocr
                except (TypeError, ValueError) as exc:
                    last_exc = exc
                    continue
            raise last_exc or RuntimeError("PaddleOCR init failed")
        except Exception as exc:  # noqa: BLE001
            _paddle_init_error = str(exc)
            raise OcrError("init_failed", str(exc)) from exc


def _get_rapid():
    global _rapid, _rapid_init_error
    with _lock:
        if _rapid is not None:
            return _rapid
        if _rapid_init_error:
            raise OcrError("init_failed", _rapid_init_error)
        try:
            from rapidocr_onnxruntime import RapidOCR

            _rapid = RapidOCR()
            return _rapid
        except Exception as exc:  # noqa: BLE001
            _rapid_init_error = str(exc)
            raise OcrError("init_failed", f"OCR 初始化失败：{exc}") from exc


def _lines_from_paddle(raw) -> list[str]:
    lines: list[str] = []
    if raw is None:
        return lines

    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, list):
            for item in first:
                try:
                    text = item[1][0]
                except Exception:
                    continue
                if text:
                    lines.append(str(text))
            return lines
        for item in raw:
            texts = None
            if hasattr(item, "rec_texts"):
                texts = item.rec_texts
            elif isinstance(item, dict) and "rec_texts" in item:
                texts = item["rec_texts"]
            elif hasattr(item, "get"):
                try:
                    texts = item.get("rec_texts")
                except Exception:
                    texts = None
            if texts:
                lines.extend(str(t) for t in texts if t)
        return lines

    if isinstance(raw, dict):
        for key in ("rec_texts", "texts", "text"):
            if key in raw and isinstance(raw[key], list):
                return [str(t) for t in raw[key] if t]
    return lines


def _recognize_paddle(png_bytes: bytes, progress: Callable[[str], None] | None) -> OcrResult:
    if progress:
        progress("加载 Paddle…")
    ocr = _get_paddle()
    if progress:
        progress("识别中…")

    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    arr = np.array(img)

    raw = None
    last_exc: Exception | None = None
    for method_name in ("predict", "ocr"):
        method = getattr(ocr, method_name, None)
        if method is None:
            continue
        try:
            if method_name == "ocr":
                try:
                    raw = method(arr, cls=True)
                except TypeError:
                    raw = method(arr)
            else:
                raw = method(arr)
            if raw is not None:
                break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue
    if raw is None:
        raise OcrError("recognize_failed", str(last_exc) if last_exc else "Paddle 无输出")

    lines = _lines_from_paddle(raw)
    return OcrResult(text="\n".join(lines).strip(), engine="paddleocr")


def _recognize_rapid(png_bytes: bytes, progress: Callable[[str], None] | None) -> OcrResult:
    if progress:
        progress("识别中…")
    engine = _get_rapid()
    result, _elapse = engine(png_bytes)
    lines: list[str] = []
    if result:
        for item in result:
            try:
                lines.append(str(item[1]))
            except Exception:
                continue
    return OcrResult(text="\n".join(lines).strip(), engine="rapidocr")


def recognize_png(png_bytes: bytes, progress: Callable[[str], None] | None = None) -> OcrResult:
    """Run OCR. Built-in path is RapidOCR; Paddle is used only if already installed."""
    if not png_bytes:
        raise OcrError("empty_image", "图片为空")

    errors: list[str] = []

    # Bundled default first — no external install required for end users.
    if rapid_available():
        try:
            return _recognize_rapid(png_bytes, progress)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rapid: {exc}")
            if progress:
                progress("内置 OCR 失败，尝试其它引擎…")

    if paddle_available():
        try:
            return _recognize_paddle(png_bytes, progress)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"paddle: {exc}")

    if not rapid_available() and not paddle_available():
        raise OcrError(
            "engine_missing",
            "OCR 组件未包含在当前程序中，请重新下载完整安装包。",
        )

    raise OcrError(
        "recognize_failed",
        "识别失败：" + ("；".join(errors) if errors else "未知错误"),
    )
