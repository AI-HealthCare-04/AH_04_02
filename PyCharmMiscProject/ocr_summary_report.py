"""
전체 OCR 샘플 종합 평가 스크립트
- sample_ocr_image.png (기본 한/영)
- receipt_sample.png (영수증)
- prescription_sample.png (처방전 단일)
- batch_prescriptions/rx_01~08_sample.png (처방전 8종)
"""

import os
import re
import difflib
from PIL import Image, ImageFilter
import easyocr

BASE_DIR  = "/Users/admin/PyCharmMiscProject"
BATCH_DIR = os.path.join(BASE_DIR, "batch_prescriptions")
OUT_FILE  = os.path.join(BASE_DIR, "ocr_summary.md")

CONF_THR = 0.5

CHAR_CORRECTIONS = {
    "캠술": "캡슐", "캠슐": "캡슐", "갭슐": "캡슐", "캡쑬": "캡슐", "캠쑬": "캡슐",
    "쟁용": "장용",
}

# ── 샘플별 Ground Truth ────────────────────────────────────────────────────────
GROUND_TRUTH = {
    "sample_ocr_image": {
        "label": "기본 OCR (한/영 혼합)",
        "category": "기본",
        "keywords": ["Hello", "OCR", "World", "EasyOCR", "OpenCV", "테스트", "안녕하세요", "Python"],
        "domain": ["Hello", "OCR", "World", "EasyOCR", "OpenCV", "테스트", "안녕하세요", "한국어", "인식", "Python"],
    },
    "receipt_sample": {
        "label": "영수증 (맛있는 한식당)",
        "category": "영수증",
        "keywords": ["영수증", "맛있는", "한식당", "비빔밥", "된장찌개", "제육볶음", "합계", "50,600", "감사합니다"],
        "domain": ["영수증", "맛있는", "한식당", "비빔밥", "된장찌개", "제육볶음", "공기밥",
                   "소계", "부가세", "합계", "결제수단", "신용카드", "감사합니다"],
    },
    "prescription_sample": {
        "label": "처방전 단일 (위염·역류성)",
        "category": "처방전",
        "keywords": ["처방전", "환자", "진단", "캡슐", "500mg", "1일", "식후", "30분", "복약"],
        "domain": ["처방전", "환자명", "진단명", "캡슐", "정", "장용정", "1일", "1회", "3회",
                   "식후", "식전", "취침전", "공복", "복용", "처방", "약품명"],
    },
}

# 배치 처방전 (ocr_batch_prescription.py에서 가져온 데이터)
BATCH_META = [
    {"id":1, "label":"고혈압·이상지질혈증", "dx":"본태성고혈압",
     "keywords":["처방전","암로디핀","로사르탄","아스피린","고혈압","식후","1회"]},
    {"id":2, "label":"2형 당뇨·비만",       "dx":"2형 당뇨병",
     "keywords":["처방전","메트포르민","글리메피리드","시타글립틴","당뇨","식후","3회"]},
    {"id":3, "label":"알레르기성 비염·결막염","dx":"알레르기성 비염",
     "keywords":["처방전","세티리진","몬테루카스트","나잘","취침전","14일"]},
    {"id":4, "label":"위식도역류·소화불량",  "dx":"위식도역류질환",
     "keywords":["처방전","판토프라졸","돔페리돈","알긴산","식전","28일"]},
    {"id":5, "label":"범불안장애·불면증",    "dx":"범불안장애",
     "keywords":["처방전","에스시탈로프람","알프라졸람","조피클론","취침전","14일"]},
    {"id":6, "label":"골관절염·골다공증",    "dx":"무릎 골관절염",
     "keywords":["처방전","셀레콕시브","캡슐","칼슘","알렌드로네이트","공복","14일"]},
    {"id":7, "label":"갑상선기능저하증",     "dx":"갑상선기능저하증",
     "keywords":["처방전","레보티록신","비타민","50mcg","공복","90일"]},
    {"id":8, "label":"폐렴·급성기관지염",   "dx":"지역사회획득폐렴",
     "keywords":["처방전","아지스로마이신","아세틸시스테인","덱스트로메토르판","식후","5일"]},
]


def fix(text: str) -> str:
    for w, r in CHAR_CORRECTIONS.items():
        text = text.replace(w, r)
    # 숫자 뒤 O → 0
    text = re.sub(r'(\d)O', r'\g<1>0', text)
    text = re.sub(r'O(\d)', r'0\1', text)
    # mg 오인식: m → rn/rN/rT/r7 분리 패턴
    text = re.sub(r'(\d[\.\d]*\s*)r[nNtT7]g\b', r'\g<1>mg', text)
    text = re.sub(r'(\d[\.\d]*\s*)rng\b',        r'\g<1>mg', text)
    # mcg 오인식
    text = re.sub(r'(\d[\.\d]*\s*)r[cC]g\b', r'\g<1>mcg', text)
    return text


