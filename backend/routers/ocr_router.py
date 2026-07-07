"""
ocr_router.py — 담당: 권순현

지금은 "흐름 확인용 가짜 데이터"만 들어있습니다.
Day3에 할 일: run_ocr_stub() 안의 가짜 OcrResult 생성 부분을
실제 CLOVA OCR 호출(ocr_interface.py) 결과로 바꿔 끼우면 됩니다.

[7/6 추가] 로직을 run_ocr_stub() 함수로 분리했습니다 — /ocr/test(개별 테스트용)와
records_router.py(업로드→OCR→가이드 한번에 처리)가 이 함수를 같이 씁니다.
CLOVA 연동 시 이 함수 하나만 고치면 양쪽 다 실제 데이터로 바뀝니다.
"""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlmodel import Session

from database import get_session
from models import MedicalRecord, OcrResult

router = APIRouter(prefix="/ocr", tags=["OCR"])


def run_ocr_stub(patient_id: int, filename: str, session: Session) -> MedicalRecord:
    """
    TODO(권순현): 이 함수 내부를 실제 CLOVA 호출 + 파싱 결과(ocr_interface.py)로 교체하면 됩니다.
    실제 로직에서는 OcrResult.confidence가 낮은 항목이 있으면 review_required=True로 표시하고,
    그 경우 record.status도 "review_required"로 맞춰주세요 — records_router.py가 그 상태를
    보고 RAG 호출을 건너뛰도록 분기돼 있습니다(PR #9 합의 반영, 7/8).

    지금은 파일 내용은 안 보고 파일명만 기록하는 가짜 버전입니다.
    [테스트용] 파일명에 "review"가 들어있으면 저신뢰 케이스를 흉내냅니다.

    실패 케이스(REQ-008) 처리할 때는 여기서 MedicalRecord.status="failed",
    failure_reason에 사유를 넣고 raise 없이 그대로 record를 반환하면
    records_router가 알아서 "실패로 끝난 처리 결과"로 응답합니다.
    """
    simulate_review = "review" in filename.lower()
    status = "review_required" if simulate_review else "completed"

    record = MedicalRecord(patient_id=patient_id, image_path=filename, status=status)
    session.add(record)
    session.commit()
    session.refresh(record)

    # ↓↓↓ 여기부터 가짜 데이터 — CLOVA 연동 완료되면 이 블록을 실제 결과로 교체 ↓↓↓
    fake_result = OcrResult(
        record_id=record.id,
        drug_name="테스트약품 500mg",
        drug_code="000000000",
        dosage="1일 3회",
        frequency="식후 30분",
        diagnosis="테스트 진단명",
        drug_class="테스트 분류",
        confidence=0.4 if simulate_review else 0.99,
        review_required=simulate_review,
    )
    session.add(fake_result)
    session.commit()
    # ↑↑↑ 여기까지 ↑↑↑

    return record


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "권순현"}


@router.post("/test")
def stub_ocr_upload(
    patient_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    """OCR만 따로 테스트하고 싶을 때 쓰는 엔드포인트 (실제 흐름은 POST /records 사용)"""
    record = run_ocr_stub(patient_id, file.filename, session)
    return {
        "record_id": record.id,
        "status": "completed",
        "note": "⚠️ 가짜 데이터입니다 — 실제 CLOVA 연동 전까지만 사용",
    }
