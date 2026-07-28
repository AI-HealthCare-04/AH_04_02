"""
image_preprocessing.py — 카메라로 직접 촬영한 처방전/약봉투 사진의 CLOVA OCR
인식률을 높이기 위한 전처리 파이프라인 (담당: 김영혜)

문제: 스캔본 수준의 원본 파일 업로드는 CLOVA OCR이 잘 인식하지만, 스마트폰
카메라로 촬영한 사진(조명 불균일, 약간의 기울어짐, 저해상도, 센서 노이즈)은
인식률이 크게 떨어진다. CLOVA OCR API 자체에는 전처리 옵션이 없으므로, 전송
전에 이미지를 직접 보정한다.

순서: EXIF 방향 보정 → 저해상도 업스케일 → 기울기 보정(deskew) → 조명 균일화
(CLAHE) → 노이즈 제거. 각 단계는 실패해도 예외를 던지지 않고 그 단계만
건너뛴다 — 전처리 파이프라인 전체가 깨져서 OCR 자체가 안 되는 것보다는, 일부
보정만 누락된 채로라도 원본이 그대로 전송되는 편이 안전하다(가장 바깥의
`preprocess_prescription_image()`도 opencv/Pillow 미설치나 디코딩 실패 시
원본 바이트를 그대로 반환한다).
"""
from __future__ import annotations

import io
import logging

_logger = logging.getLogger(__name__)

_MAX_DESKEW_ANGLE = 15.0  # 이보다 큰 회전은 오검출로 보고 적용하지 않음
_MIN_LONG_SIDE = 1600  # 촬영본 긴 변이 이보다 작으면 업스케일


def preprocess_prescription_image(image_bytes: bytes, original_ext: str) -> tuple[bytes, str]:
    """카메라 촬영 이미지를 CLOVA OCR에 보내기 전에 보정한다.

    Returns:
        (처리된 이미지 바이트, CLOVA에 보낼 format 문자열)
        보정에 성공하면 항상 JPEG로 재인코딩해 ("...", "jpg")를 반환하고,
        opencv/Pillow가 없거나 디코딩에 실패하면 (image_bytes, original_ext)를
        그대로 반환한다 — 이 경우 전처리 없이 원본이 전송될 뿐, OCR 자체는 계속 동작한다.
    """
    try:
        import cv2
    except Exception:  # noqa: BLE001 — opencv 미설치 환경에서도 OCR 자체는 동작해야 함
        _logger.warning("opencv-python 미설치 — 이미지 전처리 없이 원본 그대로 전송합니다.")
        return image_bytes, original_ext

    try:
        image = _decode_with_exif_orientation(image_bytes)
    except Exception:  # noqa: BLE001
        _logger.warning("이미지 디코딩 실패 — 원본 바이트 그대로 전송합니다.", exc_info=True)
        return image_bytes, original_ext

    try:
        image = _upscale_if_small(image, cv2)
    except Exception:  # noqa: BLE001
        _logger.warning("업스케일 단계 실패 — 건너뜁니다.", exc_info=True)

    try:
        image = _deskew(image, cv2)
    except Exception:  # noqa: BLE001
        _logger.warning("기울기 보정 실패 — 건너뜁니다.", exc_info=True)

    try:
        image = _normalize_illumination(image, cv2)
    except Exception:  # noqa: BLE001
        _logger.warning("조명 균일화 실패 — 건너뜁니다.", exc_info=True)

    try:
        image = _denoise(image, cv2)
    except Exception:  # noqa: BLE001
        _logger.warning("노이즈 제거 실패 — 건너뜁니다.", exc_info=True)

    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        _logger.warning("전처리 결과 인코딩 실패 — 원본 바이트 그대로 전송합니다.")
        return image_bytes, original_ext
    return encoded.tobytes(), "jpg"


def _decode_with_exif_orientation(image_bytes: bytes):
    """스마트폰 사진은 EXIF Orientation 태그로 실제 회전 방향을 담고 있는 경우가
    많다 — PIL로 먼저 EXIF를 반영해 정방향으로 만든 뒤 OpenCV(BGR) 배열로 변환한다."""
    import numpy as np
    from PIL import Image, ImageOps

    pil_image = Image.open(io.BytesIO(image_bytes))
    pil_image = ImageOps.exif_transpose(pil_image)  # EXIF 방향 태그를 실제 회전으로 반영
    pil_image = pil_image.convert("RGB")
    rgb_array = np.array(pil_image)
    return rgb_array[:, :, ::-1].copy()  # RGB -> BGR (OpenCV 관례)


def _upscale_if_small(image, cv2):
    """저해상도 촬영본(먼 거리에서 찍었거나 압축이 심한 경우) 작은 글씨 인식률을
    위해 긴 변 기준 `_MIN_LONG_SIDE` 이상으로 업스케일한다."""
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side >= _MIN_LONG_SIDE:
        return image
    scale = _MIN_LONG_SIDE / long_side
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _deskew(image, cv2):
    """텍스트 영역의 최소 회전 사각형(minAreaRect) 각도로 기울기를 추정해
    보정한다. 추정 각도가 비정상적으로 크면(`_MAX_DESKEW_ANGLE` 초과) 오검출로
    보고 회전을 적용하지 않는다 — 잘못된 큰 회전은 원본보다 인식률을 더
    떨어뜨릴 수 있다."""
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 텍스트가 배경보다 어둡다고 가정 — Otsu 이진화 후 반전(텍스트=흰색 픽셀)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(binary > 0))
    if coords.shape[0] < 100:  # 텍스트로 보이는 픽셀이 너무 적으면 각도 추정이 신뢰할 수 없음
        return image
    angle = cv2.minAreaRect(coords)[-1]
    # OpenCV minAreaRect 각도는 -90~0 범위로 나오므로 실제 기울기로 변환
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.3 or abs(angle) > _MAX_DESKEW_ANGLE:
        return image  # 너무 작으면 보정 불필요, 너무 크면 오검출로 간주하고 원본 유지
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _normalize_illumination(image, cv2):
    """조명이 불균일한 촬영본(그림자, 역광, 형광등 반사)의 명암비를 개선한다 —
    LAB 색공간의 명도(L) 채널에만 CLAHE(국소 대비 제한 히스토그램 평활화)를
    적용해 색상 왜곡 없이 밝기 대비만 보정한다."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _denoise(image, cv2):
    """스마트폰 카메라 센서 노이즈(저조도 촬영 시 두드러짐)를 제거하되, 글자
    경계는 보존해야 하므로 fastNlMeansDenoisingColored(비지역 평균 노이즈 제거)를
    쓴다."""
    return cv2.fastNlMeansDenoisingColored(image, None, h=7, hColor=7, templateWindowSize=7, searchWindowSize=21)
