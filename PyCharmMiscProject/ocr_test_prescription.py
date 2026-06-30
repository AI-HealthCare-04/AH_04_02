"""
처방전 샘플 이미지 생성 + EasyOCR 한/영 인식 테스트
"""

import os
import re
import difflib
import cv2
import numpy as np
import easyocr
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SAMPLE_PATH  = "prescription_sample.png"
RESULT_PATH  = "prescription_result.png"
COMPARE_PATH = "prescription_compare.png"
KOREAN_FONT  = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

S = 2.0  # 렌더 스케일 (고해상도 생성으로 OCR 정확도 향상)

# 문자 수준 교정 맵: OCR이 자주 혼동하는 패턴을 직접 치환
CHAR_CORRECTIONS = {
    "캠술": "캡슐",   # ㅂ↔ㅁ 받침 혼동
    "캠슐": "캡슐",
    "캠쑬": "캡슐",
    "갭슐": "캡슐",
    "캡쑬": "캡슐",
}

# 단어 단위 도메인 사전 (유사도 매칭용)
DOMAIN_DICT = [
    # 서식 항목
    "처방전", "의료기관명", "요양기관번호", "전화번호", "처방일자",
    "환자명", "생년월일", "진료과목", "담당의사",
    "진단명", "상기도감염", "급성위염", "고혈압", "당뇨",
    "약품명", "용량", "용법", "투여일수", "수량",
    # 약품명
    "아목시실린캡슐", "이부프로펜정", "오메프라졸캡슐", "덱사메타손정",
    "아목시실린", "이부프로펜", "오메프라졸", "덱사메타손",
    # 제형
    "캡슐", "정", "주사", "시럽",
    # 용법
    "1일", "2회", "3회", "식후", "식전", "취침전", "즉시",
    "30분", "복용하십시오",
    # 기타
    "조제약국", "조제일", "약사확인", "담당의사", "서명",
]

CONF_THRESHOLD = 0.5


def s(v: float) -> int:
    return int(v * S)


def load_fonts() -> dict:
    try:
        bold = ImageFont.truetype(KOREAN_FONT, s(17), index=6)
        return {
            "title":   ImageFont.truetype(KOREAN_FONT, s(26)),
            "heading": ImageFont.truetype(KOREAN_FONT, s(18), index=4),  # SemiBold
            "body":    ImageFont.truetype(KOREAN_FONT, s(16)),
            "bold":    bold,
            "small":   ImageFont.truetype(KOREAN_FONT, s(13)),
            "tiny":    ImageFont.truetype(KOREAN_FONT, s(11)),
        }
    except OSError:
        f = ImageFont.load_default()
        return {k: f for k in ["title", "heading", "body", "bold", "small", "tiny"]}


