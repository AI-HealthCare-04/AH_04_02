# -*- coding: utf-8 -*-
"""
한방 첩약 처방전 목업 생성 — _parse_oriental_format() 파서 검증용.
'약재명 중량g' 반복 패턴을 포함한 한의원 처방전 형식.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

FONT_PATH  = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
OUTPUT     = Path(__file__).parent / "mock_oriental_prescription.png"


def font(size, bold=False):
    # AppleSDGothicNeo는 index 0=Regular, 1=Bold 등 여러 weight 포함
    idx = 1 if bold else 0
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def make():
    W, H = 860, 1100
    img  = Image.new("RGB", (W, H), "white")
    d    = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        d.rectangle((x0, y0, x1, y1), outline="black", width=1)

    def text(x, y, t, size=14, bold=False):
        d.text((x, y), t, font=font(size, bold), fill="black")

    def hline(y, x0=20, x1=840):
        d.line((x0, y, x1, y), fill="black", width=1)

    def vline(x, y0, y1):
        d.line((x, y0, x, y1), fill="black", width=1)

    # ── 헤더 ──
    box(20, 20, 840, 60)
    text(30, 30, "[처방기관] OO한의원   [처방명] 쌍화탕 가감방", size=13)

    text(340, 80, "한 방 처 방 전", size=26, bold=True)

    # ── 환자정보 ──
    box(20, 130, 840, 210)
    text(30, 140, "성명: 정한방 (가짜 데이터)", size=13)
    vline(420, 130, 210)
    text(430, 140, "생년월일: 1965-03-12", size=13)
    hline(175, x0=20, x1=840)
    text(30, 180, "조제일자: 2026-07-09", size=13)
    text(430, 180, "처방번호: HM-20260709-001", size=13)

    # ── 처방 요약 ──
    box(20, 230, 840, 270)
    text(30, 242, "처방명: 쌍화탕(雙和湯) 가감방   제수: 20첩(봉)   복용법: 1일 2회 식후 30분 복용", size=13)

    # ── 약재 목록 헤더 ──
    box(20, 290, 840, 330)
    text(30, 302,  "약재명",    size=14, bold=True)
    text(200, 302, "중량",      size=14, bold=True)
    text(300, 302, "약재명",    size=14, bold=True)
    text(480, 302, "중량",      size=14, bold=True)
    text(580, 302, "약재명",    size=14, bold=True)
    text(740, 302, "중량",      size=14, bold=True)
    vline(190, 290, 330)
    vline(290, 290, 330)
    vline(470, 290, 330)
    vline(570, 290, 330)
    vline(730, 290, 330)

    # ── 약재 데이터 (3열 × n행) ──
    herbs = [
        ("당귀(當歸)",  "8g"),  ("천궁(川芎)",  "4g"),  ("작약(芍藥)",  "4g"),
        ("숙지황(熟地黃)", "8g"),  ("황기(黃芪)",  "6g"),  ("백출(白朮)",  "4g"),
        ("백복령(白茯苓)", "4g"),  ("감초(甘草)",  "2g"),  ("계피(桂皮)",  "2g"),
        ("생강(生薑)",  "4g"),  ("대추(大棗)",  "4g"),  ("인삼(人蔘)",  "4g"),
    ]

    ROW_H = 40
    y = 330
    for i in range(0, len(herbs), 3):
        box(20, y, 840, y + ROW_H)
        vline(190, y, y + ROW_H)
        vline(290, y, y + ROW_H)
        vline(470, y, y + ROW_H)
        vline(570, y, y + ROW_H)
        vline(730, y, y + ROW_H)
        for j, (h_name, h_dose) in enumerate(herbs[i:i+3]):
            col_x = [30, 300, 580][j]
            dose_x = [200, 480, 740][j]
            text(col_x, y + 10, h_name, size=13)
            text(dose_x, y + 10, h_dose, size=13)
        y += ROW_H

    # ── 복약 지도 ──
    box(20, y + 20, 840, y + 160)
    text(30, y + 30, "복약 지도", size=14, bold=True)
    hline(y + 55, x0=20, x1=840)
    lines = [
        "• 매 식후 30분에 따뜻하게 데워서 한 봉씩 드세요.",
        "• 하루 두 번, 아침과 저녁으로 나누어 복용하시면 됩니다.",
        "• 냉장 보관 후 데워 드시길 권합니다.",
        "• 주의사항: 복용 중 무, 녹두는 피해주세요.",
    ]
    for k, ln in enumerate(lines):
        text(30, y + 65 + k * 22, ln, size=12)

    # ── 하단 서명 ──
    box(20, y + 180, 840, y + 230)
    text(30, y + 192, "처방 의사: OO한의원 원장 (인)", size=13)
    text(560, y + 192, "면허번호: 한의사-123456", size=13)

    img.save(OUTPUT)
    print(f"저장 완료: {OUTPUT}")


if __name__ == "__main__":
    make()
