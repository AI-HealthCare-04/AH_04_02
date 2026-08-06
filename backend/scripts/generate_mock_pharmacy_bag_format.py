"""
약봉투/조제 안내서 스타일 목업 생성.
실제 양식 핵심 특징 반영:
- 투약량/횟수/일수가 "1일 3회" 같은 문구가 아니라 순수 숫자 컬럼으로만 표시됨
  (정규식 패턴 매칭이 아니라 표 컬럼 위치 기반 파싱이 필요한 케이스)
- 복약안내가 긴 자유서술문 + 짧은 경고 태그가 섞여 있음
- 약품명 옆에 성분명이 별도 줄로 붙음 (예: "메트포르민염산염 1000mg")
개인정보는 전부 가짜값.
"""

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def tag(d, x, y, text, color):
    w = 12 + len(text) * 13
    d.rounded_rectangle((x, y, x + w, y + 22), radius=4, fill=color)
    d.text((x + 6, y + 3), text, font=font(11), fill="white")
    return x + w + 8


def make_pharmacy_bag_mock(path):
    W, H = 1000, 1000
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # 헤더
    d.text((30, 20), "테스트님", font=font(24, bold=True), fill="black")
    d.text((30, 55), "1980년생 / 여 / 질병기호 E11.9", font=font(13), fill="gray")
    d.text((30, 80), "OO병원   조제일 2026.07.01 / 조제한 약사", font=font(13), fill="gray")
    d.text((650, 30), "테스트약국", font=font(22, bold=True), fill="black")

    d.line((30, 120, 970, 120), fill="black", width=1)
    col_headers = ["약품명/성분", "복약안내", "투약량", "횟수", "일수"]
    xs = [30, 430, 800, 860, 920]
    for h, x in zip(col_headers, xs):
        d.text((x, 130), h, font=font(13, bold=True), fill="black")
    d.line((30, 160, 970, 160), fill="black", width=1)

    drugs = [
        {
            "name": "[급여][649500570] 글루코파지정500mg",
            "class": "[당뇨병 치료제]",
            "ingredient": "메트포르민염산염 500mg",
            "tags": [("쪼개지 마세요", "#e05a5a"), ("씹지 마세요", "#e05a5a")],
            "guide": "식사와 함께 1일 2회 복용하세요. 저혈당 증세가 나타나면 즉시 당분 섭취하세요.",
            "amt": "1", "freq": "2", "days": "30",
        },
        {
            "name": "[급여][642201550] 노바스크정5mg",
            "class": "[고혈압 치료제]",
            "ingredient": "암로디핀베실산염 5mg",
            "tags": [("위장장애 주의", "#e0a25a")],
            "guide": "아침 식후 복용하세요. 어지러움이 있으면 천천히 일어나세요.",
            "amt": "1", "freq": "1", "days": "30",
        },
        {
            "name": "[급여][643501077] 리피토정10mg",
            "class": "[이상지질혈증 치료제]",
            "ingredient": "아토르바스타틴칼슘삼수화물 10.8mg",
            "tags": [("근육통 주의", "#e0a25a")],
            "guide": "저녁 식후 복용하세요. 간기능 이상징후가 나타나면 전문가와 상의하세요.",
            "amt": "1", "freq": "1", "days": "30",
        },
    ]

    y = 175
    for drug in drugs:
        row_h = 130
        d.line((30, y + row_h, 970, y + row_h), fill="lightgray", width=1)

        d.text((30, y), drug["name"], font=font(16, bold=True), fill="black")
        d.text((30, y + 24), drug["class"], font=font(12), fill="#3070b0")
        d.text((30, y + 46), drug["ingredient"], font=font(12), fill="gray")

        tx = 430
        for label, color in drug["tags"]:
            tx = tag(d, tx, y, label, color)

        # 복약안내 (줄바꿈 처리, 폭 제한 없이 단순 2줄 분해)
        guide_lines = [drug["guide"][:28], drug["guide"][28:]]
        gy = y + 30
        for line in guide_lines:
            if line:
                d.text((430, gy), line, font=font(12), fill="black")
                gy += 20

        d.text((800, y + 40), drug["amt"], font=font(14), fill="black")
        d.text((860, y + 40), drug["freq"], font=font(14), fill="black")
        d.text((920, y + 40), drug["days"], font=font(14), fill="black")

        y += row_h

    img.save(path)
    print(f"생성 완료: {path}")


if __name__ == "__main__":
    make_pharmacy_bag_mock("samples/mock_pharmacy_bag_format.png")