def create_prescription(path: str) -> None:
    W, H = s(520), s(740)
    bg = (252, 252, 248)
    img = Image.new("RGB", (W, H), color=bg)
    draw = ImageDraw.Draw(img)
    f = load_fonts()

    def center(text, y, font, color=(20, 20, 20)):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), text, fill=color, font=font)

    def hline(y, lx=s(20), rx=None, color=(160, 160, 160), width=1):
        draw.line([(lx, y), (rx or W - s(20), y)], fill=color, width=width)

    def cell(text, x, y, w, font, color=(30, 30, 30), align="left"):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        if align == "center":
            draw.text((x + (w - tw) // 2, y), text, fill=color, font=font)
        elif align == "right":
            draw.text((x + w - tw, y), text, fill=color, font=font)
        else:
            draw.text((x, y), text, fill=color, font=font)

    # ── 상단 헤더 ──────────────────────────────────────────
    draw.rectangle([(0, 0), (W, s(60))], fill=(30, 80, 160))
    center("처  방  전", s(12), f["title"], color=(255, 255, 255))
    draw.text((s(22), s(16)), "건강보험", fill=(200, 220, 255), font=f["small"])
    draw.text((W - s(80), s(16)), "원본", fill=(200, 220, 255), font=f["small"])

    y = s(70)

    # ── 의료기관 정보 ──────────────────────────────────────
    draw.text((s(22), y), "의료기관명:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(100), y), "서울내과의원", fill=(20, 20, 20), font=f["heading"])
    draw.text((s(280), y), "요양기관번호:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(390), y), "12345678", fill=(20, 20, 20), font=f["body"])
    y += s(24)
    draw.text((s(22), y), "주        소:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(100), y), "서울시 강남구 테헤란로 456", fill=(20, 20, 20), font=f["body"])
    y += s(24)
    draw.text((s(22), y), "전화번호:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(100), y), "02-9876-5432", fill=(20, 20, 20), font=f["body"])
    draw.text((s(280), y), "처방일자:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(355), y), "2026-06-30", fill=(20, 20, 20), font=f["body"])
    y += s(18)
    hline(y)
    y += s(12)

    # ── 환자 정보 ──────────────────────────────────────────
    draw.text((s(22), y), "환 자 명:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(100), y), "홍길동", fill=(20, 20, 20), font=f["heading"])
    draw.text((s(220), y), "생년월일:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(300), y), "1985-03-15", fill=(20, 20, 20), font=f["body"])
    y += s(24)
    draw.text((s(22), y), "진료과목:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(100), y), "내과", fill=(20, 20, 20), font=f["body"])
    draw.text((s(220), y), "담당의사:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(300), y), "김민준 (면허번호: 56789)", fill=(20, 20, 20), font=f["body"])
    y += s(18)
    hline(y)
    y += s(12)

    # ── 진단명 ─────────────────────────────────────────────
    draw.rectangle([(s(20), y), (W - s(20), y + s(28))], fill=(235, 242, 255))
    draw.text((s(26), y + s(6)), "진  단  명:", fill=(30, 60, 140), font=f["heading"])
    draw.text((s(130), y + s(6)), "상기도감염 (J06.9),  급성위염 (K29.1)", fill=(20, 20, 20), font=f["body"])
    y += s(38)
    hline(y)
    y += s(14)

    # ── 처방 의약품 테이블 헤더 ────────────────────────────
    draw.text((s(22), y), "▣ 처방 의약품", fill=(30, 60, 140), font=f["heading"])
    y += s(26)

    COL = [s(22), s(170), s(265), s(355), s(430)]
    HEADERS = ["약  품  명", "용량(1회)", "1일 횟수", "투여일수", "용법"]
    col_w   = [s(148), s(90), s(88), s(73), s(68)]

    draw.rectangle([(s(20), y), (W - s(20), y + s(26))], fill=(210, 225, 255))
    for i, (hdr, cx, cw) in enumerate(zip(HEADERS, COL, col_w)):
        cell(hdr, cx, y + s(5), cw, f["bold"], color=(30, 60, 140), align="center")

    # 세로선
    for cx in COL[1:]:
        draw.line([(cx - s(2), y), (cx - s(2), y + s(26))], fill=(160, 180, 220), width=1)
    y += s(26)
    hline(y, color=(160, 180, 220), width=2)

    # 처방 항목
    meds = [
        ("아목시실린캡슐 500mg",  "500 mg",  "3회",  "5일", "식후 30분"),
        ("이부프로펜정 400mg",    "400 mg",  "3회",  "5일", "식후 30분"),
        ("오메프라졸캡슐 20mg",   "20 mg",   "2회",  "5일", "식전 30분"),
        ("덱사메타손정 0.5mg",    "0.5 mg",  "1회",  "3일", "식후 즉시"),
    ]
    row_colors = [(255, 255, 255), (245, 248, 255)]
    for ri, (name, dose, freq, days, method) in enumerate(meds):
        ry = y
        draw.rectangle([(s(20), ry), (W - s(20), ry + s(30))], fill=row_colors[ri % 2])
        values = [name, dose, freq, days, method]
        for i, (val, cx, cw) in enumerate(zip(values, COL, col_w)):
            align = "left" if i == 0 else "center"
            cell(val, cx, ry + s(7), cw, f["body"], align=align)
        for cx in COL[1:]:
            draw.line([(cx - s(2), ry), (cx - s(2), ry + s(30))], fill=(200, 210, 230), width=1)
        hline(ry + s(30), color=(200, 210, 230))
        y += s(30)

    hline(y, color=(100, 130, 200), width=2)
    y += s(16)

    # ── 복약 안내 ──────────────────────────────────────────
    draw.rectangle([(s(20), y), (W - s(20), y + s(108))], fill=(255, 250, 235), outline=(220, 190, 100), width=1)
    draw.text((s(26), y + s(8)),  "▣ 복약 안내",                             fill=(160, 100, 0), font=f["heading"])
    draw.text((s(26), y + s(30)), "• 1일 3회, 식후 30분에 복용하십시오.",          fill=(60, 40, 0),  font=f["body"])
    draw.text((s(26), y + s(50)), "• 오메프라졸은 식전 30분에 복용하십시오.",       fill=(60, 40, 0),  font=f["body"])
    draw.text((s(26), y + s(70)), "• 항생제(아목시실린)는 정해진 기간 동안 복용하십시오.", fill=(60, 40, 0), font=f["body"])
    draw.text((s(26), y + s(90)), "• 음주 및 카페인 섭취를 삼가십시오.",             fill=(60, 40, 0),  font=f["body"])
    y += s(118)

    # ── 하단 서명 ──────────────────────────────────────────
    hline(y)
    y += s(12)
    draw.text((s(22), y), "담당의사 서명:", fill=(80, 80, 80), font=f["small"])
    draw.text((s(130), y), "김민준", fill=(20, 20, 20), font=f["body"])
    # 도장 원
    cx, cy, r = W - s(60), y + s(8), s(18)
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(180, 30, 30), width=2)
    draw.text((cx - s(12), cy - s(9)), "직인", fill=(180, 30, 30), font=f["small"])
    y += s(26)
    draw.text((s(22), y), "위 처방대로 조제하여 주시기 바랍니다.", fill=(80, 80, 80), font=f["tiny"])

    img.save(path)
    print(f"[생성] 처방전 이미지 저장: {path}  크기: {W}×{H}")


def preprocess_for_ocr(path: str) -> None:
    img = Image.open(path)
    gray = img.convert("L")
    sharpened = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    sharpened.convert("RGB").save(path)
    print(f"[전처리] 언샵마스크 완료: {img.size}")


def run_ocr(image_path: str):
    print("[OCR] 모델 로딩 중...")
    reader = easyocr.Reader(["en", "ko"], gpu=False, verbose=False)
    return reader.readtext(
        image_path,
        mag_ratio=1.0,
        contrast_ths=0.05,
        adjust_contrast=0.7,
        width_ths=0.6,
        decoder="greedy",
    )


def fix_char_level(text: str) -> str:
    """문자 수준 교정: 캡슐 혼동, 숫자/알파벳 O 혼동."""
    # 캡슐 관련 혼동 패턴 직접 치환
    for wrong, right in CHAR_CORRECTIONS.items():
        text = text.replace(wrong, right)
    # 숫자 맥락의 알파벳 O → 숫자 0  (예: 50Omg → 500mg, 2Omg → 20mg)
    text = re.sub(r'(\d)O', r'\g<1>0', text)
    text = re.sub(r'O(\d)', r'0\1', text)
    return text


def fix_word_level(text: str, conf: float) -> str:
    """신뢰도가 낮은 항목을 단어 단위로 도메인 사전과 매칭해 교정."""
    if conf >= CONF_THRESHOLD:
        return text
    words = text.split()
    result = []
    changed = False
    for word in words:
        matches = difflib.get_close_matches(word, DOMAIN_DICT, n=1, cutoff=0.6)
        if matches and matches[0] != word:
            result.append(matches[0])
            changed = True
        else:
            result.append(word)
    return " ".join(result) if changed else text


def correct_results(results: list) -> list:
    corrected = []
    for bbox, text, conf in results:
        original = text

        # 1단계: 문자 수준 교정 (신뢰도 무관하게 항상 적용)
        text = fix_char_level(text)

        # 2단계: 단어 수준 사전 교정 (신뢰도 낮은 항목만)
        text = fix_word_level(text, conf)

        if text != original:
            print(f"  [교정] {original!r} → {text!r}  (신뢰도: {conf:.3f})")

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
        label_font = ImageFont.truetype(KOREAN_FONT, 16)
    except OSError:
        label_font = ImageFont.load_default()

    for bbox, text, conf in results:
        x, y = int(bbox[0][0]), int(bbox[0][1])
        draw.text((x, max(y - 18, 0)), f"{text}({conf:.2f})", fill=(200, 0, 0), font=label_font)

    img_pil.save(output_path)
    print(f"[저장] 결과 이미지: {output_path}")


def make_compare(left_path: str, right_path: str, out_path: str) -> None:
    left  = Image.open(left_path)
    right = Image.open(right_path)
    PAD, LABEL_H = 24, 50
    W = left.width + right.width + PAD * 3
    H = max(left.height, right.height) + LABEL_H + PAD * 2
    canvas = Image.new("RGB", (W, H), (220, 220, 220))
    canvas.paste(left,  (PAD, LABEL_H + PAD))
    canvas.paste(right, (left.width + PAD * 2, LABEL_H + PAD))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype(KOREAN_FONT, 26)
    except OSError:
        font = ImageFont.load_default()
    draw.text((PAD, 12), "샘플 이미지 (원본)", fill=(40, 40, 40), font=font)
    draw.text((left.width + PAD * 2, 12), "OCR 결과 이미지", fill=(40, 40, 40), font=font)
    canvas.save(out_path)
    print(f"[저장] 비교 이미지: {out_path}")


def main():
    create_prescription(SAMPLE_PATH)
    preprocess_for_ocr(SAMPLE_PATH)

    results = run_ocr(SAMPLE_PATH)

    print("\n=== OCR 원본 결과 ===")
    for i, (bbox, text, conf) in enumerate(results, 1):
        print(f"  [{i:2d}] {text!r:40s}  신뢰도: {conf:.3f}")

    print("\n=== 도메인 사전 교정 ===")
    results = correct_results(results)

    draw_results(SAMPLE_PATH, results, RESULT_PATH)
    make_compare(SAMPLE_PATH, RESULT_PATH, COMPARE_PATH)
    print(f"\n완료!")
    print(f"  샘플 이미지 : {os.path.abspath(SAMPLE_PATH)}")
    print(f"  결과 이미지 : {os.path.abspath(RESULT_PATH)}")
    print(f"  비교 이미지 : {os.path.abspath(COMPARE_PATH)}")


if __name__ == "__main__":
    main()
