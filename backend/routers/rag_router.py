"""
rag_router.py — 담당: 김영혜

[7/8] run_rag_stub()을 run_rag()로 바꾸고 async def로 전환했습니다.
이유: rag의 실제 파이프라인(LangChain OpenAI 호출·ChromaDB 검색)은 I/O 대기가
있는 동기 코드라, 여러 사용자가 동시에 요청할 때 이벤트 루프를 막지 않으려면 비동기
경계에서 스레드로 실행해야 합니다 (아래 _generate_via_rag 참고).

⚠️ records_router.py에서 이 함수를 부를 때 반드시 `await run_rag(...)`로 불러야 합니다.
await 없이 `run_rag(...)`만 호출하면 예외 없이 coroutine 객체만 만들고 실제로는
실행되지 않는, 조용히 실패하는 버그가 됩니다 (권순현님이 지적해주신 부분).

[7/8 상태] .env에 RAG_PROVIDER=real을 명시적으로 켠 경우에만 rag 실제
파이프라인을 시도합니다 (OCR_PROVIDER 컨벤션과 동일). 기본값(미설정)은 지금까지와
동일한 가짜 데이터입니다 — "의존성이 우연히 설치돼 있으면 결과가 조용히 바뀌는" 것을
막기 위해 일부러 의존성 존재 여부만으로는 자동 전환하지 않습니다. 실제 파이프라인의
출력은 자유 텍스트(LLM 생성)라 지금의 고정 JSON 모양(diet.avoid/exercise.type 등,
Result.tsx가 그대로 소비 중)과 다르므로, RAG_PROVIDER=real은 Result.tsx가 새 모양을
받을 준비가 됐을 때(소정님과 합의 후)만 켜주세요.

[7/6] 로직을 run_rag_stub() 함수로 분리했습니다 — /rag/test/{record_id}(개별 테스트용)와
records_router.py(업로드→OCR→가이드 한번에 처리)가 이 함수를 같이 씁니다.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from fastapi import APIRouter, Depends, HTTPException
from models import GuideResult, MedicalRecord, OcrResult
from sqlmodel import Session, select

router = APIRouter(prefix="/rag", tags=["RAG"])

# RAG_PROVIDER=real일 때만 rag 실제 파이프라인을 시도한다 (OCR_PROVIDER와 동일 패턴).
# 기본값은 항상 기존 가짜 데이터 — 의존성이 설치돼 있다는 사실만으로 동작이 바뀌지 않는다.
_RAG_PROVIDER = os.environ.get("RAG_PROVIDER", "stub")

_RAG_AVAILABLE = False
if _RAG_PROVIDER == "real":
    # rag/은 별도 프로토타입 디렉터리(자체 .venv·requirements)라 backend가 항상
    # 그 의존성(langchain/chromadb/sentence-transformers 등)을 갖고 있진 않다. 없으면
    # (ImportError) 또는 import 자체가 실패하면(예: Python 버전 비호환) 폴백으로 내려간다.
    _RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
    if _RAG_DIR.is_dir() and str(_RAG_DIR) not in sys.path:
        sys.path.insert(0, str(_RAG_DIR))

    try:
        from rag.rag_chain import generate_guides_from_medications as _generate_guides

        _RAG_AVAILABLE = True
    except Exception:  # noqa: BLE001 — 의존성 미설치/버전 비호환 등 어떤 이유로든 실패하면 폴백
        _RAG_AVAILABLE = False


def _fake_guide_payload(ocr_items: list[OcrResult]) -> tuple[dict, dict, list]:
    """실제 파이프라인 연동 전까지 쓰는 흐름 확인용 가짜 데이터 (Result.tsx가 기대하는 모양)."""
    medication_guide = {
        "drugs": [
            {"drug_name": item.drug_name, "dosage_text": item.dosage, "caution": "테스트 주의사항"}
            for item in ocr_items
        ]
    }
    lifestyle_guide = {
        "diagnosis": ocr_items[0].diagnosis,
        "diet": {"avoid": ["짠 음식"], "drug_specific": []},
        "exercise": {"type": "가벼운 걷기", "duration": "30분", "intensity": "낮음"},
    }
    source_refs = [{"title": "테스트 출처", "url": "https://example.com"}]
    return medication_guide, lifestyle_guide, source_refs


def _generate_via_rag(ocr_items: list[OcrResult]) -> tuple[dict, dict, list] | None:
    """rag 실제 파이프라인 호출. 실패하거나 사용 불가하면 None(호출부가 폴백 처리)."""
    if not _RAG_AVAILABLE:
        return None

    medications = [
        {
            "drug_name": item.drug_name,
            "dosage": item.dosage,
            "frequency": item.frequency,
            "diagnosis": item.diagnosis,
            "drug_class": item.drug_class,
            "confidence": item.confidence,
        }
        for item in ocr_items
    ]
    guides = _generate_guides(medications)  # 동기 함수(LLM/벡터DB 호출) — 반드시 스레드에서 실행할 것

    medication_guide = {
        "drugs": [
            {
                "drug_name": g.drug_name,
                "medication_guide": g.medication_guide,
                "precautions": g.precautions,
                "review_required": g.review_required,
                "review_flags": g.review_flags,
            }
            for g in guides
        ]
    }
    lifestyle_guide = {
        "diagnosis": ocr_items[0].diagnosis,
        "guides": [g.lifestyle_guide for g in guides],
    }
    source_refs = [
        {
            "drug_name": g.drug_name,
            "item_name": ref.item_name,
            "field": ref.field,
            "hira_standard_code": ref.hira_standard_code,
            "hira_atc_code": ref.hira_atc_code,
            "hira_permit_date": ref.hira_permit_date,
            "hira_active": ref.hira_active,
            "permit_kind_code": ref.permit_kind_code,
            "permit_active": ref.permit_active,
        }
        for g in guides
        for ref in g.source_refs
    ] + [
        {"drug_name": g.drug_name, "disease": ref.disease, "category": ref.category, "source": ref.source}
        for g in guides
        for ref in g.lifestyle_source_refs
    ] + [
        # [7/10] DUR 병용금기 경고 — 같은 처방전의 다른 약과 실제로 금기 관계일 때만 존재.
        # [7/13] API 대신 로컬 CSV 조회로 전환(dur_master.py) — backend/data/에 해당 CSV가
        # 없으면 이 리스트는 조용히 빈 상태로 남는다(CONTRACT.md §7).
        {
            "drug_name": g.drug_name,
            "mixture_item_name": w.mixture_item_name,
            "prohbt_content": w.prohbt_content,
            "source": w.source,
        }
        for g in guides
        for w in g.dur_warnings
    ] + [
        # [7/13 추가] DUR 노인주의/연령금기/임부금기 — 다른 약과 무관하게 이 약 자체의 주의사항.
        {
            "drug_name": g.drug_name,
            "dur_category": c.category,
            "dur_detail": c.detail,
            "dur_extra": c.extra,
        }
        for g in guides
        for c in g.dur_cautions
    ]
    return medication_guide, lifestyle_guide, source_refs


async def run_rag(record_id: int, session: Session) -> GuideResult:
    """
    OCR 결과로 복약·생활습관 가이드를 생성해 GuideResult로 저장합니다.

    (medication_guide/lifestyle_guide/source_refs는 SQLite에 JSON 타입이 없어서
     json.dumps()로 문자열로 저장 — 꺼낼 때는 json.loads() 사용)
    """
    # session.exec()는 동기 SQLModel 호출이라, async def 안에서 그대로 부르면 이벤트
    # 루프를 막는다 — 아래 _generate_via_rag(LLM/벡터DB 호출)와 동일한 이유로 스레드에서 실행.
    ocr_items = await asyncio.to_thread(
        lambda: session.exec(select(OcrResult).where(OcrResult.record_id == record_id)).all()
    )
    if not ocr_items:
        raise ValueError("해당 record_id의 OCR 결과가 없어요. 먼저 OCR이 실행되어야 합니다.")

    # generate_guides_from_medications는 동기 함수(OpenAI/Chroma 호출)라, 이벤트 루프를
    # 막지 않도록 스레드에서 실행한다. RAG_PROVIDER=real이 아니면 항상 폴백(가짜 데이터).
    result = None
    if _RAG_AVAILABLE:
        result = await asyncio.to_thread(_generate_via_rag, ocr_items)

    medication_guide, lifestyle_guide, source_refs = result or _fake_guide_payload(ocr_items)

    guide = GuideResult(
        record_id=record_id,
        medication_guide=json.dumps(medication_guide, ensure_ascii=False),
        lifestyle_guide=json.dumps(lifestyle_guide, ensure_ascii=False),
        source_refs=json.dumps(source_refs, ensure_ascii=False),
    )
    def _save_guide() -> None:
        session.add(guide)
        session.commit()
        session.refresh(guide)

    await asyncio.to_thread(_save_guide)
    return guide


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "김영혜"}


@router.post("/test/{record_id}")
async def stub_generate_guide(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """RAG만 따로 테스트하고 싶을 때 쓰는 엔드포인트 (실제 흐름은 POST /records 사용)

    [2026-07-15] 인가 검증 없이 record_id만으로 누구나 타인 처방전의 가이드를 생성할 수
    있던 IDOR을 다른 라우터(ocr_router 등)와 동일한 require_actor_patient_access 패턴으로 막음(REQ-031)."""
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "처방전을 찾을 수 없어요")
    await asyncio.to_thread(require_actor_patient_access, record.patient_id, actor, session)

    try:
        guide = await run_rag(record_id, session)
    except ValueError as e:
        raise HTTPException(404, str(e))

    return {
        "guide_id": guide.id,
        "note": "⚠️ 가짜 데이터입니다 — 실제 RAG 연동 전까지만 사용" if not _RAG_AVAILABLE else "실제 RAG 파이프라인 결과입니다",
    }
