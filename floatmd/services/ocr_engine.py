"""OCR backends: PaddleOCR preferred, RapidOCR fallback."""

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


def _prep_paddle_runtime() -> None:
    # Mitigate OneDNN / PIR crashes on some CPU wheels.
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
    parts = []
    if paddle_available():
        parts.append("paddle")
    if rapid_available():
        parts.append("rapid")
    return "+".join(parts) if parts else "none"


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
    global _rapid
    with _lock:
        if _rapid is not None:
            return _rapid
        from rapidocr_onnxruntime import RapidOCR

        _rapid = RapidOCR()
        return _rapid


def _lines_from_paddle(raw) -> list[str]:
    lines: list[str] = []
    if raw is None:
        return lines

    # New paddlex Result objects / list thereof
    if isinstance(raw, list) and raw:
        first = raw[0]
        # Classic PP-OCR: [[box, (text, score)], ...]
        if isinstance(first, list):
            for item in first:
                try:
                    text = item[1][0]
                except Exception:
                    continue
                if text:
                    lines.append(str(text))
            return lines
        # predict() → list[Result]
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
        progress("加载 PaddleOCR…")
    ocr = _get_paddle()
    if progress:
        progress("Paddle 识别中…")

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
        progress("加载 RapidOCR…")
    engine = _get_rapid()
    if progress:
        progress("RapidOCR 识别中…")
    result, _elapse = engine(png_bytes)
    lines: list[str] = []
    if result:
        for item in result:
            # item: [box, text, score]
            try:
                lines.append(str(item[1]))
            except Exception:
                continue
    return OcrResult(text="\n".join(lines).strip(), engine="rapidocr")


def recognize_png(png_bytes: bytes, progress: Callable[[str], None] | None = None) -> OcrResult:
    if not png_bytes:
        raise OcrError("empty_image", "图片为空")

    errors: list[str] = []

    if paddle_available():
        try:
            return _recognize_paddle(png_bytes, progress)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"paddle: {exc}")
            if progress:
                progress(f"Paddle 失败，尝试备用引擎… ({exc})")

    if rapid_available():
        try:
            return _recognize_rapid(png_bytes, progress)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"rapid: {exc}")

    if not paddle_available() and not rapid_available():
        raise OcrError(
            "engine_missing",
            "未安装 OCR 引擎。请执行: pip install paddlepaddle paddleocr\n"
            "或备用: pip install rapidocr-onnxruntime",
        )

    raise OcrError(
        "recognize_failed",
        "所有 OCR 引擎均失败：\n" + "\n".join(errors),
    )
