"""
영수증 샘플 이미지 생성 + EasyOCR 한/영 인식 테스트
"""

import os
import difflib
import cv2
import numpy as np
import easyocr
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SAMPLE_PATH = "receipt_sample.png"
RESULT_PATH = "receipt_result.png"
KOREAN_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

# 렌더링 스케일: 1.0 기준(460×620)을 1.5배로 생성해 작은 글자 품질 향상
S = 2.0

# 도메인 사전: 영수증에 등장하는 알려진 단어 목록
DOMAIN_DICT = [
    "영수증", "맛있는", "한식당", "서울특별시", "강남구", "테헤란로",
    "주문번호", "일시", "테이블", "품목", "수량", "금액",
    "비빔밥", "된장찌개", "제육볶음", "공기밥", "서비스",
    "소계", "부가세", "합계", "결제수단", "신용카드",
    "카드번호", "승인번호", "감사합니다",
]
CONF_THRESHOLD = 0.5  # 이 미만이면 사전 교정 시도


def s(v: float) -> int:
    return int(v * S)


def load_fonts() -> dict:
    try:
        return {
            "title":  ImageFont.truetype(KOREAN_FONT, s(28)),
            "header": ImageFont.truetype(KOREAN_FONT, s(20)),
            "body":   ImageFont.truetype(KOREAN_FONT, s(22)),
            "small":  ImageFont.truetype(KOREAN_FONT, s(15)),
        }
    except OSError:
        f = ImageFont.load_default()
        return {"title": f, "header": f, "body": f, "small": f}


def create_receipt(path: str) -> None:
    W, H = s(460), s(660)
    img = Image.new("RGB", (W, H), color=(255, 253, 245))
    draw = ImageDraw.Draw(img)
    f = load_fonts()

    def center(text, y, font, color=(30, 30, 30)):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), text, fill=color, font=font)

    def divider(y, margin=s(30), color=(180, 170, 150)):
        draw.line([(margin, y), (W - margin, y)], fill=color, width=1)

    def row(label, value, y, font, lx=None, rx=None):
        lx = lx or s(30)
        rx = rx or W - s(30)
        draw.text((lx, y), label, fill=(50, 50, 50), font=font)
        vbbox = draw.textbbox((0, 0), value, font=font)
        draw.text((rx - (vbbox[2] - vbbox[0]), y), value, fill=(50, 50, 50), font=font)

    # 헤더
    center("[ 영수증 ]", s(20), f["title"])
    center("맛있는 한식당", s(58), f["header"])
    center("서울특별시 강남구 테헤란로 123", s(84), f["small"], (100, 100, 100))
    center("TEL: 02-1234-5678", s(104), f["small"], (100, 100, 100))
    divider(s(130))

    # 주문 정보
    draw.text((s(30), s(140)), "주문번호: #20260630-042", fill=(80, 80, 80), font=f["small"])
    draw.text((s(30), s(160)), "일시: 2026-06-30 12:45",  fill=(80, 80, 80), font=f["small"])
    draw.text((s(30), s(180)), "테이블: 3번",              fill=(80, 80, 80), font=f["small"])
    divider(s(205))

    # 메뉴 헤더
    draw.text((s(30),  s(215)), "품목", fill=(80, 80, 80), font=f["header"])
    draw.text((s(260), s(215)), "수량", fill=(80, 80, 80), font=f["header"])
    draw.text((s(360), s(215)), "금액", fill=(80, 80, 80), font=f["header"])
    divider(s(240))

    # 메뉴 항목
    items = [
        ("비빔밥",          "1", "12,000"),
        ("된장찌개",         "2", "18,000"),
        ("제육볶음",         "1", "13,000"),
        ("공기밥",          "3",  "3,000"),
        ("kimchi (서비스)", "-",      "0"),
    ]
    y = s(250)
    for name, qty, price in items:
        draw.text((s(30),  y), name, fill=(40, 40, 40), font=f["body"])
        draw.text((s(270), y), qty,  fill=(40, 40, 40), font=f["body"])
        pbbox = draw.textbbox((0, 0), price, font=f["body"])
        draw.text((W - s(30) - (pbbox[2] - pbbox[0]), y), price, fill=(40, 40, 40), font=f["body"])
        y += s(34)

    divider(y + s(5))
    y += s(15)
    row("소계",        "46,000원", y, f["body"])
    y += s(32)
    row("부가세(10%)", "4,600원",  y, f["body"])
    y += s(32)
    divider(y + s(5))
    y += s(14)

    # 총합계 강조
    draw.text((s(30), y), "합  계", fill=(20, 20, 20), font=f["header"])
    total = "50,600원"
    vbbox = draw.textbbox((0, 0), total, font=f["title"])
    draw.text((W - s(30) - (vbbox[2] - vbbox[0]), y - s(4)), total, fill=(180, 30, 30), font=f["title"])
    y += s(44)

    divider(y + s(5))
    y += s(15)

    # 결제 정보
    draw.text((s(30), y), "결제수단: 신용카드",             fill=(80, 80, 80), font=f["small"])
    y += s(22)
    draw.text((s(30), y), "카드번호: ****-****-****-1234", fill=(80, 80, 80), font=f["small"])
    y += s(22)
    draw.text((s(30), y), "승인번호: 78523691",            fill=(80, 80, 80), font=f["small"])
    y += s(30)
    divider(y)
    y += s(12)
    center("감사합니다. 또 오세요!", y, f["header"], (100, 80, 40))

    img.save(path)
    print(f"[생성] 영수증 이미지 저장: {path}  크기: {W}×{H}")


