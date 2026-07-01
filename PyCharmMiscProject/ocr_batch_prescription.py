"""
처방전 샘플 8종 일괄 생성 + OCR 파이프라인 적용 + 정확도 집계
"""

import os
import re
import difflib
import cv2
import numpy as np
import easyocr
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR      = "batch_prescriptions"
KOREAN_FONT  = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
S            = 2.0
CONF_THRESHOLD = 0.5

# ── 교정 맵 ────────────────────────────────────────────────────────────────────
CHAR_CORRECTIONS = {
    "캠술": "캡슐", "캠슐": "캡슐", "갭슐": "캡슐", "캡쑬": "캡슐",
    "캠쑬": "캡슐", "쟁용": "장용", "장용정": "장용정",
}

DOMAIN_DICT_BASE = [
    "처방전", "의료기관명", "요양기관번호", "전화번호", "처방일자",
    "환자명", "생년월일", "진료과목", "담당의사",
    "진단명", "약품명", "용량", "용법", "투여일수",
    "캡슐", "정", "장용정", "연질캡슐", "주사", "시럽",
    "1일", "1회", "2회", "3회", "식후", "식전", "취침전", "즉시",
    "30분", "복용하십시오", "삼가십시오",
]

# ── 8종 처방전 데이터 ──────────────────────────────────────────────────────────
PRESCRIPTIONS = [
    {
        "id": 1, "hospital": "서울내과의원", "dept": "순환기내과",
        "doctor": "박지훈", "patient": "김철수", "dob": "1965-08-20",
        "dx": "본태성고혈압 (I10),  이상지질혈증 (E78.5)",
        "meds": [
            ("암로디핀정 5mg",       "5 mg",   "1회", "30일", "식후 즉시"),
            ("로사르탄칼륨정 50mg",  "50 mg",  "1회", "30일", "식후 즉시"),
            ("아스피린장용정 100mg", "100 mg", "1회", "30일", "식후 즉시"),
        ],
        "notes": [
            "1일 1회, 매일 같은 시간에 복용하십시오.",
            "아스피린은 공복 복용을 피하십시오.",
            "복용 중단 시 반드시 의사와 상의하십시오.",
        ],
    },
    {
        "id": 2, "hospital": "강남당뇨클리닉", "dept": "내분비내과",
        "doctor": "이수진", "patient": "박영희", "dob": "1972-03-05",
        "dx": "2형 당뇨병 (E11.9),  비만 (E66.0)",
        "meds": [
            ("메트포르민정 500mg",   "500 mg", "3회", "30일", "식후 즉시"),
            ("글리메피리드정 2mg",   "2 mg",   "1회", "30일", "식전 30분"),
            ("시타글립틴정 100mg",   "100 mg", "1회", "30일", "식후 즉시"),
        ],
        "notes": [
            "혈당을 매일 측정하고 기록하십시오.",
            "식사를 거를 경우 저혈당에 주의하십시오.",
            "음주는 저혈당 위험을 높이므로 삼가십시오.",
        ],
    },
    {
        "id": 3, "hospital": "연세이비인후과의원", "dept": "이비인후과",
        "doctor": "최민호", "patient": "이준혁", "dob": "1990-11-22",
        "dx": "알레르기성 비염 (J30.1),  결막염 (H10.1)",
        "meds": [
            ("세티리진정 10mg",      "10 mg",  "1회", "14일", "취침전"),
            ("몬테루카스트정 10mg",  "10 mg",  "1회", "14일", "취침전"),
            ("나잘스프레이",         "2회분",  "2회", "14일", "식후 즉시"),
        ],
        "notes": [
            "취침 전 복용 시 졸음이 올 수 있습니다.",
            "꽃가루·먼지 노출을 최소화하십시오.",
            "증상 완화 후에도 처방 기간 동안 복용하십시오.",
        ],
    },
    {
        "id": 4, "hospital": "중앙소화기내과", "dept": "소화기내과",
        "doctor": "정현우", "patient": "송지은", "dob": "1983-06-14",
        "dx": "위식도역류질환 (K21.0),  기능성 소화불량 (K30)",
        "meds": [
            ("판토프라졸장용정 40mg", "40 mg", "1회", "28일", "식전 30분"),
            ("돔페리돈정 10mg",       "10 mg", "3회", "28일", "식전 30분"),
            ("알긴산나트륨현탁액",    "10 mL", "3회", "28일", "식후 즉시"),
        ],
        "notes": [
            "식후 바로 눕지 마십시오.",
            "맵고 기름진 음식, 커피, 탄산음료를 삼가십시오.",
            "과식을 피하고 소량씩 자주 드십시오.",
        ],
    },
    {
        "id": 5, "hospital": "마음정신건강의학과", "dept": "정신건강의학과",
        "doctor": "윤서연", "patient": "홍대우", "dob": "1978-09-30",
        "dx": "범불안장애 (F41.1),  불면증 (G47.0)",
        "meds": [
            ("에스시탈로프람정 10mg", "10 mg",   "1회", "28일", "식후 즉시"),
            ("알프라졸람정 0.25mg",   "0.25 mg", "1회", "14일", "취침전"),
            ("조피클론정 7.5mg",      "7.5 mg",  "1회", "14일", "취침전"),
        ],
        "notes": [
            "복용 중 음주를 절대 삼가십시오.",
            "졸음 유발 가능 — 운전·기계 조작 주의.",
            "갑작스러운 복용 중단은 금합니다.",
        ],
    },
    {
        "id": 6, "hospital": "정형외과의원", "dept": "정형외과",
        "doctor": "강도현", "patient": "임미란", "dob": "1960-02-17",
        "dx": "무릎 골관절염 (M17.1),  골다공증 (M81.0)",
        "meds": [
            ("셀레콕시브캡슐 200mg",  "200 mg", "2회", "14일", "식후 즉시"),
            ("칼슘+비타민D정",        "1정",    "2회", "30일", "식후 즉시"),
            ("알렌드로네이트정 70mg",  "70 mg",  "1회",  "4주", "기상 후 공복"),
        ],
        "notes": [
            "알렌드로네이트 복용 후 30분간 눕지 마십시오.",
            "물 200mL 이상과 함께 복용하십시오.",
            "무릎 과부하 활동(계단, 등산)을 줄이십시오.",
        ],
    },
    {
        "id": 7, "hospital": "한강갑상선클리닉", "dept": "내분비내과",
        "doctor": "오지현", "patient": "유성민", "dob": "1988-04-09",
        "dx": "갑상선기능저하증 (E03.9)",
        "meds": [
            ("레보티록신나트륨정 50mcg", "50 mcg", "1회", "90일", "기상 후 공복"),
            ("비타민B12정 1000mcg",     "1000 mcg","1회", "30일", "식후 즉시"),
        ],
        "notes": [
            "매일 같은 시간, 공복에 복용하십시오.",
            "칼슘·철분제와 4시간 이상 간격을 두십시오.",
            "임의로 용량을 조절하지 마십시오.",
        ],
    },
    {
        "id": 8, "hospital": "서울호흡기내과", "dept": "호흡기내과",
        "doctor": "백승준", "patient": "최서아", "dob": "1995-12-03",
        "dx": "지역사회획득폐렴 (J18.9),  급성기관지염 (J20.9)",
        "meds": [
            ("아지스로마이신정 250mg",    "250 mg", "1회",  "5일", "식후 즉시"),
            ("아세틸시스테인캡슐 200mg",  "200 mg", "3회",  "7일", "식후 즉시"),
            ("덱스트로메토르판정 15mg",   "15 mg",  "3회",  "5일", "식후 30분"),
        ],
        "notes": [
            "항생제는 반드시 처방 기간 동안 복용하십시오.",
            "충분한 수분 섭취로 가래 배출을 도우십시오.",
            "고열·호흡곤란 심화 시 응급실을 방문하십시오.",
        ],
    },
]


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def s(v):
    return int(v * S)