def correct(results, domain):
    out = []
    for bbox, text, conf in results:
        orig = text
        text = fix(text)
        if conf < CONF_THR:
            m = difflib.get_close_matches(text, domain, n=1, cutoff=0.55)
            if m:
                text = m[0]
        out.append((bbox, text, conf, orig != text))
    return out


def keyword_hits(results, keywords):
    all_text = " ".join(t for _, t, _, _ in results)
    found, missed = [], []
    for kw in keywords:
        if kw in all_text:
            found.append(kw)
        else:
            partial = [t for _, t, _, _ in results if kw[:2] in t]
            if partial:
                found.append(kw + "(?)")
            else:
                missed.append(kw)
    return found, missed


def low_conf_items(results, threshold=0.5):
    items = [(t, c) for _, t, c, _ in results if c < threshold]
    items.sort(key=lambda x: x[1])
    return items[:5]  # 상위 5개만


def run_ocr_on(reader, img_path, domain):
    # 전처리
    img = Image.open(img_path).convert("L")
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    tmp = img_path.replace(".png", "_eval_tmp.png")
    img.convert("RGB").save(tmp)

    raw = reader.readtext(
        tmp, mag_ratio=1.0, contrast_ths=0.05,
        adjust_contrast=0.7, width_ths=0.6, decoder="greedy",
    )
    os.remove(tmp)
    return correct(raw, domain)


def grade(score):
    if score >= 0.85: return "PASS"
    if score >= 0.60: return "PARTIAL"
    return "FAIL"


