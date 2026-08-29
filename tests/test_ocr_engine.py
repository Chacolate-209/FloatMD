from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from floatmd.services import ocr_engine


def _png_with_text() -> bytes:
    img = Image.new("RGB", (200, 60), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), "Hello", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_empty_image_rejected() -> None:
    with pytest.raises(ocr_engine.OcrError) as ei:
        ocr_engine.recognize_png(b"")
    assert ei.value.code == "empty_image"


def test_recognize_with_available_engine() -> None:
    png = _png_with_text()
    if not ocr_engine.paddle_available() and not ocr_engine.rapid_available():
        with pytest.raises(ocr_engine.OcrError) as ei:
            ocr_engine.recognize_png(png)
        assert ei.value.code == "engine_missing"
        assert "pip install" not in ei.value.message
        return
    result = ocr_engine.recognize_png(png)
    assert isinstance(result.text, str)
    assert result.engine in {"paddleocr", "rapidocr"}
    # Default path is RapidOCR
    if ocr_engine.rapid_available():
        assert result.engine == "rapidocr"
        assert "Hello" in result.text


def test_engine_missing_message_has_no_pip(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-user builds must not tell people to pip install."""
    monkeypatch.setattr(ocr_engine, "rapid_available", lambda: False)
    monkeypatch.setattr(ocr_engine, "paddle_available", lambda: False)
    png = _png_with_text()
    with pytest.raises(ocr_engine.OcrError) as ei:
        ocr_engine.recognize_png(png)
    assert ei.value.code == "engine_missing"
    assert "pip" not in ei.value.message.lower()
