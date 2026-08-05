"""
records_router.py — 담당: 박소정 (전체 흐름 연결)

schedule_v6의 "동기 방식" 원칙 그대로: 폴링도 스트리밍도 없이,
처방전 업로드 요청 하나로 OCR → RAG까지 다 처리해서 결과를 한 번에 돌려줍니다.

프론트 흐름:
1) Upload.tsx — 파일 선택만 하고 /processing으로 이동 (아직 요청 안 보냄)
2) Processing.tsx — 마운트되자마자 이 POST /records를 호출하고 기다림 (몇 초 걸릴 수 있음)
   기다리는 동안 기존 3단계 애니메이션을 그냥 시각 효과로 보여줌
3) 응답이 오면 그 데이터를 그대로 들고 /result로 이동 (재조회 없음)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from core.push import send_push_to_recipient
from core.schedule_alerts import caregiver_wants_notifications
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from models import (
    Caregiver,
    CaregiverPatient,
    GuideResult,
    MedicalRecord,
    MedicalRecordImage,
    MedicationFieldFlag,
    MedicationSchedule,
    OcrResult,
    Patient,
    PatientMedication,
    RecordCorrectionNotice,
)
from pydantic import BaseModel
from services.drug_matcher import MATCH_THRESHOLD, match_drug
from services.ocr_quality import requires_drug_name_review
from sqlmodel import Session, select

from routers.ocr_router import drug_info, run_ocr
from routers.rag_router import run_rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/records", tags=["Records"])

# [2026-08-05 추가, perf] 처방전 확인 화면(PrescriptionReview.tsx)이 약마다 GET
# /ocr/drug-info를 순서대로 부르면 그만큼 API 부하가 커진다 — 백그라운드 사전조회도
# 동시에 몰리는 요청 수를 여기서 제한한다(정부 공공데이터포털 API/LLM 호출을 무제한
# 동시 실행하지 않도록).
_DRUG_INFO_PREFETCH_MAX_WORKERS = 4


def _prefetch_drug_info(record_id: int, drug_names: list[str]) -> None:
    """[2026-08-05 추가, perf] POST /records 응답을 받고 사용자가 확인 화면
    (PrescriptionReview.tsx)을 거치는 동안(보통 몇 초~수십 초) 이 처방전의 약들에 대해
    GET /ocr/drug-info와 동일한 조회(drug_info())를 미리 실행해 diskcache를 채워둔다.
    사용자가 실제로 확인 화면에서 조회할 때는 캐시 히트라 콜드 상태의 지연(주의사항
    LLM 요약 등)을 체감하지 않는다.

    BackgroundTasks로 등록돼 POST /records 응답이 이미 클라이언트로 전송된 뒤 실행되므로,
    여기서 나는 어떤 예외도 그 응답에는 영향을 줄 수 없다 — 그래도 한 약의 실패가 나머지
    약 조회를 막지 않도록 개별 try/except로 감싼다.
    """
    logger.info(
        "약물 상세정보 백그라운드 사전조회 시작: record_id=%s, drug_count=%d, drug_names=%s",
        record_id, len(drug_names), drug_names,
    )
    with ThreadPoolExecutor(max_workers=_DRUG_INFO_PREFETCH_MAX_WORKERS) as executor:
        futures = {executor.submit(drug_info, name): name for name in drug_names}
        for future in futures:
            name = futures[future]
            try:
                future.result()
            except Exception:  # noqa: BLE001 — 사전조회 실패는 사용자 화면에 영향 없어야 함(로그만 남김)
                logger.warning(
                    "약물 상세정보 백그라운드 사전조회 실패: record_id=%s, drug_name=%s",
                    record_id, name, exc_info=True,
                )
    logger.info(
        "약물 상세정보 백그라운드 사전조회 완료: record_id=%s, drug_count=%d, drug_names=%s",
        record_id, len(drug_names), drug_names,
    )

# [2026-07-25 추가] ocr_router.py가 저장한 처방전 원본 사진(image_path, backend 루트
# 기준 상대경로)을 절대경로로 풀 때 쓴다.
_ROOT = Path(__file__).parent.parent

# [7/9 추가] OCR은 "1일 N회"까지만 뽑아내고 몇 시에·식전/식후인지는 파싱하지 않는다
# (parsing_rules.py 참고 — 그 정보 자체가 OcrResult에 없음). 그래서 여기서는 횟수만 보고
# 합리적인 기본 시간대로 복약일정을 만들고, 식전/식후(dose_timing)는 비워서 사용자가
# Schedule.tsx에서 직접 채우게 한다 — 모르는 걸 아는 척 지어내지 않음.
_DEFAULT_TIME_SLOTS = {
    "1일 1회": ["09:00"],
    "1일 2회": ["09:00", "19:00"],
    "1일 3회": ["08:00", "13:00", "19:00"],
    "1일 4회": ["08:00", "12:00", "17:00", "21:00"],
}
# [2026-07-21 추가] 처방확인 화면에서 고른 복용시간(dose_timing)은 환자가 회원가입 직후
# MealTimeCheck.tsx에서 설정한 실제 식사시간(Patient.breakfast_time 등, monitoring_router.py의
# PUT /patients/{id}/meal-times)을 기준으로 시각을 계산한다 — 모두에게 같은 "08:00"을
# 박아넣는 대신, 이 환자가 실제로 아침을 언제 먹는지에 맞춘다. (식전/식후) 30분,
# 공복은 아침식사 1시간 전 — 의학적으로 엄밀한 기준이 아니라 합리적인 기본값이며,
# 실제 시각은 Schedule.tsx에서 언제든 직접 수정할 수 있다.
_MEAL_OFFSET_MINUTES: dict[str, tuple[str, int]] = {
    "공복": ("breakfast", -60),
    "아침 식후": ("breakfast", 30),
    "점심 식전": ("lunch", -30),
    "점심 식후": ("lunch", 30),
    "저녁 식전": ("dinner", -30),
    "저녁 식후": ("dinner", 30),
}
# 환자가 식사시간 설문을 건너뛴 경우(필드가 None)의 폴백 — 기존 _DEFAULT_TIME_SLOTS의
# "1일 3회" 기본값과 동일하게 맞춰 일관성을 유지한다.
_MEAL_TIME_FALLBACK = {"breakfast": "08:00", "lunch": "13:00", "dinner": "19:00"}
# [2026-07-21 추가] PrescriptionReview.tsx의 "직접 시간 설정"/"몇 시간마다 반복"은 식사시간
# 라벨이 아니라 실제 "HH:MM" 문자열을 dose_timings 배열에 그대로 담아 보낸다 — 이 형식이면
# 식사시간 계산 없이 그 시각 그대로 쓴다.
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _resolve_time_slot(dose_timing: str, patient: Patient | None) -> str:
    if _TIME_RE.match(dose_timing):
        return dose_timing
    meal, offset = _MEAL_OFFSET_MINUTES.get(dose_timing, (None, 0))
    if meal is None:
        return _MEAL_TIME_FALLBACK["breakfast"]  # DOSE_TIMINGS 6종 외 값은 들어올 일이 없지만 방어적으로
    base = getattr(patient, f"{meal}_time", None) if patient else None
    base = base or _MEAL_TIME_FALLBACK[meal]
    hour, minute = (int(x) for x in base.split(":", 1))
    total = (hour * 60 + minute + offset) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _create_schedules_from_ocr(
    record: MedicalRecord,
    ocr_items: Sequence[OcrResult],
    session: Session,
    dose_timings_by_id: dict[int, list[str]] | None = None,
) -> list[str]:
    """[2026-07-23 수정] 이 환자에게 같은 약 이름으로 이미 활성 일정이 있어도, 이번
    처방전과 그 일정의 조제일자가 다르면(재처방) 중복이 아니다 — 기존 일정은
    비활성화하고 새로 만든다. 날짜가 같거나(재확인 등) 둘 중 하나라도 날짜를 모르면
    (구형 데이터, 수동입력, 날짜 파싱 실패 등) 비교할 근거가 없으니 기존처럼 이름만으로
    중복 판정한다. 반환값(중복으로 건너뛴 약 이름 목록)을 confirm_medications가 응답에
    실어 "이미 등록된 처방이에요"를 화면에 보여줄 수 있게 한다."""
    dose_timings_by_id = dose_timings_by_id or {}
    patient = session.get(Patient, record.patient_id)
    duplicate_drug_names: list[str] = []
    for item in ocr_items:
        if not item.drug_name:
            continue
        drug_name = item.display_name
        existing_active = session.exec(
            select(MedicationSchedule)
            .where(MedicationSchedule.patient_id == record.patient_id)
            .where(MedicationSchedule.drug_name == drug_name)
            .where(MedicationSchedule.active == True)  # noqa: E712
        ).all()

        superseded: list[MedicationSchedule] = []
        is_duplicate = False
        for sched in existing_active:
            other_record = session.get(MedicalRecord, sched.record_id) if sched.record_id else None
            other_date = other_record.prescription_date if other_record else None
            if not record.prescription_date or not other_date or other_date == record.prescription_date:
                is_duplicate = True
                break
            superseded.append(sched)

        if is_duplicate:
            duplicate_drug_names.append(drug_name)
            continue

        for sched in superseded:
            sched.active = False
            session.add(sched)

        timings = dose_timings_by_id.get(item.id) or []
        slots = [_resolve_time_slot(t, patient) for t in timings] if timings else None
        slots = slots or _DEFAULT_TIME_SLOTS.get(item.frequency, ["09:00"])
        for i, slot in enumerate(slots):
            session.add(
                MedicationSchedule(
                    patient_id=record.patient_id,
                    # [2026-07-20 버그수정] 예전엔 item.drug_name(축약명, 예: "암로디핀")을
                    # 그대로 썼다 — Dashboard.tsx/Schedule.tsx가 이 값을 표시하므로 환자가
                    # 매일 보는 화면에 짧은 이름이 노출되고 있었다. _build_record_response와
                    # 동일한 규칙(item.display_name)으로 통일.
                    drug_name=drug_name,
                    time_slot=slot,
                    dose_timing=timings[i] if i < len(timings) else None,
                    memo=(
                        "처방전확인 화면에서 복용시간을 설정했어요"
                        if timings
                        else "처방전에서 자동 등록됨 — 시간·식전후 여부는 확인 후 수정해주세요"
                    ),
                    # [2026-07-20 추가] 이 처방전을 나중에 삭제할 때 같이 비활성화할 수 있도록 연결.
                    record_id=record.id,
                )
            )
    session.commit()
    return duplicate_drug_names


# [2026-07-25 추가] 처방전이 완료(guide 생성)될 때 보호자 검토 대상인지 정하고, 대상이면
# 연결된 보호자·기관 전원에게 "새 처방전이 등록됐어요" 알림을 남긴다(알림함 + 나중에
# 프론트가 Web Push 구독을 붙이면 그쪽으로도 — 지금은 구독이 없으면 send_push_to_recipient가
# 조용히 건너뛴다). 연결된 보호자·기관이 하나도 없으면 검토할 사람이 없으니 대상에서 뺀다("none").
def _initial_caregiver_review_status(record: MedicalRecord, session: Session) -> str:
    caregiver_ids = session.exec(
        select(CaregiverPatient.caregiver_id)
        .where(CaregiverPatient.patient_id == record.patient_id)
        .where(CaregiverPatient.status != "revoked")
    ).all()
    if not caregiver_ids:
        return "none"
    for caregiver_id in caregiver_ids:
        session.add(
            RecordCorrectionNotice(
                recipient_role="caregiver",
                recipient_id=caregiver_id,
                record_id=record.id,
                event="review_pending",
            )
        )
        # [2026-07-30 추가] 알림함 알림(위)은 그대로 남기고, "이 기기로" 받는 푸시만
        # (이 보호자, 이 환자) 관계 단위로 꺼져있으면 건너뛴다.
        if caregiver_wants_notifications(caregiver_id, record.patient_id, session):
            send_push_to_recipient(
                session, "caregiver", caregiver_id,
                title="새 처방전이 등록됐어요", body="검토가 필요한 처방전이 있어요.",
                url=f"/records/{record.id}/guide",
            )
    return "pending"


def _build_record_response(
    record: MedicalRecord,
    session: Session,
    guide: GuideResult | None,
    duplicate_drug_names: list[str] | None = None,
) -> dict:
    ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
    uploader = (
        session.get(Caregiver, record.uploaded_by_caregiver_id)
        if record.uploaded_by_caregiver_id
        else None
    )
    # [2026-07-25 추가] 보호자·기관이 수정 요청한 칸 — item.id별로 묶어서 내려준다.
    # PrescriptionReview.tsx가 correction 모드일 때 이 목록으로 잠금/빨간테두리를 그린다.
    flags_by_item: dict[int, list[MedicationFieldFlag]] = {}
    if ocr_items:
        item_ids = [item.id for item in ocr_items]
        flags = session.exec(
            select(MedicationFieldFlag).where(MedicationFieldFlag.ocr_result_id.in_(item_ids))
        ).all()
        for flag in flags:
            flags_by_item.setdefault(flag.ocr_result_id, []).append(flag)
    return {
        "record_id": record.id,
        "status": record.status,
        "failure_reason": record.failure_reason,
        "created_at": record.created_at.isoformat(),
        "uploaded_by_name": uploader.name if uploader else None,
        "caregiver_review_status": record.caregiver_review_status,
        # [2026-07-25 추가] 원본 사진 보기 버튼을 보여줄지 — 수동 입력이거나 이 기능
        # 이전에 등록된 처방전은 사진이 없다.
        "has_image": bool(record.image_path == "database" or (record.image_path and record.image_path.startswith("uploads/prescriptions/"))),
        "medications": [
            {
                "id": item.id,  # [7/8 추가] 처방전확인 화면에서 항목별 수정 시 식별용
                # [2026-07-20] item.display_name — 확신 있게 매칭됐을 때(needs_review=False)만
                # matched_drug_name(전체 제품명)을 대표 표시값으로 쓴다(models.py 참고).
                "drug_name": item.display_name,
                "drug_code": item.drug_code,
                "dosage": item.dosage,
                "dose_amount": item.dose_amount,
                "frequency": item.frequency,
                "total_days": item.total_days,
                "diagnosis": item.diagnosis,
                "drug_class": item.drug_class,
                "confidence": item.confidence,
                "review_required": item.review_required,
                "field_flags": [
                    {
                        "id": flag.id,
                        "field_name": flag.field_name,
                        "reason": flag.reason,
                        "suggested_value": flag.suggested_value,
                        "corrected": flag.corrected,
                    }
                    for flag in flags_by_item.get(item.id, [])
                ],
            }
            for item in ocr_items
        ],
        "guide": (
            {
                "medication_guide": json.loads(guide.medication_guide),
                "lifestyle_guide": json.loads(guide.lifestyle_guide),
                "source_refs": json.loads(guide.source_refs),
            }
            if guide
            else None
        ),
        # [2026-07-23 추가] confirm_medications가 중복(이미 활성 일정이 있는 약)을 건너뛴
        # 경우에만 채워진다 — PrescriptionReview.tsx가 "이미 등록된 처방이에요"를 보여줄 때 씀.
        "duplicate_drug_names": duplicate_drug_names or [],
    }


@router.post("")
async def create_record(
    patient_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    caregiver_id: int | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    처방전 이미지를 받아서 OCR까지 끝내고 결과를 반환합니다.

    [7/9 변경] OCR 신뢰도와 상관없이 항상 review_required 상태로 반환합니다 — 가이드(RAG)
    생성은 더 이상 여기서 하지 않고, 사용자가 PrescriptionReview.tsx에서 내용을 확인/수정하고
    POST /{record_id}/confirm을 호출할 때만 트리거됩니다. run_ocr()이 신뢰도에 따라 정한
    status는 참고용으로 남겨두지 않고 덮어씁니다 — "확인 화면을 항상 거친다"는 게 지금
    유일한 진입 규칙이라, 두 상태를 따로 유지하면 나중에 헷갈리기만 합니다.

    [7/9 추가] caregiver_id를 넘기면 "보호자가 대신 업로드"로 기록됩니다(생략하면 본인 업로드).

    [7/8] 권순현님 PR #9 실제 CLOVA 로직 통합 완료 — run_ocr()가 이제 진짜 CLOVA를 호출합니다.

    ⚠️ CLOVA_OCR_API_URL/SECRET_KEY가 .env에 없으면 503으로 실패합니다(의도된 동작).
       키 없이 파이프라인만 테스트하려면 .env에 OCR_PROVIDER=mock 추가하세요.
    """
    # require_actor_patient_access/session.get 등은 동기 SQLModel 호출이라, async def
    # 안에서 그대로 부르면 이벤트 루프를 막는다 — run_ocr 내부(asyncio.to_thread로 이미
    # 감싸져 있음)와 동일한 이유로 이 함수의 DB 접근도 전부 스레드에서 실행한다.
    def _check_access() -> None:
        require_actor_patient_access(patient_id, actor, session)
        if caregiver_id is not None and not session.get(Caregiver, caregiver_id):
            raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    await asyncio.to_thread(_check_access)

    record = await run_ocr(patient_id, file, session)

    if caregiver_id is not None:
        def _mark_uploader() -> None:
            record.uploaded_by_caregiver_id = caregiver_id
            session.add(record)
            session.commit()
            session.refresh(record)

        await asyncio.to_thread(_mark_uploader)

    # 신뢰도와 무관하게 항상 확인 화면을 거치게 한다 — RAG는 /confirm에서만 호출된다.
    def _finalize_status() -> None:
        record.status = "review_required"
        session.add(record)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_finalize_status)
    response = await asyncio.to_thread(_build_record_response, record, session, None)

    # [2026-08-05 추가, perf] 확인 화면(PrescriptionReview.tsx)에서 약마다 GET
    # /ocr/drug-info를 부르기 전에, 응답을 돌려준 뒤 백그라운드에서 미리 조회해 캐시를
    # 채워둔다 — BackgroundTasks는 응답이 클라이언트로 전송된 뒤 실행되므로 이 응답
    # 자체에는 영향이 없다.
    drug_names = list(
        dict.fromkeys(name for m in response["medications"] if (name := m["drug_name"]))
    )
    if drug_names:
        background_tasks.add_task(_prefetch_drug_info, record.id, drug_names)

    return response


