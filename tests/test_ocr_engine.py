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
        return
    result = ocr_engine.recognize_png(png)
    assert isinstance(result.text, str)
    assert result.engine in {"paddleocr", "rapidocr"}
    # Synthetic rendered text should be readable by RapidOCR at least
    if result.engine == "rapidocr":
        assert "Hello" in result.text
