"""
서울내과의원 처방전 목업 (EasyOCR 시절 원본을 CLOVA 시대 기준으로 업데이트).
원본 레이아웃 재현 + 약품명 앞에 [급여/비급여][코드] 패턴 추가.
개인정보(환자명, 의사명 등)는 전부 가짜 데이터.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def make_seoul_clinic_mock(path):
    W, H = 1350, 1450
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # 상단 헤더 바 (진회색)
    d.rectangle((0, 0, W, 170), fill="#4a4a4a")
    d.text((40, 55), "건강보험", font=font(22), fill="white")
    d.text((W // 2 - 110, 45), "처 방 전", font=font(48, bold=True), fill="white")
    d.text((W - 130, 55), "원본", font=font(22), fill="white")

    y = 205
    # 의료기관 정보
    d.text((40, y), "의료기관명:", font=font(18), fill="#555")
    d.text((260, y - 5), "서울내과의원", font=font(26, bold=True), fill="black")
    d.text((720, y), "요양기관번호:", font=font(18), fill="#555")
    d.text((980, y - 5), "12345678", font=font(24, bold=True), fill="black")
    y += 50
    d.text((40, y), "주      소:", font=font(18), fill="#555")
    d.text((260, y), "서울시 강남구 테헤란로 456", font=font(20), fill="black")
    y += 50
    d.text((40, y), "전화번호:", font=font(18), fill="#555")
    d.text((260, y), "02-9876-5432", font=font(20), fill="black")
    d.text((720, y), "처방일자:", font=font(18), fill="#555")
    d.text((950, y), "2026-06-30", font=font(22, bold=True), fill="black")

    y += 55
    d.line((40, y, W - 40, y), fill="black", width=2)
    y += 30

    d.text((40, y), "환 자 명:", font=font(18), fill="#555")
    d.text((260, y - 5), "홍길동", font=font(26, bold=True), fill="black")
    d.text((720, y), "생년월일:", font=font(18), fill="#555")
    d.text((950, y - 3), "1985-03-15", font=font(22, bold=True), fill="black")
    y += 50
    d.text((40, y), "진료과목:", font=font(18), fill="#555")
    d.text((260, y - 2), "내과", font=font(22), fill="black")
    d.text((720, y), "담당의사:", font=font(18), fill="#555")
    d.text((950, y - 2), "김민준 (면허번호: 56789)", font=font(20, bold=True), fill="black")

    y += 60
    d.line((40, y, W - 40, y), fill="black", width=1)
    y += 20

    # 진단명 박스 (연회색 배경)
    d.rectangle((40, y, W - 40, y + 60), fill="#f0f0f0")
    d.text((60, y + 15), "진 단 명:", font=font(22, bold=True), fill="black")
    d.text((260, y + 15), "상기도감염 (J06.9), 급성위염 (K29.1)", font=font(22), fill="black")
    y += 90

    d.line((40, y, W - 40, y), fill="black", width=1)
    y += 30

    # 처방 의약품 섹션
    d.text((40, y), "\u25a0 처방 의약품", font=font(24, bold=True), fill="black")
    y += 45

    headers = ["약 품 명", "용량(1회)", "1일 횟수", "투여일수", "용법"]
    col_x = [50, 620, 800, 970, 1130]
    col_w = [570, 180, 170, 160, 180]

    d.rectangle((40, y, W - 40, y + 55), fill="#3a3a3a")
    for h, x, w in zip(headers, col_x, col_w):
        bbox = d.textbbox((0, 0), h, font=font(19, bold=True))
        tw = bbox[2] - bbox[0]
        d.text((x + (w - tw) // 2 - 10, y + 15), h, font=font(19, bold=True), fill="white")
    y += 55

    rows = [
        ("[급여][649500XXX]\n아목시실린캡슐 500mg", "500 mg", "3회", "5일", "식후 30분"),
        ("[급여][642201XXX]\n이부프로펜정 400mg", "400 mg", "3회", "5일", "식후 30분"),
        ("[급여][643501XXX]\n오메프라졸캡슐 20mg", "20 mg", "2회", "5일", "식전 30분"),
        ("[비급여][611209XXX]\n덱사메타손정 0.5mg", "0.5 mg", "1회", "3일", "식후 즉시"),
    ]
    row_h = 75
    for i, (name, dose, freq, days, usage) in enumerate(rows):
        bg = "#f7f7f7" if i % 2 == 0 else "white"
        d.rectangle((40, y, W - 40, y + row_h), fill=bg)
        name_lines = name.split("\n")
        d.text((col_x[0], y + 12), name_lines[0], font=font(14), fill="#555")
        d.text((col_x[0], y + 34), name_lines[1], font=font(20, bold=True), fill="black")
        d.text((col_x[1] + 10, y + 26), dose, font=font(20), fill="black")
        d.text((col_x[2] + 30, y + 26), freq, font=font(20), fill="black")
        d.text((col_x[3] + 25, y + 26), days, font=font(20), fill="black")
        d.text((col_x[4] + 10, y + 26), usage, font=font(19), fill="black")
        y += row_h
    d.rectangle((40, y - row_h * len(rows), W - 40, y), outline="black", width=2)
    for x in col_x[1:]:
        d.line((x - 15, y - row_h * len(rows), x - 15, y), fill="#ccc", width=1)

    y += 40
    # 복약 안내 박스
    box_h = 190
    d.rectangle((40, y, W - 40, y + box_h), outline="black", width=1)
    d.text((60, y + 15), "\u25a0 복약 안내", font=font(22, bold=True), fill="black")
    notes = [
        "\u2022 1일 3회, 식후 30분에 복용하십시오.",
        "\u2022 오메프라졸은 식전 30분에 복용하십시오.",
        "\u2022 항생제(아목시실린)는 정해진 기간 동안 복용하십시오.",
        "\u2022 음주 및 카페인 섭취를 삼가십시오.",
    ]
    ny = y + 60
    for note in notes:
        d.text((60, ny), note, font=font(19), fill="black")
        ny += 33
    y += box_h + 30

    d.line((40, y, W - 40, y), fill="black", width=1)
    y += 25
    d.text((40, y), "담당의사 서명:", font=font(18), fill="#555")
    d.text((250, y - 3), "김민준", font=font(24, bold=True), fill="black")
    d.ellipse((W - 160, y - 15, W - 60, y + 85), outline="#a03030", width=3)
    d.text((W - 135, y + 20), "직인", font=font(20), fill="#a03030")
    y += 55
    d.text((40, y), "위 처방대로 조제하여 주시기 바랍니다.", font=font(16), fill="#555")

    img.save(path)
    print(f"생성 완료: {path}")


if __name__ == "__main__":
    make_seoul_clinic_mock("samples/mock_seoul_clinic_prescription.png")
