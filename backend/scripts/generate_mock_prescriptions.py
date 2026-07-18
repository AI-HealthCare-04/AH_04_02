"""
목업 처방전/약봉투 이미지 3종 생성 (실제 환자 정보 없음, 테스트 전용)
서로 다른 레이아웃으로 만들어서 parsing_rules.py가 한 포맷에만
오버피팅되지 않았는지 검증하는 용도.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


# ------------------------------------------------------------------
# 목업 1: 표 형식 처방전 (실제 samples/prescription_01.jpg와 비슷한 스타일)
# ------------------------------------------------------------------
def make_mock_1(path):
    img = Image.new("RGB", (900, 700), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 20), "처 방 전", font=font(28, bold=True), fill="black")
    d.line((30, 65, 870, 65), fill="black", width=2)
    d.text((30, 90), "환자 성명: 홍길동 (개인정보 목업)", font=font(16), fill="black")
    d.text((30, 120), "질병분류기호: I10 (본태성 고혈압)", font=font(16), fill="black")

    d.line((30, 160, 870, 160), fill="gray", width=1)
    headers = ["의약품명", "1회 투약량", "1일 투여횟수", "총 투약일수"]
    xs = [30, 380, 550, 700]
    for h, x in zip(headers, xs):
        d.text((x, 170), h, font=font(15, bold=True), fill="black")
    d.line((30, 200, 870, 200), fill="gray", width=1)

    rows = [
        ("[급여][649500569] 암로디핀정5mg(한미)", "1.00", "1일 1회", "30"),
        ("[급여][642201549] 로자탄칼륨정50mg(종근당)", "1.00", "1일 1회", "30"),
        ("[급여][643501076] 메트포르민정500mg(대웅)", "2.00", "1일 2회", "30"),
    ]
    y = 210
    for name, amt, freq, days in rows:
        d.text((30, y), name, font=font(15), fill="black")
        d.text((380, y), amt, font=font(15), fill="black")
        d.text((550, y), freq, font=font(15), fill="black")
        d.text((700, y), days, font=font(15), fill="black")
        y += 40

    d.text((30, 400), "진단명: 고혈압, 제2형 당뇨병", font=font(16), fill="black")
    img.save(path)


# ------------------------------------------------------------------
# 목업 2: 약봉투 스타일 (한 줄 서술형, 표 없음 — 표1과 완전히 다른 레이아웃)
# ------------------------------------------------------------------
def make_mock_2(path):
    img = Image.new("RGB", (700, 900), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "OO약국", font=font(26, bold=True), fill="black")
    d.line((20, 60, 680, 60), fill="black", width=2)
    d.text((20, 80), "환자: 김철수 (개인정보 목업)", font=font(16), fill="black")
    d.text((20, 110), "조제일자: 2026-07-01", font=font(14), fill="gray")

    d.line((20, 150, 680, 150), fill="gray", width=1)
    lines = [
        "1. [급여][658101482] 아스피린프로텍트정100mg",
        "   1회 1정, 1일 1회, 30일분 복용",
        "",
        "2. [급여][645209871] 심바스타틴정20mg(유한양행)",
        "   1회 1정, 1일 1회 (취침전), 30일분",
        "",
        "3. [급여][622309872] 오메프라졸캡슐20mg",
        "   1회 1캡슐, 1일 1회 (식전), 30일분",
    ]
    y = 170
    for line in lines:
        d.text((20, y), line, font=font(17), fill="black")
        y += 34

    d.text((20, y + 20), "진단명: 관상동맥질환, 위염", font=font(16), fill="black")
    img.save(path)


# ------------------------------------------------------------------
# 목업 3: 손글씨 느낌 + 약어 포함 (엣지케이스 — 표기가 불규칙한 처방전)
# ------------------------------------------------------------------
def make_mock_3(path):
    img = Image.new("RGB", (800, 600), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "처방전 (약식)", font=font(24, bold=True), fill="black")
    d.line((20, 60, 780, 60), fill="black", width=2)

    lines = [
        "Pt: 이영희(모)",
        "Dx: 골관절염, 불면증",
        "",
        "Rx)",
        "1) [급여][601209872] 세레브렉스캡슐200mg 1C bid #14",
        "2) [급여][633409872][향정] 졸피뎀정10mg 1T qd(취침전) #7",
        "3) [급여][611209874] 파모티딘정20mg 1T bid #14",
    ]
    y = 90
    for line in lines:
        d.text((20, y), line, font=font(18), fill="black")
        y += 36

    img.save(path)


if __name__ == "__main__":
    make_mock_1("samples/mock_prescription_table.png")
    make_mock_2("samples/mock_prescription_bag.png")
    make_mock_3("samples/mock_prescription_abbrev.png")
    print("3개 목업 이미지 생성 완료")