@router.post("/manual")
def create_manual_record(
    patient_id: int,
    caregiver_id: int | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전 인식 실패(OcrError.tsx) 화면의 "직접 입력하기" — OCR을 거치지 않고
    빈 항목 1개짜리 review_required 기록을 만들어서 PrescriptionReview.tsx에서 그대로
    입력·수정하게 합니다. 이후 흐름(확인 완료 → RAG 가이드 생성)은 기존 확인 화면과 동일합니다.
    """
    require_actor_patient_access(patient_id, actor, session)
    if caregiver_id is not None and not session.get(Caregiver, caregiver_id):
        raise HTTPException(404, "해당 보호자를 찾을 수 없어요")

    record = MedicalRecord(
        patient_id=patient_id,
        image_path="manual_entry",
        status="review_required",
        uploaded_by_caregiver_id=caregiver_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    session.add(OcrResult(record_id=record.id, drug_name="", confidence=0.0, review_required=True))
    session.commit()

    return _build_record_response(record, session, None)


@router.post("/{record_id}/medications")
def add_medication_item(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전확인 화면의 "약물 추가" — 빈 항목을 하나 더 만들어서, 사용자가
    처방전에 있지만 인식되지 않은 약을 직접 추가할 수 있게 합니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    session.add(OcrResult(record_id=record_id, drug_name="", confidence=0.0, review_required=True))
    session.commit()

    return _build_record_response(record, session, None)


@router.delete("/{record_id}/medications/{medication_id}")
def remove_medication_item(
    record_id: int,
    medication_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/9 추가] 처방전확인 화면 — "약물 추가"로 잘못 추가했거나 필요 없는 항목을 지우는 용도.
    최소 1개는 남아 있어야 해서(약이 0개인 처방전은 의미가 없음) 마지막 항목은 못 지웁니다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    item = session.get(OcrResult, medication_id)
    if not item or item.record_id != record_id:
        raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")

    remaining = session.exec(select(OcrResult).where(OcrResult.record_id == record_id)).all()
    if len(remaining) <= 1:
        raise HTTPException(409, "처방전에는 최소 1개의 약물 항목이 있어야 해요")

    session.delete(item)
    session.commit()

    return _build_record_response(record, session, None)


class MedicationPatch(BaseModel):
    drug_name: str
    dosage: str = ""
    frequency: str = ""
    total_days: str = ""
    diagnosis: str = ""
    drug_class: str = ""


class MedicationPatchResult(BaseModel):
    id: int
    drug_name: str
    dosage: str
    frequency: str
    total_days: str
    diagnosis: str
    drug_class: str
    matched_drug_name: str
    match_score: float
    needs_review: bool
    typo_suggestion: str | None = None


@router.patch("/{record_id}/medications/{medication_id}", response_model=MedicationPatchResult)
def patch_medication_item(
    record_id: int,
    medication_id: int,
    payload: MedicationPatch,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    처방전확인 화면 — 단건 약물 항목 수정 + REQ-047 오타 제안.

    drug_name을 약물명 사전과 대조해, 사전에 정확히 없으면 가장 유사한 후보를
    typo_suggestion으로 응답에 포함한다. typo_suggestion은 저장하지 않는다.
    완전 일치 조건은 matched_name == drug_name (raw 문자열 exact match).
    """
    record = session.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)
    if record.status != "review_required":
        raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")

    item = session.get(OcrResult, medication_id)
    if not item or item.record_id != record_id:
        raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")

    item.drug_name = payload.drug_name
    item.dosage = payload.dosage
    item.frequency = payload.frequency
    item.total_days = payload.total_days
    item.diagnosis = payload.diagnosis
    item.drug_class = payload.drug_class

    matched_name, score = match_drug(payload.drug_name)
    item.matched_drug_name = matched_name
    item.match_score = score
    item.needs_review = requires_drug_name_review(payload.drug_name, matched_name, score)

    session.add(item)
    session.commit()
    session.refresh(item)

    typo_suggestion: str | None = None
    if matched_name and matched_name != payload.drug_name and score >= MATCH_THRESHOLD:
        typo_suggestion = matched_name

    return MedicationPatchResult(
        id=item.id,
        drug_name=item.drug_name,
        dosage=item.dosage,
        frequency=item.frequency,
        total_days=item.total_days,
        diagnosis=item.diagnosis,
        drug_class=item.drug_class,
        matched_drug_name=item.matched_drug_name,
        match_score=item.match_score,
        needs_review=item.needs_review,
        typo_suggestion=typo_suggestion,
    )


