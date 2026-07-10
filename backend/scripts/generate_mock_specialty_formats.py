# -*- coding: utf-8 -*-
"""
mock_prescription_official.png과 동일한 틀(건강보험심사평가원 표준 양식 스타일)로
치과/한의원/소아과/정신과/대학병원 5종을 통일해서 재생성.

공통 구조:
- 상단 박스: [조제기관] [처방기관] [보험자명]
- 중앙 큰 제목: 처 방 전
- 환자정보 표 (요양기관기호/명, 성명, 생년월일, 질병분류기호)
- 처방 내역 표 (처방 의약품의 명칭 | 1회 투약량 | 1일 투여횟수 | 총 투약일수 | 용법)
- 하단 박스: 사용기간 / 조제기관명 / 조제약사 성명 + QR 자리
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def make_official_style_mock(path, top_info, patient_rows, drug_rows, note_lines=None, H=None):
    W = 900
    if H is None:
        H = 700 if not note_lines else 500
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    d.rectangle((20, 20, 880, 70), outline="black", width=1)
    d.text((30, 30), top_info, font=font(13), fill="black")

    d.text((380, 90), "처 방 전", font=font(30, bold=True), fill="black")

    y0 = 150
    row_h = 45
    box_h = row_h * len(patient_rows)
    d.rectangle((20, y0, 880, y0 + box_h), outline="black", width=1)
    for i, (label, value) in enumerate(patient_rows):
        ry = y0 + i * row_h
        if i > 0:
            d.line((20, ry, 880, ry), fill="black", width=1)
        d.text((30, ry + 12), f"{label}: {value}", font=font(13), fill="black")

    y = y0 + box_h + 30

    if drug_rows:
        ty = y
        d.rectangle((20, ty, 880, ty + 40), outline="black", width=1)
        headers = ["처방 의약품의 명칭", "1회\n투약량", "1일\n투여횟수", "총\n투약일수", "용법"]
        xs = [30, 470, 560, 650, 740]
        for h, x in zip(headers, xs):
            d.text((x, ty + 5), h, font=font(12, bold=True), fill="black")

        y = ty + 40
        row_h2 = 55
        for name, amt, freq, days, note in drug_rows:
            d.rectangle((20, y, 880, y + row_h2), outline="black", width=1)
            d.text((30, y + 8), name, font=font(12), fill="black")
            d.text((485, y + 20), amt, font=font(12), fill="black")
            d.text((575, y + 20), freq, font=font(12), fill="black")
            d.text((665, y + 20), days, font=font(12), fill="black")
            if note:
                d.text((740, y + 8), note, font=font(10), fill="black")
            y += row_h2
    else:
        box_h2 = 28 * len(note_lines) + 20
        d.rectangle((20, y, 880, y + box_h2), outline="black", width=1)
        ny = y + 15
        for line in note_lines:
            d.text((35, ny), line, font=font(13), fill="black")
            ny += 28
        y += box_h2

    by = y + 30
    d.rectangle((20, by, 880, by + 100), outline="black", width=1)
    d.text((30, by + 10), "사용기간: 교부일부터 (3)일간", font=font(12), fill="black")
    d.text((30, by + 40), "조제기관명:", font=font(12), fill="black")
    d.text((30, by + 65), "조제약사 성명:", font=font(12), fill="black")
    d.rectangle((760, by + 10, 860, by + 90), outline="gray", width=1)
    d.text((775, by + 40), "QR", font=font(16), fill="gray")

    img.save(path)
    print(f"생성: {path}")


if __name__ == "__main__":
    make_official_style_mock(
        "samples/mock_dental_bag.png",
        "[처방기관] OO치과의원   [진료내용] 발치(#38) 후 처방   [전화] 02-000-0000",
        [("성명", "박치아 (가짜 데이터)"), ("진료일자", "2026-07-03")],
        [
            ("[급여][649500566] 아모클란정375mg(아모피실린/클라불란산)", "1", "3", "5", ""),
            ("[급여][642201546] 이지엔6프로연질캡슐(이부프로펜)", "1", "통증시 3회", "4", ""),
            ("[비급여][611209873] 클로르헥시딘 가글액", "적량", "2", "-", "가글 후 뱉어내세요"),
        ],
    )

    make_official_style_mock(
        "samples/mock_oriental_medicine.png",
        "[처방기관] OO한의원   [처방명] 십전대보탕 가감방",
        [("성명", "정한방 (가짜 데이터)"), ("조제일자", "2026-07-03"), ("총 제수", "20첩(봉)")],
        drug_rows=None,
        note_lines=[
            "매 식후 30분에 따뜻하게 데워서 한 봉씩 드세요.",
            "하루 두 번, 아침과 저녁으로 나누어 복용하시면 됩니다.",
            "냉장 보관 후 데워 드시길 권합니다.",
            "주의사항: 복용 중 무, 녹두는 피해주세요.",
        ],
    )

    make_official_style_mock(
        "samples/mock_pediatric.png",
        "[처방기관] OO소아청소년과의원   [전화] 02-000-0000",
        [("환아 성명", "김아기 (가짜 / 3세, 14kg)"), ("질병분류기호", "H66.9 (급성 중이염)")],
        [
            ("[급여][649500567] 오구멘틴시럽(아목시실린/클라불란산)", "5mL", "2", "10", "45mg/kg/day 기준"),
            ("[급여][642201547] 챔프시럽(아세트아미노펜)", "4mL", "발열시", "-", "4~6시간 간격"),
            ("[급여][643501074] 지르텍시럽(세티리진)", "2.5mL", "1", "7", "취침전"),
        ],
    )

    make_official_style_mock(
        "samples/mock_psychiatry.png",
        "[처방기관] OO정신건강의학과의원   [전화] 02-000-0000",
        [("성명", "이마음 (가짜 데이터)"), ("질병분류기호", "F41.1 (범불안장애)")],
        [
            ("[급여][649500568][향정] 자낙스정0.25mg(알프라졸람)", "1", "2", "14", "아침/저녁"),
            ("[급여][642201548] 렉사프로정10mg(에스시탈로프람)", "1", "1", "30", "아침"),
            ("[급여][643501075][향정] 스틸녹스정10mg(졸피뎀)", "1", "1", "7", "취침전"),
        ],
    )

    W, H = 900, 850
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((20, 20, 880, 70), outline="black", width=1)
    d.text((30, 30), "[처방기관] OO대학교병원   [협진과] 내분비내과·심장내과", font=font(13), fill="black")
    d.text((380, 90), "처 방 전", font=font(30, bold=True), fill="black")

    y0 = 150
    d.rectangle((20, y0, 880, y0 + 45), outline="black", width=1)
    d.text((30, y0 + 12), "성명: 최복합 (가짜 데이터)", font=font(13), fill="black")

    y = y0 + 45 + 20
    d.text((30, y), "[내분비내과] 진단: 제2형 당뇨병, 이상지질혈증", font=font(13, bold=True), fill="#3070b0")
    y += 25
    ty = y
    d.rectangle((20, ty, 880, ty + 40), outline="black", width=1)
    headers = ["처방 의약품의 명칭", "1회", "1일횟수", "총일수", "용법"]
    xs = [30, 470, 560, 650, 740]
    for h, x in zip(headers, xs):
        d.text((x, ty + 12), h, font=font(12, bold=True), fill="black")
    y = ty + 40
    rows1 = [
        ("[급여][649500560] 자누메트정50/1000mg", "1", "2", "30", ""),
        ("[급여][642201540] 아토젯정10/40mg", "1", "1", "30", "취침전"),
    ]
    for name, amt, freq, days, note in rows1:
        d.rectangle((20, y, 880, y + 45), outline="black", width=1)
        d.text((30, y + 12), name, font=font(12), fill="black")
        d.text((485, y + 12), amt, font=font(12), fill="black")
        d.text((575, y + 12), freq, font=font(12), fill="black")
        d.text((665, y + 12), days, font=font(12), fill="black")
        d.text((740, y + 12), note, font=font(10), fill="black")
        y += 45

    y += 20
    d.text((30, y), "[심장내과] 진단: 본태성 고혈압, 심방세동", font=font(13, bold=True), fill="#3070b0")
    y += 25
    ty = y
    d.rectangle((20, ty, 880, ty + 40), outline="black", width=1)
    for h, x in zip(headers, xs):
        d.text((x, ty + 12), h, font=font(12, bold=True), fill="black")
    y = ty + 40
    rows2 = [
        ("[급여][644308830] 엘리퀴스정5mg", "1", "2", "30", ""),
        ("[급여][658101480] 콘칼정5/5mg", "1", "1", "30", "아침"),
        ("[비급여][643501070] 오메가3연질캡슐", "1", "1", "30", ""),
    ]
    for name, amt, freq, days, note in rows2:
        d.rectangle((20, y, 880, y + 45), outline="black", width=1)
        d.text((30, y + 12), name, font=font(12), fill="black")
        d.text((485, y + 12), amt, font=font(12), fill="black")
        d.text((575, y + 12), freq, font=font(12), fill="black")
        d.text((665, y + 12), days, font=font(12), fill="black")
        d.text((740, y + 12), note, font=font(10), fill="black")
        y += 45

    by = y + 30
    d.rectangle((20, by, 880, by + 100), outline="black", width=1)
    d.text((30, by + 10), "사용기간: 교부일부터 (3)일간", font=font(12), fill="black")
    d.text((30, by + 40), "조제기관명:", font=font(12), fill="black")
    d.text((30, by + 65), "조제약사 성명:", font=font(12), fill="black")
    d.rectangle((760, by + 10, 860, by + 90), outline="gray", width=1)
    d.text((775, by + 40), "QR", font=font(16), fill="gray")
    img.save("samples/mock_university_hospital.png")
    print("생성: samples/mock_university_hospital.png")

    print("5개 전부 표준양식 스타일로 통일 완료")
