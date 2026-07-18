"""
10개 추가 목업 - 새로운 진료과/상황 커버.
표준양식(mock_prescription_official.png) 틀 재사용.

1. 안과 - 점안, 좌안/우안/양안 표기
2. 피부과 - 경구약 없이 도포(외용)만 있는 케이스
3. 산부인과 - 특정 요일부터 시작하는 주기적 복용
4. 요양병원 다약제 - 고령 만성질환자 10종 이상 (REQ 핵심 대상과 가장 유사)
5. 응급실 단회처방 - 1회성 처방, 짧은 기간
6. 퇴원약 처방전 - 입원사유/퇴원약/외래예약이 섞인 다른 구조
7. 대체조제 체크박스 포함 표준처방전
8. 영문 약품명 혼용 (한글 처방전 안에 영문 성분명이 그대로 노출)
9. 재진 처방전 - 이전 대비 변경/유지/중단 표시
10. 직인(도장) 이미지가 텍스트와 겹치는 케이스 - 실제로 자주 발생하는 OCR 방해 요소
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def base_canvas(W=900, H=700):
    img = Image.new("RGB", (W, H), "white")
    return img, ImageDraw.Draw(img)


def header_box(d, W, top_info):
    d.rectangle((20, 20, W - 20, 70), outline="black", width=1)
    d.text((30, 30), top_info, font=font(13), fill="black")
    d.text((W // 2 - 70, 90), "처 방 전", font=font(30, bold=True), fill="black")


def patient_box(d, W, y0, rows):
    row_h = 40
    d.rectangle((20, y0, W - 20, y0 + row_h * len(rows)), outline="black", width=1)
    for i, txt in enumerate(rows):
        ry = y0 + i * row_h
        if i > 0:
            d.line((20, ry, W - 20, ry), fill="black", width=1)
        d.text((30, ry + 11), txt, font=font(13), fill="black")
    return y0 + row_h * len(rows)


def drug_table(d, W, y0, rows, headers=("처방 의약품의 명칭", "1회", "횟수", "일수", "용법"),
               col_x=(30, 470, 560, 650, 740), row_h=50):
    d.rectangle((20, y0, W - 20, y0 + 36), outline="black", width=1)
    for h, x in zip(headers, col_x):
        d.text((x, y0 + 9), h, font=font(12, bold=True), fill="black")
    y = y0 + 36
    for cells in rows:
        d.rectangle((20, y, W - 20, y + row_h), outline="black", width=1)
        for cell, x in zip(cells, col_x):
            d.text((x, y + row_h // 2 - 8), str(cell), font=font(11), fill="black")
        y += row_h
    return y


# 1. 안과
def make_ophthalmology(path):
    img, d = base_canvas(900, 500)
    header_box(d, 900, "[처방기관] OO안과의원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 최눈영 (가짜 데이터)", "질병분류기호: H10.9 (결막염)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][651200340] 트루솝점안액", "1방울", "3", "14", "좌안(OS)"),
        ("[급여][649801120] 알레르기롭점안액", "1방울", "2", "14", "양안(OU)"),
        ("[급여][642950870] 리박씬점안연고", "적량", "1", "7", "우안(OD), 취침전 도포"),
    ])
    img.save(path)
    print(f"생성: {path}")


# 2. 피부과 - 외용제만
def make_dermatology(path):
    img, d = base_canvas(900, 450)
    header_box(d, 900, "[처방기관] OO피부과의원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 강피부 (가짜 데이터)", "질병분류기호: L20.9 (아토피피부염)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][647301230] 데스오웬크림", "적량", "2", "14", "환부 도포"),
        ("[비급여][611200450] 보습로션(세라마이드)", "적량", "수시", "-", "전신 도포"),
        ("[급여][653400980] 타크로리무스연고0.1%", "적량", "2", "28", "안면부는 소량만"),
    ])
    img.save(path)
    print(f"생성: {path}")


# 3. 산부인과 - 주기적 복용
def make_obgyn(path):
    img, d = base_canvas(900, 450)
    header_box(d, 900, "[처방기관] OO산부인과의원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 오주기 (가짜 데이터)", "질병분류기호: N91.0 (무월경)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][644102340] 프로베라정5mg", "1", "2", "10", "생리 시작 예정일 5일 전부터"),
        ("[급여][648903450] 클로미드정50mg", "1", "1", "5", "월경 시작 3일째부터"),
        ("[비급여][601200120] 엽산정400mcg", "1", "1", "30", "매일 아침"),
    ])
    img.save(path)
    print(f"생성: {path}")


# 4. 요양병원 다약제 - REQ 핵심 대상과 가장 유사
def make_nursing_hospital(path):
    img, d = base_canvas(900, 800)
    header_box(d, 900, "[처방기관] OO요양병원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, [
        "성명: 홍말년 (가짜 / 84세)",
        "질병분류기호: I10, E11.9, F03 (고혈압, 당뇨병, 치매)",
    ])
    y = drug_table(d, 900, y + 20, [
        ("[급여][649500561] 암로디핀정5mg", "1", "1", "30", "아침"),
        ("[급여][642201541] 메트포르민정500mg", "1", "2", "30", "아침/저녁"),
        ("[급여][644308831] 아리셉트정5mg(도네페질)", "1", "1", "30", "저녁"),
        ("[급여][658101481] 아스피린프로텍트정100mg", "1", "1", "30", "아침"),
        ("[급여][643501071] 리피토정10mg", "1", "1", "30", "저녁"),
        ("[급여][645209870] 란소프라졸캡슐15mg", "1", "1", "30", "아침 식전"),
        ("[비급여][611209871] 센나정", "1", "1", "30", "취침전, 변비시"),
        ("[급여][622309871] 마그네슘옥사이드정", "1", "2", "30", "아침/저녁"),
        ("[비급여][601209871] 비타민D3정", "1", "1", "30", "아침"),
        ("[급여][633409871] 쿠에타핀정25mg(퀘티아핀)", "1", "1", "30", "취침전, 불안시"),
    ], row_h=40)
    img.save(path)
    print(f"생성: {path}")


# 5. 응급실 단회처방
def make_er(path):
    img, d = base_canvas(900, 400)
    header_box(d, 900, "[처방기관] OO병원 응급의료센터   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 박응급 (가짜 데이터)", "질병분류기호: R10.4 (급성 복통)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][649911230] 부스코판정10mg", "1", "1회(당일)", "1", "즉시 복용"),
        ("[비급여][611922340] 게보린정", "1", "1회(당일)", "1", "즉시 복용, 통증 지속시 응급실 재방문"),
    ])
    img.save(path)
    print(f"생성: {path}")


# 6. 퇴원약 처방전 - 다른 섹션 구조
def make_discharge(path):
    img, d = base_canvas(900, 700)
    d.rectangle((20, 20, 880, 70), outline="black", width=1)
    d.text((30, 30), "[처방기관] OO병원   퇴원약 처방전", font=font(13), fill="black")
    d.text((350, 90), "퇴 원 약", font=font(28, bold=True), fill="black")

    y = 150
    d.rectangle((20, y, 880, y + 80), outline="black", width=1)
    d.text((30, y + 10), "성명: 윤퇴원 (가짜 데이터)", font=font(13), fill="black")
    d.text((30, y + 35), "입원사유: 폐렴 (J18.9)", font=font(13), fill="black")
    d.text((30, y + 55), "입원기간: 2026-06-25 ~ 2026-07-02", font=font(12), fill="gray")

    y = drug_table(d, 900, y + 100, [
        ("[급여][649500562] 타미론정(아목시실린)", "1", "3", "5", "식후"),
        ("[급여][642201542] 뮤코펙트정(암브록솔)", "1", "3", "5", "식후, 거담"),
        ("[비급여][611209872] 타이레놀정500mg", "1", "발열시", "-", "필요시"),
    ])
    d.rectangle((20, y + 20, 880, y + 70), outline="black", width=1)
    d.text((30, y + 32), "외래 예약: 2026-07-09(목) 호흡기내과 10:00", font=font(12), fill="black")
    img.save(path)
    print(f"생성: {path}")


# 7. 대체조제 체크박스 포함
def make_substitution_checkbox(path):
    img, d = base_canvas(900, 500)
    header_box(d, 900, "[처방기관] OO내과의원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 정대체 (가짜 데이터)", "질병분류기호: I10 (고혈압)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][649500563] 노바스크정5mg(암로디핀)", "1", "1", "30", ""),
        ("[급여][642201543] 디오반정80mg(발사르탄)", "1", "1", "30", ""),
    ])
    d.rectangle((20, y + 15, 880, y + 65), outline="black", width=1)
    d.text((30, y + 25), "☐ 대체조제 불가   ☑ 대체조제 가능", font=font(13), fill="black")
    d.text((30, y + 45), "(체크가 없는 경우 대체조제 가능으로 간주)", font=font(10), fill="gray")
    img.save(path)
    print(f"생성: {path}")


# 8. 영문 약품명 혼용
def make_english_mixed(path):
    img, d = base_canvas(900, 450)
    header_box(d, 900, "[처방기관] OO내과의원(영문 처방)   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["Name: Kim Younghee (가짜 데이터)", "Dx: Type 2 Diabetes Mellitus"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][649500564] Metformin 500mg", "1 tab", "2", "30", "after meal"),
        ("[급여][642201544] Glimepiride 2mg", "1 tab", "1", "30", "before breakfast"),
        ("[급여][643501072] Atorvastatin 10mg", "1 tab", "1", "30", "at bedtime"),
    ])
    img.save(path)
    print(f"생성: {path}")


# 9. 재진 처방전 - 변경/유지/중단 표시
def make_followup_change(path):
    img, d = base_canvas(900, 550)
    header_box(d, 900, "[처방기관] OO내과의원 (재진)   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 서재진 (가짜 데이터)", "질병분류기호: E78.5 (고지혈증)"])
    y = drug_table(
        d, 900, y + 20,
        [
            ("[급여][643501073] 리피토정10mg", "1", "1", "30", "유지"),
            ("[급여][643501080] 크레스토정20mg", "1", "1", "30", "[신규] 용량 증량"),
            ("[급여][645600120] 트라젠타정5mg", "0", "0", "0", "[중단] 부작용으로 중단"),
        ],
        headers=("처방 의약품의 명칭", "1회", "횟수", "일수", "변경사항"),
    )
    img.save(path)
    print(f"생성: {path}")


# 10. 직인(도장)이 텍스트와 겹치는 케이스
def make_stamp_overlap(path):
    img, d = base_canvas(900, 500)
    header_box(d, 900, "[처방기관] OO의원   [전화] 02-000-0000")
    y = patient_box(d, 900, 150, ["성명: 임도장 (가짜 데이터)", "질병분류기호: I10 (고혈압)"])
    y = drug_table(d, 900, y + 20, [
        ("[급여][649500565] 암로디핀정5mg", "1", "1", "30", ""),
        ("[급여][642201545] 로자탄칼륨정50mg", "1", "1", "30", ""),
    ])
    # 빨간 원형 직인이 텍스트 영역과 겹치도록 배치
    stamp_x, stamp_y = 700, y - 90
    d.ellipse((stamp_x, stamp_y, stamp_x + 100, stamp_y + 100), outline="#c0392b", width=3)
    d.text((stamp_x + 20, stamp_y + 35), "醫院印", font=font(18, bold=True), fill="#c0392b")
    img.save(path)
    print(f"생성: {path}")


if __name__ == "__main__":
    make_ophthalmology("samples/mock_ophthalmology.png")
    make_dermatology("samples/mock_dermatology.png")
    make_obgyn("samples/mock_obgyn.png")
    make_nursing_hospital("samples/mock_nursing_hospital.png")
    make_er("samples/mock_er.png")
    make_discharge("samples/mock_discharge.png")
    make_substitution_checkbox("samples/mock_substitution_checkbox.png")
    make_english_mixed("samples/mock_english_mixed.png")
    make_followup_change("samples/mock_followup_change.png")
    make_stamp_overlap("samples/mock_stamp_overlap.png")
    print("10개 전부 생성 완료")