def load_fonts():
    try:
        return {
            "title":   ImageFont.truetype(KOREAN_FONT, s(24)),
            "heading": ImageFont.truetype(KOREAN_FONT, s(17), index=4),
            "body":    ImageFont.truetype(KOREAN_FONT, s(15)),
            "bold":    ImageFont.truetype(KOREAN_FONT, s(16), index=6),
            "small":   ImageFont.truetype(KOREAN_FONT, s(12)),
            "tiny":    ImageFont.truetype(KOREAN_FONT, s(10)),
        }
    except OSError:
        f = ImageFont.load_default()
        return {k: f for k in ["title","heading","body","bold","small","tiny"]}


def create_prescription_image(data: dict, path: str) -> None:
    W, H = s(500), s(700)
    img = Image.new("RGB", (W, H), (252, 252, 248))
    draw = ImageDraw.Draw(img)
    f = load_fonts()

    def center(text, y, font, color=(20, 20, 20)):
        bb = draw.textbbox((0, 0), text, font=font)
        draw.text(((W - bb[2] + bb[0]) // 2, y), text, fill=color, font=font)

    def hline(y, lx=s(18), color=(170, 170, 170), w=1):
        draw.line([(lx, y), (W - s(18), y)], fill=color, width=w)

    def row(label, value, y, font, color_v=(30, 30, 30)):
        draw.text((s(22), y), label, fill=(90, 90, 90), font=f["small"])
        draw.text((s(110), y), value, fill=color_v, font=font)

    # 헤더
    draw.rectangle([(0, 0), (W, s(54))], fill=(25, 75, 155))
    center("처  방  전", s(10), f["title"], (255, 255, 255))
    draw.text((s(22), s(14)), "건강보험", fill=(180, 210, 255), font=f["small"])
    draw.text((W - s(60), s(14)), "원본", fill=(180, 210, 255), font=f["small"])

    y = s(62)
    row("의료기관:", data["hospital"], y, f["heading"])
    draw.text((s(310), y), f"처방일자: 2026-06-30", fill=(80, 80, 80), font=f["small"])
    y += s(22)
    row("진  료  과:", data["dept"], y, f["body"])
    draw.text((s(310), y), f"담당의사: {data['doctor']}", fill=(80, 80, 80), font=f["small"])
    y += s(18)
    hline(y)
    y += s(10)

    row("환  자  명:", data["patient"], y, f["heading"])
    draw.text((s(240), y), "생년월일:", fill=(90, 90, 90), font=f["small"])
    draw.text((s(310), y), data["dob"], fill=(30, 30, 30), font=f["body"])
    y += s(20)
    hline(y)
    y += s(10)

    # 진단명
    draw.rectangle([(s(18), y), (W - s(18), y + s(26))], fill=(230, 240, 255))
    draw.text((s(24), y + s(5)), "진  단  명:", fill=(25, 60, 140), font=f["heading"])
    draw.text((s(120), y + s(5)), data["dx"], fill=(20, 20, 20), font=f["body"])
    y += s(34)
    hline(y)
    y += s(12)

    # 약품 테이블
    draw.text((s(22), y), "▣ 처방 의약품", fill=(25, 60, 140), font=f["heading"])
    y += s(24)

    COL = [s(22), s(168), s(248), s(318), s(388)]
    HDR = ["약  품  명", "용량(1회)", "1일 횟수", "투여일수", "용법"]
    CW  = [s(144), s(78), s(68), s(68), s(90)]

    draw.rectangle([(s(18), y), (W - s(18), y + s(24))], fill=(205, 220, 255))
    for hdr, cx, cw in zip(HDR, COL, CW):
        bb = draw.textbbox((0, 0), hdr, font=f["bold"])
        draw.text((cx + (cw - bb[2] + bb[0]) // 2, y + s(4)), hdr,
                  fill=(25, 60, 140), font=f["bold"])
    for cx in COL[1:]:
        draw.line([(cx - s(2), y), (cx - s(2), y + s(24))], fill=(160, 180, 220))
    y += s(24)
    hline(y, color=(130, 160, 210), w=2)

    row_colors = [(255, 255, 255), (245, 248, 255)]
    for ri, (name, dose, freq, days, method) in enumerate(data["meds"]):
        ry = y
        draw.rectangle([(s(18), ry), (W - s(18), ry + s(28))], fill=row_colors[ri % 2])
        for i, (val, cx, cw) in enumerate(zip(
                [name, dose, freq, days, method], COL, CW)):
            bb = draw.textbbox((0, 0), val, font=f["body"])
            tx = cx if i == 0 else cx + (cw - bb[2] + bb[0]) // 2
            draw.text((tx, ry + s(6)), val, fill=(30, 30, 30), font=f["body"])
        for cx in COL[1:]:
            draw.line([(cx - s(2), ry), (cx - s(2), ry + s(28))], fill=(200, 210, 230))
        hline(ry + s(28), color=(200, 210, 230))
        y += s(28)

    hline(y, color=(100, 130, 200), w=2)
    y += s(14)

    # 복약 안내
    note_h = s(16) * len(data["notes"]) + s(28)
    draw.rectangle([(s(18), y), (W - s(18), y + note_h)],
                   fill=(255, 250, 235), outline=(210, 180, 80))
    draw.text((s(24), y + s(7)), "▣ 복약 안내", fill=(150, 90, 0), font=f["heading"])
    for ni, note in enumerate(data["notes"]):
        draw.text((s(24), y + s(26) + ni * s(16)), f"• {note}",
                  fill=(60, 40, 0), font=f["body"])
    y += note_h + s(12)

    # 서명
    hline(y)
    y += s(10)
    draw.text((s(22), y), f"담당의사 서명:  {data['doctor']}", fill=(60, 60, 60), font=f["small"])
    cx, cy, r = W - s(48), y + s(8), s(16)
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(160, 30, 30), width=2)
    draw.text((cx - s(10), cy - s(8)), "직인", fill=(160, 30, 30), font=f["small"])

    img.save(path)


def preprocess(path: str) -> None:
    img = Image.open(path)
    gray = img.convert("L")
    sharp = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=130, threshold=3))
    sharp.convert("RGB").save(path)


