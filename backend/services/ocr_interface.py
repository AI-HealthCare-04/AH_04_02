# -*- coding: utf-8 -*-
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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal
import json
import os

from services.parsing_rules import parse_prescription
from services.drug_reference import get_drug_class


# ------------------------------------------------------------------
# 1. 출력 스키마 (Day2에 ①②③이 이걸 기준으로 합의·고정 예정)
# ------------------------------------------------------------------

@dataclass
class MedicationItem:
    drug_name: str
    dosage: str            # 예: "500mg" (1회 투약량)
    frequency: str         # 예: "3회" (1일 투약횟수 — "1일"은 라벨에 있어 값엔 안 넣음)
    diagnosis: str          # 예: "고혈압"
    drug_class: str = ""    # 약효분류, 예: "이뇨제"
    drug_code: str = ""     # [급여/비급여][코드] 패턴에서 추출한 코드
    total_days: str = ""    # [2026-07-18 추가] 총 투약일수, 예: "30일"
    confidence: float = 0.0  # 0.0 ~ 1.0


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

def _build_medications(raw_text: str, confidence: float) -> list:
    meds, diagnosis = parse_prescription(raw_text)
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
        # "암로디민"(오타), "500"(단위 누락)은 실제 OCR에서 흔한 오류 패턴.
        confidences = [0.65, 0.72]
        result = OCRResult(
            raw_text="암로디민 5mg 1일 1회 / 고혈압, 제2형 당뇨병 / 메트포르민 500 1일 2회",
            medications=[
                MedicationItem(
                    drug_name="암로디민 5mg",
                    dosage="5mg",
                    frequency="1회",
                    diagnosis="고혈압",
                    drug_class="칼슘채널차단제",
                    total_days="30일",
                    confidence=confidences[0],
                ),
                MedicationItem(
                    drug_name="메트포르민 500mg",
                    dosage="500",
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

        ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "jpg"
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

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
        raw_text = " ".join(f.get("inferText", "") for f in fields)
        confidences = [f.get("inferConfidence", 0.0) for f in fields if "inferConfidence" in f]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        result = OCRResult(
            raw_text=raw_text,
            medications=_build_medications(raw_text, round(overall_confidence, 4)),
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