@router.get("")
def list_records(
    patient_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    환자별 처방전 이력 목록 (RecordsPage '이용 기록' 화면용).
    각 항목은 상세 조회 없이 목록에 필요한 요약 정보만 담습니다.
    """
    require_actor_patient_access(patient_id, actor, session)
    records = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .where(MedicalRecord.deleted_at.is_(None))
        # [2026-07-21 추가] 고정(pinned)한 항목을 맨 위로 — 같은 고정 여부 안에서는 최신순 유지
        .order_by(MedicalRecord.pinned.desc(), MedicalRecord.created_at.desc())  # ty: ignore[unresolved-attribute]
    ).all()
    if not records:
        return []

    # [perf, N+1 수정] 기록마다 OcrResult/Caregiver를 따로 조회하던 걸 /monitoring/today,
    # /monitoring/caregivers/{id}/patients와 동일한 "ID 모아서 bulk-select" 패턴으로
    # 바꿨다. 기록 수와 무관하게 쿼리 수가 고정된다.
    record_ids = [r.id for r in records]
    ocr_items_by_record: dict[int, list[OcrResult]] = {}
    for item in session.exec(select(OcrResult).where(OcrResult.record_id.in_(record_ids))).all():
        ocr_items_by_record.setdefault(item.record_id, []).append(item)

    caregiver_ids = {r.uploaded_by_caregiver_id for r in records if r.uploaded_by_caregiver_id}
    uploader_names_by_id = (
        {c.id: c.name for c in session.exec(select(Caregiver).where(Caregiver.id.in_(caregiver_ids)))}
        if caregiver_ids
        else {}
    )

    summaries = []
    for r in records:
        ocr_items = ocr_items_by_record.get(r.id, [])
        # [버그수정] 예전엔 ocr_items[0].diagnosis만 써서, 약마다 진단명이 다른
        # 처방전(예: 천식약+비염약)은 목록에 첫 번째 약의 진단명만 보이고 나머지가
        # 조용히 사라졌다 — 모든 약의 진단명을 중복 제거해 합쳐서 보여준다.
        diagnoses = []
        for item in ocr_items:
            if item.diagnosis and item.diagnosis not in diagnoses:
                diagnoses.append(item.diagnosis)
        summaries.append(
            {
                "record_id": r.id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "diagnosis": ", ".join(diagnoses),
                "drug_names": [item.drug_name for item in ocr_items],
                "uploaded_by_name": uploader_names_by_id.get(r.uploaded_by_caregiver_id),
                "pinned": r.pinned,
                "caregiver_review_status": r.caregiver_review_status,
                "has_image": bool(r.image_path == "database" or (r.image_path and r.image_path.startswith("uploads/prescriptions/"))),
            }
        )
    return summaries


class PinPayload(BaseModel):
    pinned: bool


@router.patch("/{record_id}/pin")
def pin_record(
    record_id: int,
    payload: PinPayload,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[2026-07-21 추가] 등록내역 목록에서 즐겨찾기처럼 위쪽에 고정/해제."""
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    record.pinned = payload.pinned
    session.add(record)
    session.commit()
    return {"record_id": record_id, "pinned": record.pinned}


@router.delete("/{record_id}")
def delete_record(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [2026-07-16 추가] 등록내역(처방전 기록) 삭제 — 멘토링에서 지적된 "등록내역 삭제 기능
    필요" 항목. OcrResult/GuideResult 등 연결 데이터는 그대로 두고 soft-delete만 하며
    (PatientMedication.deleted_at과 동일한 관례), 목록/상세 조회에서만 제외한다.

    [2026-07-20 추가] 이 처방전에서 자동 생성된 복약 일정(MedicationSchedule.record_id로
    연결됨)도 함께 비활성화한다 — 안 그러면 "삭제한" 처방전의 약이 대시보드/스케줄러
    알림에 계속 남아있게 된다(리뷰에서 발견).

    [2026-07-22 추가] PatientMedication.prescription_id로 연결된 내약 데이터도 함께
    soft-delete한다. 등록내역 화면에서는 사라졌지만 내약/일정 화면에 처방전 기반 약이
    계속 남으면 사용자는 "다음 로그인 때 삭제가 안 됐다"고 느끼게 된다.
    """
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    record.deleted_at = datetime.now()
    session.add(record)

    # DB에 저장된 민감한 처방전 원본은 등록내역 삭제 시 실제로 제거한다.
    stored_image = session.get(MedicalRecordImage, record_id)
    if stored_image is not None:
        session.delete(stored_image)

    schedules = session.exec(
        select(MedicationSchedule).where(MedicationSchedule.record_id == record_id)
    ).all()
    for schedule in schedules:
        schedule.active = False
        session.add(schedule)

    medications = session.exec(
        select(PatientMedication)
        .where(PatientMedication.prescription_id == record_id)
        .where(PatientMedication.deleted_at.is_(None))
    ).all()
    medication_ids = [medication.id for medication in medications if medication.id is not None]
    for medication in medications:
        medication.deleted_at = datetime.now()
        medication.is_active = False
        medication.updated_at = datetime.now()
        session.add(medication)

    if medication_ids:
        linked_schedules = session.exec(
            select(MedicationSchedule).where(MedicationSchedule.patient_medication_id.in_(medication_ids))
        ).all()
        for schedule in linked_schedules:
            schedule.active = False
            session.add(schedule)

    session.commit()
    return {"message": "삭제됐어요"}


class MedicationCorrection(BaseModel):
    id: int  # OcrResult.id
    drug_name: str
    dosage: str
    dose_amount: str = ""
    frequency: str
    total_days: str = ""  # [2026-07-18 추가] 총 투약일수
    diagnosis: str
    drug_class: str
    # [2026-07-21 추가] 처방확인 화면에서 고른 복용시간(공복/아침 식후 등) — 환자의 실제
    # 식사시간(_resolve_time_slot) 기준으로 시간대에 매핑된다. 비어있으면 기존처럼 frequency로 기본 추정.
    dose_timings: list[str] = []


class ConfirmMedicationsPayload(BaseModel):
    medications: list[MedicationCorrection]


@router.post("/{record_id}/confirm")
async def confirm_medications(
    record_id: int,
    payload: ConfirmMedicationsPayload,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """
    [7/8 추가] 처방전확인 화면 — review_required(저신뢰) 처방전의 항목을 보호자가 직접
    수정·확정하면 그 값으로 OCR 결과를 갈아끼우고 바로 RAG 가이드 생성까지 이어서 처리합니다.
    (POST /records 상단 docstring에 있던 "재요청 엔드포인트는 별도 TODO"를 해소)
    """
    # 이 함수의 모든 SQLModel 호출(동기)은 스레드에서 실행한다 — run_ocr/run_rag와
    # 동일한 이유(async def 안에서 동기 DB 호출이 이벤트 루프를 막지 않도록).
    def _load_and_check() -> MedicalRecord:
        rec = session.get(MedicalRecord, record_id)
        if not rec:
            raise HTTPException(404, "해당 기록을 찾을 수 없어요")
        require_actor_patient_access(rec.patient_id, actor, session)
        if rec.status != "review_required":
            raise HTTPException(409, "확인이 필요한 상태의 처방전이 아니에요")
        return rec

    record = await asyncio.to_thread(_load_and_check)

    def _apply_corrections() -> None:
        for correction in payload.medications:
            item = session.get(OcrResult, correction.id)
            if not item or item.record_id != record_id:
                continue
            item.drug_name = correction.drug_name
            item.dosage = correction.dosage
            item.dose_amount = correction.dose_amount
            item.frequency = correction.frequency
            item.total_days = correction.total_days
            item.diagnosis = correction.diagnosis
            item.drug_class = correction.drug_class
            item.review_required = False
            item.user_confirmed = True
            session.add(item)
        session.commit()

    await asyncio.to_thread(_apply_corrections)

    try:
        guide, _from_cache, _cache_expires_at = await run_rag(record.id, session)
    except ValueError as exc:
        _failure_reason = str(exc)  # except 블록 밖에서 e가 삭제되기 전에 캡처

        def _mark_failed() -> None:
            record.status = "failed"
            record.failure_reason = _failure_reason
            session.add(record)
            session.commit()
            session.refresh(record)

        await asyncio.to_thread(_mark_failed)
        return await asyncio.to_thread(_build_record_response, record, session, None)

    def _mark_completed() -> None:
        record.status = "completed"
        record.failure_reason = None
        record.caregiver_review_status = _initial_caregiver_review_status(record, session)
        session.add(record)
        session.commit()
        session.refresh(record)

    await asyncio.to_thread(_mark_completed)

    # [7/9 추가] 확인이 끝난 약을 복약 일정에도 자동으로 등록 — 사용자가 Schedule.tsx에서
    # 매번 손으로 다시 입력하지 않도록.
    def _register_schedules() -> list[str]:
        ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
        dose_timings_by_id = {c.id: c.dose_timings for c in payload.medications if c.dose_timings}
        return _create_schedules_from_ocr(record, ocr_items, session, dose_timings_by_id)

    duplicate_drug_names = await asyncio.to_thread(_register_schedules)

    return await asyncio.to_thread(_build_record_response, record, session, guide, duplicate_drug_names)


# [2026-07-25 추가] get_record()가 재조회할 때 쓰던 "이 record_id의 최신 GuideResult
# 찾기" 로직을 검토 흐름 엔드포인트들도 그대로 써야 해서(응답에 guide를 계속 포함시켜야
# 화면이 안 깨짐) 공용 함수로 뺐다.
def _latest_guide(record: MedicalRecord, session: Session) -> GuideResult | None:
    return session.exec(
        select(GuideResult)
        .where(GuideResult.record_id == record.id)
        .order_by(GuideResult.id.desc())  # ty: ignore[unresolved-attribute]
    ).first()


# [2026-07-25 추가] 처방전확인 화면(PrescriptionReview.tsx)의 7개 칸과 동일한 목록 —
# 보호자가 지목할 수 있는 칸을 여기로 제한해서 임의의 필드가 들어오는 걸 막는다.
_CORRECTABLE_FIELDS = {
    "drug_name", "dosage", "dose_amount", "frequency", "total_days", "diagnosis", "drug_class",
}


class FieldFlagRequest(BaseModel):
    ocr_result_id: int
    field_name: str
    reason: str
    # [2026-07-25 추가] 보호자·기관이 생각하는 정답 — 환자는 이 값을 드롭다운에서
    # 선택만 하지, 자유 입력으로 다른 값을 저장할 수 없다.
    suggested_value: str


class RequestCorrectionPayload(BaseModel):
    flags: list[FieldFlagRequest]


@router.post("/{record_id}/request-correction")
async def request_correction(
    record_id: int,
    payload: RequestCorrectionPayload,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """보호자·기관이 "수정이 필요해요"를 눌러 지목한 칸들을 저장하고 환자에게 알린다."""
    role, _subject = actor
    if role != "caregiver":
        raise HTTPException(403, "보호자·기관만 수정을 요청할 수 있어요")
    if not payload.flags:
        raise HTTPException(422, "수정이 필요한 칸을 1개 이상 골라주세요")

    def _apply() -> MedicalRecord:
        rec = session.get(MedicalRecord, record_id)
        if not rec:
            raise HTTPException(404, "해당 기록을 찾을 수 없어요")
        require_actor_patient_access(rec.patient_id, actor, session)
        if rec.status != "completed":
            raise HTTPException(409, "복약 가이드가 생성된 처방전만 검토할 수 있어요")

        item_ids = {item.id for item in session.exec(
            select(OcrResult).where(OcrResult.record_id == record_id)
        ).all()}
        for flag in payload.flags:
            if flag.ocr_result_id not in item_ids:
                raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")
            if flag.field_name not in _CORRECTABLE_FIELDS:
                raise HTTPException(422, f"수정 요청할 수 없는 항목이에요: {flag.field_name}")
            # [2026-07-25 수정] 이유는 선택 — 정답(suggested_value)만 필수로 남긴다.
            if not flag.suggested_value.strip():
                raise HTTPException(422, "정답(수정할 값)을 입력해주세요")
            session.add(
                MedicationFieldFlag(
                    ocr_result_id=flag.ocr_result_id,
                    field_name=flag.field_name,
                    reason=flag.reason.strip(),
                    suggested_value=flag.suggested_value.strip(),
                )
            )

        rec.caregiver_review_status = "needs_correction"
        session.add(rec)
        session.add(
            RecordCorrectionNotice(
                recipient_role="patient",
                recipient_id=rec.patient_id,
                record_id=rec.id,
                event="correction_requested",
            )
        )
        send_push_to_recipient(
            session, "patient", rec.patient_id,
            title="처방전 수정 요청이 왔어요", body="보호자·기관이 확인해달라는 칸이 있어요.",
            url=f"/records/{rec.id}/review?mode=correction",
        )
        # [2026-07-31 추가] 지금까지는 환자한테만 알림이 갔다 — 같은 환자를 같이 보는 다른
        # 보호자·기관(예: 기관이 요청했는데 보호자는 목록을 직접 열어봐야만 알 수 있던 것)은
        # 상태값(caregiver_review_status)이 바뀐 걸로만 간접적으로 알 수 있었다. 요청을 보낸
        # 사람 본인은 빼고, 같은 환자에 연결된 나머지 caregiver 전원에게도 알린다.
        acting_caregiver_id = actor[1].id
        other_caregiver_ids = session.exec(
            select(CaregiverPatient.caregiver_id)
            .where(CaregiverPatient.patient_id == rec.patient_id)
            .where(CaregiverPatient.status != "revoked")
            .where(CaregiverPatient.caregiver_id != acting_caregiver_id)
        ).all()
        for other_caregiver_id in other_caregiver_ids:
            session.add(
                RecordCorrectionNotice(
                    recipient_role="caregiver",
                    recipient_id=other_caregiver_id,
                    record_id=rec.id,
                    event="correction_requested",
                )
            )
            if caregiver_wants_notifications(other_caregiver_id, rec.patient_id, session):
                send_push_to_recipient(
                    session, "caregiver", other_caregiver_id,
                    title="처방전 수정 요청이 왔어요",
                    body="다른 보호자·기관이 확인해달라는 칸이 있어요.",
                    url=f"/records/{rec.id}/guide",
                )
        session.commit()
        session.refresh(rec)
        return rec

    record = await asyncio.to_thread(_apply)
    return await asyncio.to_thread(_build_record_response, record, session, _latest_guide(record, session))


@router.post("/{record_id}/mark-reviewed")
async def mark_reviewed(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """보호자·기관이 처방전 내용을 최종 확인했다는 표시."""
    role, _subject = actor
    if role != "caregiver":
        raise HTTPException(403, "보호자·기관만 검토를 완료할 수 있어요")

    def _apply() -> MedicalRecord:
        rec = session.get(MedicalRecord, record_id)
        if not rec:
            raise HTTPException(404, "해당 기록을 찾을 수 없어요")
        require_actor_patient_access(rec.patient_id, actor, session)
        # [2026-07-31 추가] 이미 "reviewed"면 그대로 반환 — 아니면 같은 처방전을 여러
        # 보호자/기관이 각자 검토 완료를 누르거나, 중복 클릭·새로고침 후 재호출될 때마다
        # RecordCorrectionNotice(review_completed)가 계속 쌓이고 환자에게 푸시가 매번
        # 다시 나간다(리뷰 지적사항, 실사용에서 반복될 수 있는 케이스).
        if rec.caregiver_review_status == "reviewed":
            return rec
        rec.caregiver_review_status = "reviewed"
        session.add(rec)
        # [2026-07-30 추가] 보호자·기관이 검토를 완료해도 환자한테는 아무 알림이 안 가서,
        # 환자가 자기 처방전이 검토 끝났는지 알 방법이 없었다 — correction_requested/
        # correction_completed와 같은 패턴으로 환자에게 알림+푸시를 남긴다.
        session.add(
            RecordCorrectionNotice(
                recipient_role="patient",
                recipient_id=rec.patient_id,
                record_id=rec.id,
                event="review_completed",
            )
        )
        send_push_to_recipient(
            session, "patient", rec.patient_id,
            title="처방전 검토가 완료됐어요", body="보호자·기관이 처방전 확인을 마쳤어요.",
            url=f"/records/{rec.id}/guide",
        )
        session.commit()
        session.refresh(rec)
        return rec

    record = await asyncio.to_thread(_apply)
    return await asyncio.to_thread(_build_record_response, record, session, _latest_guide(record, session))


class FieldCorrectionPayload(BaseModel):
    # [2026-07-25 수정] 자유 입력 value를 없앴다 — 이 칸에 적용될 값은 보호자·기관이
    # 미리 지정한 suggested_value 하나뿐이라(환자는 드롭다운에서 그 값을 선택·확인만
    # 함), 환자가 직접 값을 보낼 필요도, 다른 값을 보낼 여지도 없다.
    field_name: str


@router.patch("/{record_id}/medications/{medication_id}/correct")
async def correct_medication_field(
    record_id: int,
    medication_id: int,
    payload: FieldCorrectionPayload,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """환자가 보호자·기관이 지목한 칸 하나를 수정한다 — 활성 플래그가 있는 칸만 허용한다
    (프론트 잠금은 UI일 뿐이라, 서버에서도 실제로 지목된 칸인지 확인해야 함).

    [2026-07-27 수정, 코드 리뷰 반영] role 체크가 없어서 require_actor_patient_access를
    통과하는 연결된 보호자·기관도 호출할 수 있었다 — 수정을 요청한 보호자 본인이 그
    suggested_value를 스스로 적용해버리면 "환자가 확인하고 반영"하는 검토 흐름의 목적이
    무력화된다. request_correction/mark_reviewed와 반대로 여기는 환자 전용으로 막는다."""
    role, _subject = actor
    if role != "patient":
        raise HTTPException(403, "환자 본인만 수정을 반영할 수 있어요")
    if payload.field_name not in _CORRECTABLE_FIELDS:
        raise HTTPException(422, f"수정할 수 없는 항목이에요: {payload.field_name}")

    def _apply() -> MedicalRecord:
        rec = session.get(MedicalRecord, record_id)
        if not rec:
            raise HTTPException(404, "해당 기록을 찾을 수 없어요")
        require_actor_patient_access(rec.patient_id, actor, session)

        item = session.get(OcrResult, medication_id)
        if not item or item.record_id != record_id:
            raise HTTPException(404, "해당 약물 항목을 찾을 수 없어요")

        flag = session.exec(
            select(MedicationFieldFlag)
            .where(MedicationFieldFlag.ocr_result_id == medication_id)
            .where(MedicationFieldFlag.field_name == payload.field_name)
            .where(MedicationFieldFlag.corrected == False)  # noqa: E712
        ).first()
        if not flag:
            raise HTTPException(409, "보호자·기관이 수정을 요청한 칸이 아니에요")

        setattr(item, payload.field_name, flag.suggested_value)
        flag.corrected = True
        flag.corrected_at = datetime.now()
        session.add(item)
        session.add(flag)
        session.commit()

        # 이 처방전에 남아있는 미수정 플래그가 하나도 없으면 보호자·기관에게 알린다.
        item_ids = {i.id for i in session.exec(select(OcrResult).where(OcrResult.record_id == record_id)).all()}
        remaining = session.exec(
            select(MedicationFieldFlag)
            .where(MedicationFieldFlag.ocr_result_id.in_(item_ids))
            .where(MedicationFieldFlag.corrected == False)  # noqa: E712
        ).first()
        if not remaining:
            # [2026-07-30 추가] 환자가 지목된 칸을 전부 고치기 전까지는 caregiver_review_status가
            # 계속 "needs_correction"(보호자 요청, 환자 응답 대기)이었는데, 다 고친 뒤에도 이 값이
            # 안 바뀌어서 보호자 화면이 "아직 환자가 안 고쳤다"는 문구를 계속 보여주는 버그가 있었다.
            # 이제 "환자가 다 고쳐서 재검토 대기" 상태로 명확히 전이시킨다.
            rec.caregiver_review_status = "correction_completed"
            session.add(rec)
            caregiver_ids = session.exec(
                select(CaregiverPatient.caregiver_id)
                .where(CaregiverPatient.patient_id == rec.patient_id)
                .where(CaregiverPatient.status != "revoked")
            ).all()
            for caregiver_id in caregiver_ids:
                session.add(
                    RecordCorrectionNotice(
                        recipient_role="caregiver",
                        recipient_id=caregiver_id,
                        record_id=rec.id,
                        event="correction_completed",
                    )
                )
                if caregiver_wants_notifications(caregiver_id, rec.patient_id, session):
                    send_push_to_recipient(
                        session, "caregiver", caregiver_id,
                        title="환자가 처방전을 수정했어요", body="요청한 칸을 모두 고쳤어요. 확인하고 검토를 완료해주세요.",
                        url=f"/records/{rec.id}/guide",
                    )
            session.commit()

        session.refresh(rec)
        return rec

    record = await asyncio.to_thread(_apply)
    return await asyncio.to_thread(_build_record_response, record, session, _latest_guide(record, session))


class RecordCorrectionNoticePublic(BaseModel):
    id: int
    record_id: int
    patient_id: int
    patient_name: str
    event: str
    created_at: datetime
    read_at: datetime | None = None


@router.get("/notices", response_model=list[RecordCorrectionNoticePublic])
def list_correction_notices(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """읽지 않은 처방전 검토 알림 — 환자는 "수정 요청"을, 보호자·기관은 "검토 요청"/"수정 완료"와
    (요청한 사람 본인 제외) 다른 보호자·기관이 보낸 "수정 요청"을 받는다.
    Dashboard.tsx/MonitoringDashboard.tsx가 배너로 보여주고 record_id로 바로 이동시킨다."""
    role, subject = actor
    notices = session.exec(
        select(RecordCorrectionNotice)
        .where(RecordCorrectionNotice.recipient_role == role)
        .where(RecordCorrectionNotice.recipient_id == subject.id)
        .where(RecordCorrectionNotice.read_at == None)  # noqa: E711
        .order_by(RecordCorrectionNotice.created_at.desc())
    ).all()
    result = []
    for notice in notices:
        record = session.get(MedicalRecord, notice.record_id)
        if not record:
            continue
        patient = session.get(Patient, record.patient_id)
        result.append(
            RecordCorrectionNoticePublic(
                id=notice.id,
                record_id=notice.record_id,
                patient_id=record.patient_id,
                patient_name=patient.name if patient else "",
                event=notice.event,
                created_at=notice.created_at,
                read_at=notice.read_at,
            )
        )
    return result


@router.post("/notices/{notice_id}/read")
def mark_correction_notice_read(
    notice_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    role, subject = actor
    notice = session.get(RecordCorrectionNotice, notice_id)
    if not notice or notice.recipient_role != role or notice.recipient_id != subject.id:
        raise HTTPException(404, "해당 알림을 찾을 수 없어요")
    notice.read_at = datetime.now()
    session.add(notice)
    session.commit()
    return {"status": "read"}


@router.get("/{record_id}/image")
def get_record_image(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """[2026-07-25 추가] 처방전 원본 사진 — 보호자·기관이 수정을 요청할 때, 환자가 수정할
    때 둘 다 참고할 수 있게. record_id로만 조회해서 이 기록에 연결된 사진만 내려준다
    (다른 처방전 사진이 섞여 나올 수 없음). 수동 입력(manual_entry)이거나 이 기능 이전에
    등록된 처방전(원본 파일명만 저장돼 있던 시절)은 사진이 없다 — 404."""
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    stored_image = session.get(MedicalRecordImage, record_id)
    if stored_image is not None:
        return Response(
            content=stored_image.content,
            media_type=stored_image.content_type,
            headers={"Content-Length": str(stored_image.byte_size)},
        )

    # 마이그레이션 이전에 로컬 디스크에 저장된 기존 기록은 계속 조회할 수 있게 유지한다.
    if not record.image_path or not record.image_path.startswith("uploads/prescriptions/"):
        raise HTTPException(404, "저장된 처방전 사진이 없어요")
    image_file = _ROOT / record.image_path
    if not image_file.is_file():
        raise HTTPException(404, "저장된 처방전 사진이 없어요")
    return FileResponse(image_file)


@router.get("/{record_id}")
def get_record(
    record_id: int,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 (Processing에서 받은 데이터가 없을 때 대비)"""
    record = session.get(MedicalRecord, record_id)
    if not record or record.deleted_at is not None:
        raise HTTPException(404, "해당 기록을 찾을 수 없어요")
    require_actor_patient_access(record.patient_id, actor, session)

    guide = session.exec(
        select(GuideResult)
        .where(GuideResult.record_id == record_id)
        .order_by(GuideResult.id.desc())  # ty: ignore[unresolved-attribute]
    ).first()
    return _build_record_response(record, session, guide)