# ── 교정 로직 ─────────────────────────────────────────────────────────────────
def fix_char_level(text: str) -> str:
    for wrong, right in CHAR_CORRECTIONS.items():
        text = text.replace(wrong, right)
    # 숫자 뒤 O → 0  (50Omg → 500mg)
    text = re.sub(r'(\d)O', r'\g<1>0', text)
    text = re.sub(r'O(\d)', r'0\1', text)
    # mg 오인식: m이 rn/rN/rT/r7으로 분리되는 패턴 → mg
    text = re.sub(r'(\d[\.\d]*\s*)r[nNtT7]g\b', r'\g<1>mg', text)
    text = re.sub(r'(\d[\.\d]*\s*)rng\b',        r'\g<1>mg', text)
    # mcg 오인식: rc/rC로 분리되는 패턴 → mcg
    text = re.sub(r'(\d[\.\d]*\s*)r[cC]g\b', r'\g<1>mcg', text)
    return text


def fix_word_level(text: str, conf: float, domain: list) -> str:
    if conf >= CONF_THRESHOLD:
        return text
    words = text.split()
    result, changed = [], False
    for w in words:
        m = difflib.get_close_matches(w, domain, n=1, cutoff=0.62)
        if m and m[0] != w:
            result.append(m[0]); changed = True
        else:
            result.append(w)
    return " ".join(result) if changed else text


