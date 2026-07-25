"""
ocr_router.py — 담당: 권순현

[7/8 통합] 권순현님 PR #9의 실제 CLOVA 연동 로직을 backend/ 구조에 맞춰 통합.
핵심 로직을 run_ocr() 함수로 분리해서 이 파일의 /ocr/test(개별 테스트용)와
records_router.py(실제 업로드→OCR→가이드 한 번에 처리) 양쪽에서 재사용합니다.

[7/8 추가] OCR_PROVIDER 환경변수로 clova/mock 전환 가능하게 함
— CLOVA 키 발급 전까지 팀 전체가 파이프라인을 mock으로 테스트할 수 있게 하기 위함
  (.env에 OCR_PROVIDER=mock 추가하면 됨, 없으면 기본값 clova)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests.exceptions
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

# ocr_interface.py 등은 backend/ 루트(main.py와 같은 위치)에 있어서 별도 sys.path 조작 불필요
# (uvicorn을 backend/ 폴더에서 실행하면 그 폴더 자체가 이미 import 루트가 됨)
_ROOT = Path(__file__).parent.parent
from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from models import MedicalRecord, OcrResult
from services.drug_matcher import MATCH_THRESHOLD, match_drug
from services.drug_reference import get_drug_info
from services.ocr_interface import get_ocr_provider  # noqa: E402
from services.parsing_rules import extract_prescription_date

# [2026-07-20 추가, 담당: 김영혜] /drug-info(DrugDetail.tsx)에 사용상의 주의사항·부작용·
# 상호작용·보관법을 채워주기 위해 rag/ 패키지의 e약은요·DUR 클라이언트를 재사용한다.
# chat_router.py의 온디맨드 DUR 조회와 동일한 패턴 — HIRA/e약은요 정적 파일
# (services/drug_reference.py)엔 이 필드들이 애초에 없어서(품목 매칭·분류 전용) 새
# 데이터 소스가 필요했다.
_RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
if _RAG_DIR.is_dir() and str(_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(_RAG_DIR))

router = APIRouter(prefix="/ocr", tags=["OCR"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# [2026-07-25 추가] 처방전 원본 사진 저장 — 지금까지는 OCR 텍스트만 남기고 사진 자체는
# 버렸는데(image_path에 원본 파일명만 기록), 보호자·기관이 수정을 요청할 때 원본을
# 참고할 방법이 없었다. 로컬 디스크에 record별로 저장하고, image_path에는 실제 경로를
# 남긴다. 클라우드 저장소 전환은 나중에(팀 논의) — 지금은 가장 단순한 형태로 우선 연결.
_UPLOAD_DIR = _ROOT / "uploads" / "prescriptions"


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "권순현"}


def _fetch_permit_precautions(candidates: list[str]) -> list[str]:
    """허가정보 상세(search_permit_detail)의 "사용상의 주의사항" 원문 — 후보 이름을
    순서대로 시도해 처음 걸리는 것만 쓴다."""
    # [2026-07-20] "사용상의 주의사항"이라는 정확한 명칭의 필드는 e약은요(atpn_qesitm,
    # 그냥 "주의사항"으로 라벨링됨)가 아니라 허가정보 상세(search_permit_detail의
    # nb_doc_data)에 있다 — mfds_client.py에 이미 "제품허가정보로 사용상의 주의사항
    # 조회 가능한지 확인 요청"이라는 주석까지 있는, 이 목적으로 만들어진 함수다. 처음에
    # 이걸 빠뜨리고 e약은요 필드만 썼었다 — 공식 허가사항 원문을 우선 소스로 추가한다.
    precaution_parts: list[str] = []
    try:
        from rag.mfds_client import parse_doc_sections, search_permit_detail

        for candidate in candidates:
            permit_hits = search_permit_detail(candidate, num_of_rows=1)
            if permit_hits and permit_hits[0].nb_doc_data:
                sections = parse_doc_sections(permit_hits[0].nb_doc_data)
                for title, text in sections:
                    precaution_parts.append(f"[사용상의 주의사항 - {title}] {text}" if title else text)
                break
    except Exception:  # noqa: BLE001 — 키 미설정/네트워크 실패/미등재 약품명 등 어떤 이유로든 조용히 폴백
        pass
    return precaution_parts


def _fetch_eyakeun_info(candidates: list[str]) -> dict:
    """e약은요(경고/주의사항/부작용/상호작용/보관법) — 후보 이름을 순서대로 시도해
    처음 걸리는 것만 쓴다."""
    precaution_parts: list[str] = []
    side_effects: str | None = None
    interactions: str | None = None
    storage: str | None = None
    try:
        from rag.mfds_client import search_by_name

        for candidate in candidates:
            hits = search_by_name(candidate, num_of_rows=1)
            if hits:
                hit = hits[0]
                if hit.atpn_warn_qesitm:
                    precaution_parts.append(f"[경고] {hit.atpn_warn_qesitm.strip()}")
                if hit.atpn_qesitm:
                    precaution_parts.append(hit.atpn_qesitm.strip())
                side_effects = hit.se_qesitm.strip() if hit.se_qesitm else None
                interactions = hit.intrc_qesitm.strip() if hit.intrc_qesitm else None
                storage = hit.deposit_method_qesitm.strip() if hit.deposit_method_qesitm else None
                break
    except Exception:  # noqa: BLE001 — 키 미설정/네트워크 실패/미등재 약품명 등 어떤 이유로든 조용히 폴백
        pass
    return {
        "precaution_parts": precaution_parts,
        "side_effects": side_effects,
        "interactions": interactions,
        "storage": storage,
    }


def _fetch_dur_cautions(candidates: list[str]) -> list[dict]:
    """DUR 노인주의/연령금기/임부금기 — 카테고리별로 후보 이름을 순서대로 시도해
    처음 걸리는 것만 쓴다."""
    dur_cautions: list[dict] = []
    try:
        from rag.dur_master import search_age_taboo, search_elderly_caution, search_pregnancy_taboo

        raw_cautions: list = []
        for search_fn in (search_elderly_caution, search_age_taboo, search_pregnancy_taboo):
            for candidate in candidates:
                found = search_fn(candidate, num_of_rows=20)
                if found:
                    raw_cautions.extend(found)
                    break
        dur_cautions = [
            {"category": c.category, "detail": c.detail, "extra": c.extra} for c in raw_cautions
        ]
    except Exception:  # noqa: BLE001
        pass
    return dur_cautions


def _fetch_rag_drug_detail(drug_name: str) -> dict:
    """e약은요(주의사항/부작용/상호작용/보관법)와 DUR(노인주의/연령금기/임부금기)을
    live API로 보강 조회한다. chat_router.py의 온디맨드 DUR 조회와 동일한 패턴 —
    특정 PROVIDER 플래그와 무관하게 항상 시도하고, 조회어가 안 걸리거나
    DATA_GO_KR_SERVICE_KEY 미설정·네트워크 실패 등 어떤 이유로든 실패해도 이 엔드포인트
    전체가 500이 되지 않도록 각 호출을 개별로 조용히 폴백시킨다.

    병용금기(search_usjnt_taboo)는 "약 하나"가 아니라 "약 A + 약 B" 관계 정보라 이
    단일 약품 조회와 성격이 달라 여기서는 제외했다(처방전 전체 컨텍스트가 있는
    chat_router.py의 DUR 보강조회 쪽 몫으로 남겨둠).

    [2026-07-25 추가] 아래 허가정보/e약은요/DUR 3개 조회는 서로 독립적인데 예전엔
    순서대로 실행돼서 외부 공공 API 왕복 시간이 그대로 더해지고 있었다("로딩이
    생각보다 길다" 피드백) — 스레드로 동시에 실행해서 전체 소요 시간을 셋 중 가장
    느린 것 수준으로 줄인다. 결과 순서(허가정보 → e약은요)는 기존과 동일하게 유지.
    """
    # [2026-07-20 추가] "노바스크정5mg"처럼 e약은요 등록명과 글자 단위로 다른 이름이 들어와도
    # 조회가 걸리도록 후보 이름을 순서대로 시도한다(rag_chain.py의 resolve_drug_name_candidates
    # 재사용 — DUR/RAG 가이드 생성과 동일한 폴백 체인, 중복 구현 금지).
    try:
        from rag.rag_chain import resolve_drug_name_candidates

        candidates = resolve_drug_name_candidates(drug_name)
    except Exception:  # noqa: BLE001 — 후보 생성 실패 시 원문 하나만으로 폴백
        candidates = [drug_name]

    with ThreadPoolExecutor(max_workers=3) as executor:
        permit_future = executor.submit(_fetch_permit_precautions, candidates)
        eyakeun_future = executor.submit(_fetch_eyakeun_info, candidates)
        dur_future = executor.submit(_fetch_dur_cautions, candidates)

        permit_precaution_parts = permit_future.result()
        eyakeun = eyakeun_future.result()
        dur_cautions = dur_future.result()

    precautions = "\n\n".join(permit_precaution_parts + eyakeun["precaution_parts"]) or None

    return {
        "precautions": precautions,
        "side_effects": eyakeun["side_effects"],
        "interactions": eyakeun["interactions"],
        "storage": eyakeun["storage"],
        "dur_cautions": dur_cautions,
    }


# [2026-07-20 추가] 허가사항/e약은요 원문(_fetch_rag_drug_detail)은 의료 전문 용어가 많고
# 길어서 고령 환자가 그대로 읽기 어렵다 — chat_router.py/rag_chain.py와 동일하게
# ChatOpenAI + JSON 모드로 환자용 쉬운 말 요약을 만든다. 원문은 그대로 유지하고(내부/폴백용),
# 화면에는 이 요약을 우선 노출한다.
_PATIENT_SUMMARY_SYSTEM_PROMPT = """\
당신은 고령 만성질환 환자를 위한 복약 안내문 작성자입니다. [원문]은 식약처 허가사항·
e약은요의 사용상의 주의사항/경고/부작용/상호작용 원문입니다. 환자가 이해하기 쉬운 말로
바꿔 아래 3개 항목으로 나눠 정리하세요.

규칙:
- 어려운 의학 용어는 쉬운 말로 풀어씁니다.
- 원문에 없는 위험을 새로 만들어내지 않습니다 — 원문에 없으면 그 항목은 빈 배열로 둡니다.
- 환자가 바로 행동할 수 있게 씁니다(예: "이런 증상이 있으면 복용을 멈추고 병원에 가세요").
- 너무 겁주지 말고, 필요하면 의사·약사 상담을 안내합니다.
- 각 항목은 짧은 문장 1개로, 배열 하나당 최대 4개까지만 담습니다.
- 반드시 아래 JSON 형식으로만 답하세요:
  {"must_check": ["..."], "tell_doctor": ["..."], "avoid_together": ["..."]}
- must_check: 복용 중 이런 증상이 있으면 즉시 병원·약사에게 연락해야 하는 것(알레르기 반응,
  응급 증상 등)
- tell_doctor: 복용 전 의사·약사에게 미리 알려야 하는 본인 상태(간·신장 질환, 임신 등)
- avoid_together: 이 약과 함께 피해야 하는 것(음식·음주·다른 약 등)
"""


def _summarize_precautions_for_patient(
    drug_name: str, precautions: str | None, side_effects: str | None, interactions: str | None
) -> dict | None:
    """원문 3종을 환자용 3분류(꼭 확인/의사·약사에게 알려주세요/함께 피할 것)로 요약한다.
    LLM 실패/키 미설정/원문 자체가 없음 등 어떤 이유로든 실패하면 None — 호출부가 기존
    원문 카드로 폴백한다(chat_router.py의 LLM 실패 시 폴백과 동일한 원칙)."""
    if not precautions and not side_effects and not interactions:
        return None

    try:
        from langchain_openai import ChatOpenAI
        from rag.config import settings as rag_settings

        if not rag_settings.OPENAI_API_KEY:
            return None

        raw_text = "\n\n".join(
            part
            for part in [
                f"[사용상의 주의사항/경고]\n{precautions}" if precautions else None,
                f"[부작용]\n{side_effects}" if side_effects else None,
                f"[상호작용]\n{interactions}" if interactions else None,
            ]
            if part
        )
        chat = ChatOpenAI(
            model=rag_settings.OPENAI_MODEL,
            api_key=rag_settings.OPENAI_API_KEY,
            temperature=0.3,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        response = chat.invoke(
            [
                {"role": "system", "content": _PATIENT_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"약품명: {drug_name}\n\n[원문]\n{raw_text}"},
            ]
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        data = json.loads(content)
        return {
            "must_check": [str(x) for x in (data.get("must_check") or [])][:4],
            "tell_doctor": [str(x) for x in (data.get("tell_doctor") or [])][:4],
            "avoid_together": [str(x) for x in (data.get("avoid_together") or [])][:4],
        }
    except Exception:  # noqa: BLE001 — LLM 실패/키 미설정/JSON 파싱 실패 등 어떤 이유로든 원문 폴백
        return None


@router.get("/drug-info")
def drug_info(drug_name: str):
    """
    [7/8] 약물상세 화면(DrugInfo.tsx/DrugDetail.tsx)의 "약효분류·적응증" 표시용 —
    OCR 세션과 무관하게 약품명만으로 다시 조회하는 stateless 조회입니다.
    get_drug_info()이 HIRA/e약은요/ATC/폴백 순으로 조회하는 로직을 재사용합니다.

    [2026-07-20 추가] DrugDetail.tsx(복약 일정 기반, OCR 기록과 연결 안 됨)가 주의사항
    등을 표시할 방법이 아예 없었던 문제 — rag/ 패키지 live API로 보강 조회한 필드들을
    함께 내려준다(_fetch_rag_drug_detail 참고).
    """
    result = get_drug_info(drug_name)
    efficacy = result["efficacy"]
    # [2026-07-19 PR #52 기준 정렬] matched_name(PrescriptionReview.tsx가 "이 약품명이
    # 실제로 맞는지" 판단하는 값)은 get_drug_info()의 matched_item이 아니라 match_drug()의
    # 유사도 점수로 판정한다 — PR #52에서 이미 이렇게 바뀐 걸 그대로 따른다. get_drug_info()의
    # atc_pattern/fallback 단계는 "이름에 특정 키워드가 포함되는가"만 보는 부분일치라
    # "졸피뎀아무말"처럼 실제 이름 뒤에 엉뚱한 말을 붙여도 통과해버리는데, match_drug()은
    # (용량 표기를 정규화한 뒤) 전체 문자열 유사도를 보므로 이런 입력을 실제로 걸러낸다
    # (run_ocr()이 review_required를 정할 때 쓰는 것과 동일한 기준, MATCH_THRESHOLD).
    #
    # PR #52 이전엔 matched_item이 "hira_name 등에서 찾은 다른(더 정확한) 이름"일 수 있어서
    # rag 조회어를 matched_item으로 바꿔치기했지만, 이 기준으로는 matched_name이 항상
    # drug_name 그 자체(검증 통과) 또는 None(검증 실패)이라 그런 대체가 의미 없어졌다 —
    # rag/DUR 조회는 검증 결과와 무관하게 원본 drug_name으로 그대로 시도한다(실패해도
    # _fetch_rag_drug_detail이 이미 null/빈 값으로 조용히 폴백).
    _, score = match_drug(drug_name)
    matched_name = drug_name if score >= MATCH_THRESHOLD else None
    rag_detail = _fetch_rag_drug_detail(drug_name)
    patient_summary = _summarize_precautions_for_patient(
        drug_name, rag_detail["precautions"], rag_detail["side_effects"], rag_detail["interactions"]
    )
    return {
        "drug_name": drug_name,
        "matched_name": matched_name,
        "drug_class": result["drug_class"],
        "indication": efficacy.strip() if efficacy else efficacy,
        **rag_detail,
        "patient_summary": patient_summary,
    }


async def run_ocr(patient_id: int, file: UploadFile, session: Session) -> MedicalRecord:
    """
    처방전 이미지를 CLOVA OCR로 인식하고 DB에 저장하는 실제 로직.
    records_router.py(POST /records)와 아래 /ocr/test 양쪽에서 호출됩니다.

    - patient_id: 이 처방전의 환자 id
    - 인식된 약품마다 ocr_results 행이 1개씩 생성됩니다.
    - review_required는 처방전 전체 단위 판정(overall_confidence < 0.80)이며,
      그 값이 모든 OcrResult 행에 동일하게 기록됩니다.

    검증 실패(400)나 CLOVA 통신 오류(502/503/504)는 HTTPException으로 던져지고,
    호출부(records_router.py)에서 그대로 전파되어 프론트가 실패로 인식합니다.
    """
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="파일을 다시 선택해주시겠어요?")
    _, ext = os.path.splitext(filename)
    if ext.lower() not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail="JPG, PNG 형식의 사진 파일만 올릴 수 있어요. "
                   "다른 형식의 파일이라면 사진으로 변환한 뒤 다시 올려주시겠어요?",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="사진 파일이 비어있어요. 다시 찍어서 올려주시겠어요?")

    # [2026-07-25 추가] 원본 사진을 record별로 저장 — 파일명은 patient_id/원본 파일명이
    # 그대로 노출되지 않도록 uuid로 새로 만든다(개인정보가 파일 경로에 남지 않게).
    stored_name = f"{uuid.uuid4().hex}{ext.lower()}"

    def _save_image() -> None:
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (_UPLOAD_DIR / stored_name).write_bytes(content)

    await asyncio.to_thread(_save_image)

    record = MedicalRecord(
        patient_id=patient_id,
        image_path=f"uploads/prescriptions/{stored_name}",
        status="processing",
    )

    # session.add/commit/refresh는 동기 SQLModel 호출이라, async def 안에서 그대로 부르면
    # 이벤트 루프를 막는다 — 아래 CLOVA 호출(asyncio.to_thread로 이미 감싸져 있음)과 같은
    # 이유로 이 함수의 모든 DB 접근도 스레드에서 실행한다.
    def _persist(rec: MedicalRecord) -> None:
        session.add(rec)
        session.commit()

    def _persist_and_refresh(rec: MedicalRecord) -> None:
        session.add(rec)
        session.commit()
        session.refresh(rec)

    await asyncio.to_thread(_persist_and_refresh, record)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext.lower()) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        provider_kind = os.environ.get("OCR_PROVIDER", "clova")
        provider = get_ocr_provider(provider_kind)
        ocr_result = await asyncio.to_thread(provider.extract, tmp_path)

    except requests.exceptions.Timeout as exc:
        record.status = "failed"
        record.failure_reason = "CLOVA API 타임아웃"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=504,
            detail="처방전 인식에 시간이 너무 걸렸어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        record.status = "failed"
        record.failure_reason = "CLOVA API 연결 실패"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=503,
            detail="인터넷 연결을 확인하고 다시 시도해주시겠어요?",
        ) from exc
    except requests.exceptions.HTTPError as exc:
        http_status = exc.response.status_code if exc.response is not None else "?"
        record.status = "failed"
        record.failure_reason = f"CLOVA API HTTP {http_status} 오류"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=502,
            detail="처방전 인식 서비스에 일시적인 문제가 생겼어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    except RuntimeError as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=503,
            detail="처방전 인식 서비스를 현재 사용할 수 없어요. 관리자에게 문의해주세요.",
        ) from exc
    except Exception as exc:
        record.status = "failed"
        record.failure_reason = str(exc)
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=500,
            detail="처방전을 처리하는 중에 문제가 생겼어요. 잠시 후 다시 시도해주시겠어요?",
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    record.raw_text = ocr_result.raw_text
    record.prescription_date = extract_prescription_date(ocr_result.raw_text) or None
    record.status = "review_required" if ocr_result.review_required else "completed"
    session.add(record)

    if not ocr_result.medications:
        record.status = "review_required"
        await asyncio.to_thread(_persist, record)
        raise HTTPException(
            status_code=422,
            detail="처방전에서 약품 정보를 찾지 못했어요. 처방전이 잘 보이도록 다시 찍어서 올려주시겠어요?",
        )

    def _save_ocr_results() -> None:
        for med in ocr_result.medications:
            matched_name, score = match_drug(med.drug_name)
            row = OcrResult(
                record_id=record.id,
                drug_name=med.drug_name,
                drug_code=med.drug_code,
                dosage=med.dosage,
                dose_amount=med.dose_amount,
                frequency=med.frequency,
                diagnosis=med.diagnosis,
                drug_class=med.drug_class,
                total_days=med.total_days,
                confidence=med.confidence,
                review_required=ocr_result.review_required,
                matched_drug_name=matched_name,
                match_score=score,
                needs_review=score < MATCH_THRESHOLD,
            )
            session.add(row)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_save_ocr_results)
    return record


@router.post("/test")
async def test_ocr_upload(
    patient_id: int,
    file: UploadFile = File(...),
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """OCR만 따로 테스트하고 싶을 때 쓰는 엔드포인트 (실제 흐름은 POST /records 사용)"""
    # require_actor_patient_access/session.exec 둘 다 동기 SQLModel 호출이라 스레드에서 실행.
    await asyncio.to_thread(require_actor_patient_access, patient_id, actor, session)
    record = await run_ocr(patient_id, file, session)
    medications = await asyncio.to_thread(
        lambda: [
            {
                "drug_name": m.drug_name,
                "dosage": m.dosage,
                "dose_amount": m.dose_amount,
                "frequency": m.frequency,
                "diagnosis": m.diagnosis,
                "drug_class": m.drug_class,
                "confidence": m.confidence,
                "review_required": m.review_required,
            }
            for m in session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
        ]
    )
    return {
        "record_id": record.id,
        "status": record.status,
        "medications": medications,
    }
