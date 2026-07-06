"""
ocr_router.py — 담당: 권순현

지금은 "흐름 확인용 가짜 데이터"만 들어있습니다.
Day3에 할 일: stub_ocr_upload() 안의 가짜 OcrResult 생성 부분을
실제 CLOVA OCR 호출(ocr_interface.py) 결과로 바꿔 끼우면 됩니다.
나머지(파일 받기, DB 저장하는 틀)는 이미 만들어져 있어서 그대로 쓰면 됩니다.
"""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlmodel import Session

from database import get_session
from models import MedicalRecord, OcrResult

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.get("/ping")
def ping():
    """서버에 이 라우터가 잘 붙었는지 확인용. /docs에서 눌러보면 됨"""
    return {"status": "ok", "owner": "권순현"}


@router.post("/test")
def stub_ocr_upload(
    patient_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    """
    임시 stub 엔드포인트.
    지금 하는 일: 파일을 받아서 → MedicalRecord 1행 생성 → 가짜 OcrResult 1행 생성
    TODO(권순현): 아래 "가짜 데이터" 부분을 실제 CLOVA 호출 결과로 교체

    ⚠️ [7/6 변경] patient_id가 필수 파라미터로 추가됨 (환자 구분 도입).
    테스트할 땐 데모 시드 환자 id=1을 쓰면 됩니다.
    """
    record = MedicalRecord(patient_id=patient_id, image_path=file.filename, status="completed")
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
        confidence=0.99,
        review_required=False,
    )
    session.add(fake_result)
    session.commit()
    # ↑↑↑ 여기까지 ↑↑↑

    return {
        "record_id": record.id,
        "status": "completed",
        "note": "⚠️ 가짜 데이터입니다 — 실제 CLOVA 연동 전까지만 사용",
    }