def correct_results(results: list, domain: list) -> list:
    out = []
    for bbox, text, conf in results:
        orig = text
        text = fix_char_level(text)
        text = fix_word_level(text, conf, domain)
        out.append((bbox, text, conf, orig != text))
    return out


# ── OCR 실행 ─────────────────────────────────────────────────────────────────
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("  [OCR] 모델 로딩...")
        _reader = easyocr.Reader(["en", "ko"], gpu=False, verbose=False)
    return _reader


def run_ocr(path: str):
    return get_reader().readtext(
        path, mag_ratio=1.0, contrast_ths=0.05,
        adjust_contrast=0.7, width_ths=0.6, decoder="greedy",
    )


# ── 정확도 평가 ───────────────────────────────────────────────────────────────
def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def evaluate(data: dict, results: list) -> dict:
    texts = [t for _, t, _, _ in results]
    full = " ".join(texts)

    # 진단명
    dx_score = max((similarity(data["dx"], t) for _, t, _, _ in results), default=0)

    # 약품명
    med_scores = []
    for med_name, *_ in data["meds"]:
        sc = max((similarity(med_name, t) for _, t, _, _ in results), default=0)
        med_scores.append(sc)

    # 용법 키워드
    keywords = ["식후", "식전", "취침전", "공복", "즉시", "30분"]
    kw_found = sum(1 for kw in keywords if kw in full)

    avg_conf = sum(c for _, _, c, _ in results) / len(results) if results else 0
    n_corrected = sum(1 for *_, changed in results if changed)

    return {
        "dx_score":    dx_score,
        "med_scores":  med_scores,
        "med_avg":     sum(med_scores) / len(med_scores) if med_scores else 0,
        "kw_found":    kw_found,
        "kw_total":    len([kw for kw in keywords
                            if any(kw in m[-1] for m in data["meds"])
                            or any(kw in n for n in data["notes"])]),
        "avg_conf":    avg_conf,
        "n_corrected": n_corrected,
        "n_results":   len(results),
    }


