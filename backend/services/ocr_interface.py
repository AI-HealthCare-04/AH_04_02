from __future__ import annotations

"""
OCR Provider 추상화 레이어
- CLOVA OCR 승인이 늦어져도 Mock으로 ②(RAG) ③(백엔드)이 바로 개발 시작 가능하게 함
- CLOVA 장애/지연 시 Tesseract 등으로 무중단 전환 가능하게 인터페이스 고정

사용 예:
    provider = get_ocr_provider("mock")   # 오늘은 이걸로 시작
    # provider = get_ocr_provider("clova")  # CLOVA 키 발급되면 여기로 전환
    result = provider.extract("samples/prescription_01.jpg")
"""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from services.drug_reference import get_drug_class
from services.parsing_rules import parse_prescription

# ------------------------------------------------------------------
# 1. 출력 스키마 (Day2에 ①②③이 이걸 기준으로 합의·고정 예정)
# ------------------------------------------------------------------

@dataclass
class MedicationItem:
    drug_name: str
    dosage: str            # 예: "1정" (1회 사용량 — 환자가 한 번에 먹는 개수/단위)
    frequency: str         # 예: "3회" (1일 투약횟수 — "1일"은 라벨에 있어 값엔 안 넣음)
    diagnosis: str          # 예: "고혈압"
    drug_class: str = ""    # 약효분류, 예: "이뇨제"
    drug_code: str = ""     # [급여/비급여][코드] 패턴에서 추출한 코드
    total_days: str = ""    # [2026-07-18 추가] 총 투약일수, 예: "30일"
    confidence: float = 0.0  # 0.0 ~ 1.0
    dose_amount: str = ""  # [2026-07-25 추가] 1회 투여량 — 예: "5mg" (mg/ml 등 질량·부피 단위)


@dataclass
class OCRResult:
    raw_text: str
    medications: list[MedicationItem] = field(default_factory=list)
    overall_confidence: float = 0.0
    review_required: bool = False  # confidence < 0.80 이면 True (REQ-011)
    source: Literal["clova", "mock", "tesseract"] = "mock"

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "medications": [m.__dict__ for m in self.medications],
            "overall_confidence": self.overall_confidence,
            "review_required": self.review_required,
            "source": self.source,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 1-b. 파싱 헬퍼 — raw_text → MedicationItem 리스트
# ------------------------------------------------------------------

def _build_medications(raw_text: str, confidence: float, fields: list | None = None) -> list:
    meds, diagnosis = parse_prescription(raw_text, fields)
    return [
        MedicationItem(
            drug_name=m["drug_name"],
            dosage=m["dosage"],
            frequency=m["frequency"],
            diagnosis=diagnosis,
            drug_class=m.get("drug_class") or get_drug_class(m["drug_name"]),
            drug_code=m.get("drug_code", ""),
            total_days=m.get("total_days", ""),
            confidence=confidence,
            dose_amount=m.get("dose_amount", ""),
        )
        for m in meds
    ]


# ------------------------------------------------------------------
# 1-c. bounding box 좌표 기반 행 재구성
# ------------------------------------------------------------------