def preprocess_for_ocr(src_path: str, dst_path: str) -> str:
    """언샵마스크로 텍스트 경계 강화 (이미 고해상도이므로 업스케일 불필요)."""
    img = Image.open(src_path)
    gray = img.convert("L")
    sharpened = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    sharpened.convert("RGB").save(dst_path)
    print(f"[전처리] 언샵마스크 적용 완료: {img.size}")
    return dst_path


def run_ocr(image_path: str):
    print("[OCR] 모델 로딩 중...")
    reader = easyocr.Reader(["en", "ko"], gpu=False, verbose=False)
    return reader.readtext(
        image_path,
        mag_ratio=1.0,
        contrast_ths=0.05,
        adjust_contrast=0.7,
        width_ths=0.7,
        decoder="greedy",
    )


def correct_results(results: list) -> list:
    """신뢰도가 낮은 항목을 도메인 사전과 유사도 매칭으로 교정."""
    corrected = []
    for bbox, text, conf in results:
        if conf < CONF_THRESHOLD:
            matches = difflib.get_close_matches(text, DOMAIN_DICT, n=1, cutoff=0.5)
            if matches:
                print(f"  [교정] {text!r} → {matches[0]!r}  (원본 신뢰도: {conf:.3f})")
                text = matches[0]
        corrected.append((bbox, text, conf))
    return corrected


def draw_results(image_path: str, results: list, output_path: str) -> None:
    img_bgr = cv2.imread(image_path)
    for bbox, _, _ in results:
        pts = np.array(bbox, dtype=np.int32)
        cv2.polylines(img_bgr, [pts], isClosed=True, color=(0, 180, 0), thickness=2)

    img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    try:
        label_font = ImageFont.truetype(KOREAN_FONT, 15)
    except OSError:
        label_font = ImageFont.load_default()

    for bbox, text, confidence in results:
        x, y = int(bbox[0][0]), int(bbox[0][1])
        draw.text((x, max(y - 18, 0)), f"{text}({confidence:.2f})", fill=(200, 0, 0), font=label_font)

    img_pil.save(output_path)
    print(f"[저장] 결과 이미지 저장: {output_path}")


def main():
    create_receipt(SAMPLE_PATH)
    preprocess_for_ocr(SAMPLE_PATH, SAMPLE_PATH)  # 제자리 처리

    results = run_ocr(SAMPLE_PATH)

    print("\n=== OCR 원본 결과 ===")
    for i, (bbox, text, conf) in enumerate(results, 1):
        print(f"  [{i:2d}] {text!r:35s}  신뢰도: {conf:.3f}")

    print("\n=== 도메인 사전 교정 ===")
    results = correct_results(results)

    draw_results(SAMPLE_PATH, results, RESULT_PATH)
    print(f"\n완료! 결과 이미지: {os.path.abspath(RESULT_PATH)}")


if __name__ == "__main__":
    main()
