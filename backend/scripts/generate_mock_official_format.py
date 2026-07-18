"""
건강보험심사평가원 표준 처방전 양식을 흉내낸 목업 생성.
실제 양식 핵심 특징 반영:
- 약품명 앞에 [급여]/[비급여] + 코드번호가 붙음 (예: [급여][649500560])
- 용법이 자유서술형으로 붙는 경우 있음 (예: "1일 1회 흡입하세요")
- 상단에 조제기관/환자/보험자 정보 표
개인정보는 전부 가짜값이며 실제 환자와 무관함.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def make_official_format_mock(path):
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # 상단 박스: 조제기관/보험자
    d.rectangle((20, 20, 880, 70), outline="black", width=1)
    d.text((30, 30), "[조제기관] OO약국   [처방기관] OO의원   [보험자명] 국민건강보험공단", font=font(13), fill="black")

    # 타이틀
    d.text((380, 90), "처 방 전", font=font(30, bold=True), fill="black")

    # 환자정보 테이블
    y0 = 150
    d.rectangle((20, y0, 880, y0 + 140), outline="black", width=1)
    d.text((30, y0 + 10), "요양기관기호: 12345678", font=font(13), fill="black")
    d.line((450, y0, 450, y0 + 140), fill="black", width=1)
    d.text((460, y0 + 10), "요양기관명: OO정형외과의원", font=font(13), fill="black")

    d.line((20, y0 + 45, 880, y0 + 45), fill="black", width=1)
    d.text((30, y0 + 55), "성 명: 김민수 (가짜 데이터)", font=font(13), fill="black")
    d.text((460, y0 + 55), "생년월일: 700101-1", font=font(13), fill="black")

    d.line((20, y0 + 90, 880, y0 + 90), fill="black", width=1)
    d.text((30, y0 + 100), "질병분류기호: M17 (무릎관절증)", font=font(13), fill="black")

    # 처방 테이블
    ty = 330
    d.rectangle((20, ty, 880, ty + 40), outline="black", width=1)
    headers = ["처방 의약품의 명칭", "1회\n투약량", "1일\n투여횟수", "총\n투약일수", "용법"]
    xs = [30, 470, 560, 650, 740]
    for h, x in zip(headers, xs):
        d.text((x, ty + 5), h, font=font(13, bold=True), fill="black")

    rows = [
        ("[급여][649500560] 세레콕시브캡슐200mg", "1", "2", "7", ""),
        ("[급여][642201540] 에페리손염산염정50mg", "1", "3", "7", ""),
        ("[급여][644308830] 라베프라졸나트륨장용정", "1", "1", "7", ""),
        ("[급여][658101480] 조인트콘드로이친캡슐 110/500", "1", "1", "1", "1일 1회 취침전 복용하세요"),
        ("[비급여][643501070] 파스(온습포)", "1", "2", "7", ""),
    ]
    y = ty + 40
    row_h = 55
    for name, amt, freq, days, note in rows:
        d.rectangle((20, y, 880, y + row_h), outline="black", width=1)
        d.text((30, y + 8), name, font=font(13), fill="black")
        d.text((485, y + 20), amt, font=font(13), fill="black")
        d.text((575, y + 20), freq, font=font(13), fill="black")
        d.text((665, y + 20), days, font=font(13), fill="black")
        if note:
            d.text((740, y + 8), note, font=font(11), fill="black")
        y += row_h

    # 하단 조제기관 정보 + QR 자리
    by = y + 40
    d.rectangle((20, by, 880, by + 100), outline="black", width=1)
    d.text((30, by + 10), "사용기간: 교부일부터 (3)일간", font=font(13), fill="black")
    d.text((30, by + 40), "조제기관명:", font=font(13), fill="black")
    d.text((30, by + 65), "조제약사 성명:", font=font(13), fill="black")
    d.rectangle((760, by + 10, 860, by + 90), outline="gray", width=1)
    d.text((775, by + 40), "QR", font=font(16), fill="gray")

    img.save(path)
    print(f"생성 완료: {path}")


if __name__ == "__main__":
    make_official_format_mock("samples/mock_prescription_official.png")
