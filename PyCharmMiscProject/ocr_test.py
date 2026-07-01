"""
EasyOCR + OpenCV OCR 테스트
- Pillow로 샘플 이미지 생성
- OpenCV로 이미지 전처리 (그레이스케일, 이진화)
- EasyOCR로 텍스트 추출
- 결과 이미지 저장
"""

import os
import cv2
import numpy as np
import easyocr
from PIL import Image, ImageDraw, ImageFont


SAMPLE_IMAGE_PATH = "sample_ocr_image.png"
RESULT_IMAGE_PATH = "sample_ocr_result.png"


def create_sample_image(path: str) -> None:
    """테스트용 샘플 이미지 생성."""
    img = Image.new("RGB", (640, 210), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    KOREAN_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    try:
        font_large = ImageFont.truetype(KOREAN_FONT, 36)
        font_small = ImageFont.truetype(KOREAN_FONT, 24)
    except OSError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((30, 20), "Hello, OCR World!", fill=(0, 0, 0), font=font_large)
    draw.text((30, 75), "EasyOCR + OpenCV 테스트", fill=(50, 50, 200), font=font_small)
    draw.text((30, 115), "안녕하세요! 한국어 인식 테스트입니다.", fill=(0, 120, 0), font=font_small)
    draw.text((30, 155), "Python 3.13  |  2026-06-30", fill=(200, 50, 50), font=font_small)

    img.save(path)
    print(f"[생성] 샘플 이미지 저장: {path}")


def preprocess_image(path: str) -> np.ndarray:
    """OpenCV로 이미지 전처리 (그레이스케일 + 이진화)."""
    img_bgr = cv2.imread(path)
    if img_bgr is None:
        raise FileNotFoundError(f"이미지를 불러올 수 없습니다: {path}")

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Otsu 이진화로 텍스트 대비 강화
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    print(f"[전처리] 원본 크기: {img_bgr.shape[:2]} → 그레이스케일 + Otsu 이진화 완료")
    return img_bgr, binary


def run_ocr(image_path: str) -> list[dict]:
    """EasyOCR로 텍스트 인식 후 결과 반환."""
    print("[OCR] 모델 로딩 중... (처음 실행 시 모델 다운로드 발생)")
    reader = easyocr.Reader(["en", "ko"], gpu=False, verbose=False)

    results = reader.readtext(image_path)
    return results


def draw_results(image_path: str, results: list, output_path: str) -> None:
    """인식 결과를 원본 이미지에 바운딩 박스 + 한글 라벨로 시각화."""
    # OpenCV로 바운딩 박스만 그린 뒤 Pillow로 변환해 한글 라벨 추가
    img_bgr = cv2.imread(image_path)
    for bbox, _, _ in results:
        pts = np.array(bbox, dtype=np.int32)
        cv2.polylines(img_bgr, [pts], isClosed=True, color=(0, 200, 0), thickness=2)

    img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    KOREAN_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
    try:
        label_font = ImageFont.truetype(KOREAN_FONT, 16)
    except OSError:
        label_font = ImageFont.load_default()

    for bbox, text, confidence in results:
        x, y = int(bbox[0][0]), int(bbox[0][1])
        label = f"{text} ({confidence:.2f})"
        draw.text((x, max(y - 20, 0)), label, fill=(220, 0, 0), font=label_font)

    img_pil.save(output_path)
    print(f"[저장] 결과 이미지 저장: {output_path}")


def main() -> None:
    # 1. 샘플 이미지 생성
    create_sample_image(SAMPLE_IMAGE_PATH)

    # 2. OpenCV 전처리
    original_bgr, binary = preprocess_image(SAMPLE_IMAGE_PATH)

    # 3. EasyOCR 실행 (원본 이미지 경로 전달)
    results = run_ocr(SAMPLE_IMAGE_PATH)

    # 4. 결과 출력
    print("\n=== OCR 결과 ===")
    if not results:
        print("인식된 텍스트가 없습니다.")
    for i, (bbox, text, confidence) in enumerate(results, 1):
        print(f"  [{i}] 텍스트: {text!r:30s}  신뢰도: {confidence:.3f}")

    # 5. 바운딩 박스 시각화 저장
    draw_results(SAMPLE_IMAGE_PATH, results, RESULT_IMAGE_PATH)

    print(f"\n완료! 결과 이미지: {os.path.abspath(RESULT_IMAGE_PATH)}")


if __name__ == "__main__":
    main()
