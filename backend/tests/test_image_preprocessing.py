"""
test_image_preprocessing.py — preprocess_prescription_image() 단위 테스트

배경: 스마트폰 카메라로 촬영한 처방전/약봉투 사진(조명 불균일·기울어짐·저해상도·
노이즈)의 CLOVA OCR 인식률을 높이기 위한 전처리 파이프라인. 핵심 설계 원칙은
"실패해도 OCR을 막지 않는다" — opencv 미설치나 디코딩 실패 시 원본 바이트를
그대로 반환해야 하므로, 이 테스트는 정상 동작뿐 아니라 그 폴백 경로를 반드시
함께 검증한다.
"""
from __future__ import annotations

import io
import sys

from services.image_preprocessing import preprocess_prescription_image


def _make_jpeg_bytes(width: int = 50, height: int = 50) -> bytes:
    """간단한 synthetic 이미지(회색 배경 + 검은 사각형 "글자")를 JPEG 바이트로 생성."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), color=(220, 220, 220))
    draw = ImageDraw.Draw(img)
    # 텍스트처럼 보이는 검은 픽셀 뭉치를 여러 개 그려 deskew의 텍스트-픽셀 최소 기준을 넘긴다
    for y in range(5, height - 5, 6):
        draw.rectangle([5, y, width - 5, y + 2], fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ── 정상 동작 ────────────────────────────────────────────────────────────────

def test_preprocess_returns_jpg_bytes_on_success():
    raw = _make_jpeg_bytes()
    processed_bytes, ext = preprocess_prescription_image(raw, "jpg")
    assert ext == "jpg"
    assert isinstance(processed_bytes, bytes)
    assert len(processed_bytes) > 0
    assert processed_bytes != raw  # 실제로 재인코딩/보정이 일어났어야 함


def test_preprocess_upscales_small_images():
    """긴 변이 _MIN_LONG_SIDE(1600) 미만인 저해상도 촬영본은 업스케일되어야 한다."""
    import cv2
    import numpy as np

    raw = _make_jpeg_bytes(width=50, height=40)
    processed_bytes, _ = preprocess_prescription_image(raw, "jpg")

    arr = cv2.imdecode(np.frombuffer(processed_bytes, dtype="uint8"), cv2.IMREAD_COLOR)
    assert arr is not None
    assert max(arr.shape[:2]) >= 1600


def test_preprocess_result_is_decodable_image():
    """전처리 결과가 다시 정상적으로 디코딩 가능한 유효 이미지여야 한다."""
    import cv2
    import numpy as np

    raw = _make_jpeg_bytes()
    processed_bytes, _ = preprocess_prescription_image(raw, "jpg")
    arr = cv2.imdecode(np.frombuffer(processed_bytes, dtype="uint8"), cv2.IMREAD_COLOR)
    assert arr is not None
    assert arr.ndim == 3  # 컬러 이미지(H, W, 3)


# ── 폴백 경로 — 실패해도 OCR을 막지 않아야 한다 ───────────────────────────────

def test_preprocess_falls_back_to_original_when_cv2_missing(monkeypatch):
    """opencv-python 미설치 환경을 흉내내면 원본 바이트/확장자를 그대로 반환한다."""
    monkeypatch.setitem(sys.modules, "cv2", None)  # `import cv2` 시 강제로 ImportError 발생
    raw = _make_jpeg_bytes()
    processed_bytes, ext = preprocess_prescription_image(raw, "jpg")
    assert processed_bytes == raw
    assert ext == "jpg"


def test_preprocess_falls_back_to_original_when_decode_fails():
    """이미지가 아닌 임의 바이트가 들어오면(디코딩 실패) 원본을 그대로 반환한다."""
    garbage = b"this is not an image file at all"
    processed_bytes, ext = preprocess_prescription_image(garbage, "png")
    assert processed_bytes == garbage
    assert ext == "png"


def test_preprocess_falls_back_to_original_when_a_single_step_raises(monkeypatch):
    """개별 보정 단계 하나가 예외를 던져도(예: deskew 실패) 전체 파이프라인이
    중단되지 않고 나머지 단계로 계속 진행해 결과를 반환해야 한다."""
    import services.image_preprocessing as mod

    def _boom(image, cv2):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(mod, "_deskew", _boom)
    raw = _make_jpeg_bytes()
    processed_bytes, ext = preprocess_prescription_image(raw, "jpg")
    assert ext == "jpg"
    assert isinstance(processed_bytes, bytes)
    assert len(processed_bytes) > 0