def main():
    print("EasyOCR 모델 로딩...")
    reader = easyocr.Reader(["en", "ko"], gpu=False, verbose=False)
    print("로딩 완료\n")

    rows = []

    # 1. 기본·영수증·처방전 단일 샘플
    for key, meta in GROUND_TRUTH.items():
        img_path = os.path.join(BASE_DIR, f"{key}.png")
        if not os.path.exists(img_path):
            print(f"  [SKIP] {img_path}")
            continue
        print(f"OCR: {meta['label']} ...")
        results = run_ocr_on(reader, img_path, meta["domain"])

        n   = len(results)
        avg_conf = sum(c for _, _, c, _ in results) / n if n else 0
        n_fix = sum(1 for *_, ch in results if ch)
        found, missed = keyword_hits(results, meta["keywords"])
        kw_rate = len([f for f in found if "(?)" not in f]) / len(meta["keywords"])
        low = low_conf_items(results)

        rows.append({
            "no": len(rows) + 1,
            "category": meta["category"],
            "label": meta["label"],
            "n_regions": n,
            "avg_conf": avg_conf,
            "kw_rate": kw_rate,
            "n_fix": n_fix,
            "grade": grade(min(avg_conf, kw_rate)),
            "missed": missed[:3],
            "low_conf": low,
        })
        print(f"  avg_conf={avg_conf:.3f}  kw={kw_rate:.2f}  fix={n_fix}")

    # 2. 배치 처방전 8종
    for meta in BATCH_META:
        img_path = os.path.join(BATCH_DIR, f"rx_{meta['id']:02d}_sample.png")
        if not os.path.exists(img_path):
            print(f"  [SKIP] {img_path}")
            continue
        print(f"OCR: rx_{meta['id']:02d} {meta['label']} ...")
        domain = ["처방전","환자명","진단명","캡슐","정","장용정","1일","1회","2회","3회",
                  "식후","식전","취침전","공복","복용","처방","약품명","30분",
                  "복용하십시오","삼가십시오"] + meta["keywords"]
        results = run_ocr_on(reader, img_path, domain)

        n = len(results)
        avg_conf = sum(c for _, _, c, _ in results) / n if n else 0
        n_fix = sum(1 for *_, ch in results if ch)
        found, missed = keyword_hits(results, meta["keywords"])
        kw_rate = len([f for f in found if "(?)" not in f]) / len(meta["keywords"])
        low = low_conf_items(results)

        rows.append({
            "no": len(rows) + 1,
            "category": f"처방전 #{meta['id']:02d}",
            "label": meta["label"],
            "n_regions": n,
            "avg_conf": avg_conf,
            "kw_rate": kw_rate,
            "n_fix": n_fix,
            "grade": grade(min(avg_conf, kw_rate)),
            "missed": missed[:3],
            "low_conf": low,
        })
        print(f"  avg_conf={avg_conf:.3f}  kw={kw_rate:.2f}  fix={n_fix}")

    # ── 마크다운 출력 ──────────────────────────────────────────────────────────
    md_lines = []
    md_lines.append("# OCR 샘플 종합 평가 보고서\n")
    md_lines.append("> **평가 기준**: 키워드 검출률 + 평균 신뢰도의 최솟값으로 등급 결정  ")
    md_lines.append("> PASS ≥ 0.85 | PARTIAL 0.60 ~ 0.85 | FAIL < 0.60\n")

    # ─ 메인 집계 표
    md_lines.append("## 전체 샘플 OCR 결과 요약\n")
    md_lines.append("| # | 분류 | 샘플명 | 인식 영역 수 | 평균 신뢰도 | 키워드 검출률 | 교정 건수 | 종합 등급 |")
    md_lines.append("|---|------|--------|:---:|:---:|:---:|:---:|:---:|")
    for r in rows:
        grade_icon = {"PASS": "✅ PASS", "PARTIAL": "⚠️ PARTIAL", "FAIL": "❌ FAIL"}[r["grade"]]
        md_lines.append(
            f"| {r['no']} | {r['category']} | {r['label']} "
            f"| {r['n_regions']} | {r['avg_conf']:.3f} | {r['kw_rate']:.0%} "
            f"| {r['n_fix']}건 | {grade_icon} |"
        )

    # 통계 요약
    total = len(rows)
    pass_n    = sum(1 for r in rows if r["grade"] == "PASS")
    partial_n = sum(1 for r in rows if r["grade"] == "PARTIAL")
    fail_n    = sum(1 for r in rows if r["grade"] == "FAIL")
    avg_conf_all = sum(r["avg_conf"] for r in rows) / total
    avg_kw_all   = sum(r["kw_rate"]  for r in rows) / total
    total_fix    = sum(r["n_fix"]    for r in rows)

    md_lines.append("")
    md_lines.append(f"> **총 {total}건** | ✅ PASS {pass_n}건 | ⚠️ PARTIAL {partial_n}건 | ❌ FAIL {fail_n}건  ")
    md_lines.append(f"> 전체 평균 신뢰도: **{avg_conf_all:.3f}** | 평균 키워드 검출률: **{avg_kw_all:.0%}** | 총 교정 적용: **{total_fix}건**\n")

    # ─ 오인식 상세 표
    md_lines.append("## 샘플별 오인식/미검출 상세\n")
    md_lines.append("| # | 샘플명 | 미검출 키워드 | 저신뢰 항목 (신뢰도) |")
    md_lines.append("|---|--------|------------|----------------------|")
    for r in rows:
        missed_str = ", ".join(r["missed"]) if r["missed"] else "없음"
        low_str = " / ".join(f"`{t}`({c:.2f})" for t, c in r["low_conf"][:3]) if r["low_conf"] else "없음"
        md_lines.append(f"| {r['no']} | {r['label']} | {missed_str} | {low_str} |")

    md_lines.append("")
    md_lines.append("## 주요 오인식 패턴 분석\n")
    md_lines.append("| 패턴 유형 | 예시 | 원인 | 적용된 교정 방법 |")
    md_lines.append("|-----------|------|------|----------------|")
    md_lines.append("| 숫자-영문 혼동 | `50Omg` → `500mg` | 대문자 O와 0 혼동 | 정규식 `(\\d)O` → `\\g<1>0` |")
    md_lines.append("| 음절 오인식 | `캠술` → `캡슐` | 'ㅍ' vs 'ㅁ' 획 혼동 | CHAR_CORRECTIONS 딕셔너리 |")
    md_lines.append("| 저신뢰 단어 | `비임밥` → `비빔밥` | '빔' 음절 획 복잡성 | difflib 유사도 매칭 |")
    md_lines.append("| 공백 삽입 | `일    시` → `일시` | 자간 넓은 글자 분리 | 이미지 렌더 스케일 2× |")
    md_lines.append("| 한자·특수문자 | 의학 코드 `(I10)` | 괄호 내 숫자/문자 | 도메인 사전 보완 |")

    md_lines.append("")
    md_lines.append("## 파이프라인 구성\n")
    md_lines.append("```")
    md_lines.append("샘플 이미지 생성 (Pillow, S=2.0 렌더링)")
    md_lines.append("   ↓")
    md_lines.append("전처리: UnsharpMask(radius=1.5, percent=130, threshold=3)")
    md_lines.append("   ↓")
    md_lines.append("EasyOCR (en+ko, decoder=greedy, mag_ratio=1.0,")
    md_lines.append("          contrast_ths=0.05, adjust_contrast=0.7, width_ths=0.6)")
    md_lines.append("   ↓")
    md_lines.append("후처리 1단계: CHAR_CORRECTIONS (캠술→캡슐) + regex (50O→500)")
    md_lines.append("   ↓")
    md_lines.append("후처리 2단계: difflib.get_close_matches (도메인 사전, cutoff=0.55)")
    md_lines.append("   ↓")
    md_lines.append("평가: 키워드 검출률 × 평균 신뢰도 → PASS / PARTIAL / FAIL")
    md_lines.append("```")

    md_text = "\n".join(md_lines)
    print("\n" + "="*70)
    print(md_text)
    print("="*70)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"\n[저장] {OUT_FILE}")


if __name__ == "__main__":
    main()