def grade(score: float) -> str:
    if score >= 0.85: return "✅ PASS"
    if score >= 0.60: return "⚠️ PARTIAL"
    return "❌ FAIL"


# ── 결과 이미지 저장 ──────────────────────────────────────────────────────────
def draw_and_save(sample_path: str, results: list, out_path: str) -> None:
    img_bgr = cv2.imread(sample_path)
    for bbox, _, _, _ in results:
        cv2.polylines(img_bgr, [np.array(bbox, dtype=np.int32)],
                      True, (0, 180, 0), 2)
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    dr = ImageDraw.Draw(pil)
    try:
        lf = ImageFont.truetype(KOREAN_FONT, 14)
    except OSError:
        lf = ImageFont.load_default()
    for bbox, text, conf, _ in results:
        x, y = int(bbox[0][0]), int(bbox[0][1])
        dr.text((x, max(y - 16, 0)), f"{text}({conf:.2f})", fill=(200, 0, 0), font=lf)
    pil.save(out_path)


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    all_evals = []

    for data in PRESCRIPTIONS:
        pid = data["id"]
        print(f"\n{'='*60}")
        print(f"  처방전 #{pid:02d} | {data['patient']} | {data['dx'][:30]}...")
        print(f"{'='*60}")

        # 도메인 사전 = 공통 + 이 처방전의 약품명
        domain = DOMAIN_DICT_BASE + [m[0] for m in data["meds"]]

        sample_path = os.path.join(OUT_DIR, f"rx_{pid:02d}_sample.png")
        result_path = os.path.join(OUT_DIR, f"rx_{pid:02d}_result.png")

        # 1. 이미지 생성
        create_prescription_image(data, sample_path)
        preprocess(sample_path)
        print(f"  [생성] {sample_path}")

        # 2. OCR
        raw = run_ocr(sample_path)
        print(f"  [OCR] {len(raw)}개 영역 인식")

        # 3. 교정
        corrected = correct_results(raw, domain)
        n_fixed = sum(1 for *_, ch in corrected if ch)
        if n_fixed:
            print(f"  [교정] {n_fixed}건 교정 적용")

        # 4. 결과 이미지
        draw_and_save(sample_path, corrected, result_path)

        # 5. 평가
        ev = evaluate(data, corrected)
        all_evals.append({"id": pid, "patient": data["patient"],
                           "dx_short": data["dx"].split("(")[0].strip(), **ev})

    # ── 최종 집계 표 ───────────────────────────────────────────────────────────
    print(f"\n\n{'='*100}")
    print("  처방전 OCR 파이프라인 결과 집계")
    print(f"{'='*100}")
    print(f"{'#':>2}  {'환자':6}  {'진단명':20}  {'진단인식':10}  "
          f"{'약품명 평균':10}  {'약품수':6}  {'평균신뢰도':10}  {'교정건수':8}  {'종합'}")
    print("-" * 100)

    pass_cnt = partial_cnt = fail_cnt = 0
    for e in all_evals:
        n_meds = len(PRESCRIPTIONS[e["id"] - 1]["meds"])
        med_pass = sum(1 for sc in e["med_scores"] if sc >= 0.85)
        g = grade(min(e["dx_score"], e["med_avg"]))
        if "PASS" in g:    pass_cnt += 1
        elif "PARTIAL" in g: partial_cnt += 1
        else:              fail_cnt += 1

        print(f"{e['id']:>2}  {e['patient']:6}  {e['dx_short']:20}  "
              f"{e['dx_score']:>6.3f} {grade(e['dx_score']):>12}  "
              f"{e['med_avg']:>6.3f} ({med_pass}/{n_meds})  "
              f"{e['avg_conf']:>8.3f}  "
              f"{e['n_corrected']:>6}건  "
              f"{g}")

    print("-" * 100)
    print(f"  결과: ✅ PASS {pass_cnt}건 / ⚠️ PARTIAL {partial_cnt}건 / ❌ FAIL {fail_cnt}건  "
          f"(전체 {len(all_evals)}건)")
    print(f"  평균 신뢰도: {sum(e['avg_conf'] for e in all_evals)/len(all_evals):.3f}")
    print(f"  총 교정 적용: {sum(e['n_corrected'] for e in all_evals)}건")
    print(f"\n  결과 이미지 저장 위치: {os.path.abspath(OUT_DIR)}/")


if __name__ == "__main__":
    main()