def _sort_fields_by_bbox(fields: list) -> list:
    """CLOVA fields를 boundingPoly 중심 좌표 기준으로 행→열 순서로 재정렬.

    CLOVA는 표(table) 레이아웃에서 열(column) 단위로 텍스트를 출력하는 경우가 있어
    약품명·용량·횟수가 뒤섞인다. 이 함수는 각 field의 bounding box 중심 y좌표로
    행을 그룹핑한 뒤 x좌표로 정렬해 자연스러운 읽기 순서로 복원한다.

    boundingPoly가 없는 field(mock 등)는 원래 순서 그대로 유지된다.
    """
    if not fields:
        return fields

    def _center(f: dict) -> tuple:
        verts = f.get("boundingPoly", {}).get("vertices", [])
        if not verts:
            return (0.0, 0.0)
        return (
            sum(v.get("x", 0) for v in verts) / len(verts),
            sum(v.get("y", 0) for v in verts) / len(verts),
        )

    def _height(f: dict) -> float:
        verts = f.get("boundingPoly", {}).get("vertices", [])
        if not verts:
            return 0.0
        ys = [v.get("y", 0) for v in verts]
        return float(max(ys) - min(ys))

    # boundingPoly가 하나도 없으면 정렬 의미 없음 — 원본 반환
    if all(_height(f) == 0.0 for f in fields):
        return fields

    # 행 그룹핑 허용 오차: 필드 높이 중앙값 × 0.5
    heights = sorted(_height(f) for f in fields if _height(f) > 0)
    row_tol = heights[len(heights) // 2] * 0.5

    # 1차: y 중심 오름차순 정렬
    fields_by_y = sorted(fields, key=lambda f: _center(f)[1])

    # 2차: 인접 필드를 동일 행으로 묶기
    rows: list = []
    row_anchor_y = None

    for f in fields_by_y:
        cy = _center(f)[1]
        if row_anchor_y is None or abs(cy - row_anchor_y) > row_tol:
            rows.append([f])
            row_anchor_y = cy
        else:
            rows[-1].append(f)

    # 3차: 행 내부를 x 중심 오름차순 정렬 후 펼치기
    result = []
    for row in rows:
        row.sort(key=lambda f: _center(f)[0])
        result.extend(row)
    return result


# ------------------------------------------------------------------
# 1-d. 한글+영문 혼용 약품명이 bounding box 2개로 쪼개져 인식되는 문제 보정
# ------------------------------------------------------------------
# [2026-07-28 추가] "글루코파지XR"처럼 한글 브랜드명 뒤에 영문 방출제어 접미사(서방정
# 계열: SR/XR/ER/CR/MR/IR/LA/CD/SA)가 붙는 약품명은, CLOVA가 한글 부분과 영문 부분을
# 별개의 텍스트 필드(bounding box)로 인식하는 경우가 실제로 있다 — 스크립트(문자 체계)가
# 바뀌는 지점에서 필드 경계를 나누는 경향 때문으로 보인다. 그대로 두면 raw_text에
# 공백으로 이어붙어("글루코파지 XR") 서로 다른 두 개의 텍스트로 남고, parsing_rules.py의
# DRUG_NAME_RE는 이 둘을 하나의 약품명으로 되돌릴 방법이 없어 "글루코파지"와 "XR"이
# 각각 별도 항목으로(혹은 "XR"은 아예 매칭 실패로 버려져) 처리된다.
# 이 함수는 아직 raw_text로 펼치기 전, boundingPoly 좌표가 남아있는 시점에 실행해
# (1) 같은 행(y좌표 겹침)에 있고 (2) 가로 간격이 글자 높이 대비 좁으며 (3) 한쪽은
# 한글 위주, 다른 쪽은 순수 대문자 영문 1~3자(방출제어 접미사로 보임)인 인접 필드 쌍을
# 공백 없이 하나의 필드로 합친다. 세 조건을 전부 만족해야만 합치므로, 원래부터 공백을
# 두고 떨어져 있던 서로 다른 두 약품명까지 잘못 합치는 일은 없다.
_HANGUL_RE = re.compile(r"[가-힣]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_RELEASE_SUFFIX_RE = re.compile(r"^[A-Z]{1,3}$")  # SR/XR/ER/CR/MR/IR/LA/CD/SA 등


def _merge_split_drug_name_fields(fields: list) -> list:
    if len(fields) < 2:
        return fields

    def _bbox(f: dict) -> list:
        return f.get("boundingPoly", {}).get("vertices", [])

    def _should_merge(a: dict, b: dict) -> bool:
        text_a, text_b = a.get("inferText", ""), b.get("inferText", "")
        if not text_a or not text_b:
            return False
        # 한쪽은 한글이 섞여 있고(영문은 없어도 됨), 다른 쪽은 순수 대문자 영문 1~3자
        # (방출제어 접미사 패턴)여야 병합 대상으로 본다 — 조건이 좁아야 무관한 두
        # 약품명을 실수로 합치지 않는다.
        if not _HANGUL_RE.search(text_a):
            return False
        if not _RELEASE_SUFFIX_RE.match(text_b):
            return False

        verts_a, verts_b = _bbox(a), _bbox(b)
        if not verts_a or not verts_b:
            return False

        top_a, bottom_a = min(v.get("y", 0) for v in verts_a), max(v.get("y", 0) for v in verts_a)
        top_b, bottom_b = min(v.get("y", 0) for v in verts_b), max(v.get("y", 0) for v in verts_b)
        height = max(bottom_a - top_a, bottom_b - top_b, 1)
        overlap = min(bottom_a, bottom_b) - max(top_a, top_b)
        if overlap < height * 0.5:  # 같은 행이 아니면 병합하지 않음
            return False

        right_a = max(v.get("x", 0) for v in verts_a)
        left_b = min(v.get("x", 0) for v in verts_b)
        gap = left_b - right_a
        # 글자 높이의 40% 이내로 붙어있어야 "한 단어"로 본다 — 일반적인 단어 사이
        # 공백은 보통 이보다 넓게 찍힌다.
        return -height * 0.1 <= gap <= height * 0.4

    merged: list = []
    i = 0
    while i < len(fields):
        current = fields[i]
        if i + 1 < len(fields) and _should_merge(current, fields[i + 1]):
            nxt = fields[i + 1]
            combined = dict(current)
            combined["inferText"] = current.get("inferText", "") + nxt.get("inferText", "")
            combined["inferConfidence"] = min(
                current.get("inferConfidence", 1.0), nxt.get("inferConfidence", 1.0)
            )
            merged.append(combined)
            i += 2
        else:
            merged.append(current)
            i += 1
    return merged


# ------------------------------------------------------------------
# 2. 추상 인터페이스 — 모든 OCR 구현체는 이 계약을 따름
# ------------------------------------------------------------------

class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image_path: str) -> OCRResult:
        """이미지 경로를 받아 OCRResult를 반환한다."""
        raise NotImplementedError

    @staticmethod
    def _apply_review_flag(result: OCRResult, threshold: float = 0.80) -> OCRResult:
        result.review_required = result.overall_confidence < threshold
        return result


# ------------------------------------------------------------------
# 3. Mock 구현체 — 오늘(Day1)부터 바로 쓸 수 있음
# ------------------------------------------------------------------

class MockOCRProvider(OCRProvider):
    """실제 OCR 없이 고정된 샘플 결과를 반환. ②③이 이걸로 선행 개발."""

    def extract(self, image_path: str) -> OCRResult:
        # [7/9] 일부러 인식 정확도가 낮은 항목을 섞어둠 — review_required가 실제로
        # 트리거돼야 처방전확인(PrescriptionReview.tsx) 화면을 흐름상 볼 수 있음.
        # "암로디민"(오타), "1"(복용량 단위 누락)은 실제 OCR에서 흔한 오류 패턴.
        confidences = [0.65, 0.72]
        result = OCRResult(
            raw_text="암로디민 5mg 1정 1일 1회 / 고혈압, 제2형 당뇨병 / 메트포르민 500mg 1일 2회",
            medications=[
                MedicationItem(
                    drug_name="암로디민 5mg",
                    dosage="1정",
                    frequency="1회",
                    diagnosis="고혈압",
                    drug_class="칼슘채널차단제",
                    total_days="30일",
                    confidence=confidences[0],
                ),
                MedicationItem(
                    drug_name="메트포르민 500mg",
                    dosage="1",
                    frequency="2회",
                    diagnosis="제2형 당뇨병",
                    drug_class="당뇨병용제(비구아니드)",
                    total_days="30일",
                    confidence=confidences[1],
                ),
            ],
            overall_confidence=round(sum(confidences) / len(confidences), 4),
            source="mock",
        )
        return self._apply_review_flag(result)


# ------------------------------------------------------------------
# 4. CLOVA 구현체 — 키 발급되면 TODO만 채우면 됨
# ------------------------------------------------------------------

class ClovaOCRProvider(OCRProvider):
    """네이버클라우드 CLOVA General OCR 연동.

    키는 코드에 하드코딩하지 말고 .env / 환경변수로만 주입한다.
    .env.example을 복사해서 .env로 만들고 값 채운 뒤 python-dotenv로 로드해서 쓰면 된다.
    """

    def __init__(self, api_url: str | None = None, secret_key: str | None = None):
        self.api_url = api_url or os.environ.get("CLOVA_OCR_API_URL", "")
        self.secret_key = secret_key or os.environ.get("CLOVA_OCR_SECRET_KEY", "")

    def extract(self, image_path: str) -> OCRResult:
        if not self.api_url or not self.secret_key:
            raise RuntimeError(
                "CLOVA_OCR_API_URL / CLOVA_OCR_SECRET_KEY 환경변수가 없습니다. "
                ".env 파일을 만들고 load_dotenv()로 로드했는지 확인하세요. "
                "키가 없으면 get_ocr_provider('mock')을 대신 쓰세요."
            )

        import base64
        import time
        import uuid

        import requests

        from services.image_preprocessing import preprocess_prescription_image

        ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "jpg"
        with open(image_path, "rb") as f:
            raw_bytes = f.read()
        # [2026-07-28 추가] 스마트폰 카메라로 직접 촬영한 사진(조명 불균일·기울어짐·
        # 저해상도·노이즈)은 스캔본 수준의 원본 파일보다 CLOVA 인식률이 크게 떨어진다 —
        # 전송 전에 보정한다. 전처리가 실패해도(디코딩 불가·라이브러리 미설치 등) 원본
        # 바이트를 그대로 돌려주므로 이 단계 자체가 OCR을 막는 일은 없다.
        image_bytes, ext = preprocess_prescription_image(raw_bytes, ext)
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [
                {"format": ext, "name": "prescription", "data": image_b64}
            ],
        }
        headers = {
            "X-OCR-SECRET": self.secret_key,
            "Content-Type": "application/json",
        }

        response = requests.post(self.api_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        body = response.json()

        fields = body.get("images", [{}])[0].get("fields", [])
        fields = _sort_fields_by_bbox(fields)  # bounding box 기반 행 재구성
        fields = _merge_split_drug_name_fields(fields)  # 한글+영문 혼용 약품명 분리 인식 보정
        raw_text = " ".join(f.get("inferText", "") for f in fields)
        confidences = [f.get("inferConfidence", 0.0) for f in fields if "inferConfidence" in f]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        result = OCRResult(
            raw_text=raw_text,
            medications=_build_medications(raw_text, round(overall_confidence, 4), fields),
            overall_confidence=round(overall_confidence, 4),
            source="clova",
        )
        return self._apply_review_flag(result)


# ------------------------------------------------------------------
# 5. 폴백 구현체 — CLOVA +2일 이상 지연 시 무중단 전환용 뼈대
# ------------------------------------------------------------------

class TesseractOCRProvider(OCRProvider):
    """CLOVA 장애/지연 시 폴백. 로컬 tesseract 설치 필요."""

    def extract(self, image_path: str) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise RuntimeError(
                "pytesseract/Pillow 미설치. `pip install pytesseract pillow` 후 "
                "`brew install tesseract`(mac) 필요"
            ) from e

        text = pytesseract.image_to_string(Image.open(image_path), lang="kor+eng")
        result = OCRResult(
            raw_text=text,
            medications=_build_medications(text, 0.0),
            overall_confidence=0.0,
            source="tesseract",
        )
        return self._apply_review_flag(result)


# ------------------------------------------------------------------
# 6. 팩토리 함수
# ------------------------------------------------------------------

def get_ocr_provider(kind: Literal["mock", "clova", "tesseract"] = "mock") -> OCRProvider:
    if kind == "mock":
        return MockOCRProvider()
    if kind == "clova":
        return ClovaOCRProvider()
    if kind == "tesseract":
        return TesseractOCRProvider()
    raise ValueError(f"알 수 없는 provider: {kind}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    import sys
    kind = sys.argv[1] if len(sys.argv) > 1 else "mock"
    image = sys.argv[2] if len(sys.argv) > 2 else "samples/prescription_01.jpg"

    provider = get_ocr_provider(kind)
    result = provider.extract(image)
    print(result.to_json())
