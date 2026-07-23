"""
test_records_router_duplicate_prescription.py — _create_schedules_from_ocr()의
날짜 기반 재처방 판정 (2026-07-23 추가)

기존엔 같은 약 이름으로 활성 일정이 있으면 무조건 "중복"으로 건너뛰었다 — 그래서
실제로는 다음 달 재처방(용량/횟수가 바뀔 수 있음)인데도 "이미 등록된 처방이에요"로
막혀버렸다. 이제 두 처방전의 조제일자가 다르면 재처방으로 보고 기존 일정을
비활성화한 뒤 새로 등록한다. 날짜를 모르면(구형 데이터/파싱 실패/수동입력) 비교할
근거가 없으니 기존처럼 이름만으로 중복 처리한다(회귀 방지).
"""
import pytest
from models import MedicalRecord, MedicationSchedule, OcrResult, Patient
from routers.records_router import _create_schedules_from_ocr
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_patient(session: Session) -> Patient:
    pt = Patient(hashed_password="x")
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_record(session: Session, patient_id: int, prescription_date: str | None) -> MedicalRecord:
    record = MedicalRecord(
        patient_id=patient_id, image_path="x.jpg", status="review_required",
        prescription_date=prescription_date,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _make_ocr_item(session: Session, record_id: int, drug_name: str = "암로디핀정5mg") -> OcrResult:
    item = OcrResult(record_id=record_id, drug_name=drug_name, frequency="1일 1회")
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _active_schedules(session: Session, patient_id: int) -> list[MedicationSchedule]:
    return session.exec(
        select(MedicationSchedule)
        .where(MedicationSchedule.patient_id == patient_id)
        .where(MedicationSchedule.active == True)  # noqa: E712
    ).all()


class TestDateBasedDuplicateDetection:
    def test_same_drug_same_date_is_duplicate(self, session: Session):
        pt = _make_patient(session)
        record1 = _make_record(session, pt.id, "2026-07-01")
        item1 = _make_ocr_item(session, record1.id)
        _create_schedules_from_ocr(record1, [item1], session)

        record2 = _make_record(session, pt.id, "2026-07-01")
        item2 = _make_ocr_item(session, record2.id)
        duplicates = _create_schedules_from_ocr(record2, [item2], session)

        assert duplicates == ["암로디핀정5mg"]
        assert len(_active_schedules(session, pt.id)) == 1

    def test_same_drug_different_date_is_new_prescription_and_supersedes_old(self, session: Session):
        pt = _make_patient(session)
        record1 = _make_record(session, pt.id, "2026-06-01")
        item1 = _make_ocr_item(session, record1.id)
        _create_schedules_from_ocr(record1, [item1], session)
        old_schedule_id = _active_schedules(session, pt.id)[0].id

        record2 = _make_record(session, pt.id, "2026-07-01")
        item2 = _make_ocr_item(session, record2.id)
        duplicates = _create_schedules_from_ocr(record2, [item2], session)

        assert duplicates == []
        active = _active_schedules(session, pt.id)
        assert len(active) == 1
        assert active[0].id != old_schedule_id  # 새 일정으로 교체됨
        assert session.get(MedicationSchedule, old_schedule_id).active is False

    def test_unknown_date_falls_back_to_name_only_duplicate_check(self, session: Session):
        pt = _make_patient(session)
        record1 = _make_record(session, pt.id, None)
        item1 = _make_ocr_item(session, record1.id)
        _create_schedules_from_ocr(record1, [item1], session)

        record2 = _make_record(session, pt.id, None)
        item2 = _make_ocr_item(session, record2.id)
        duplicates = _create_schedules_from_ocr(record2, [item2], session)

        assert duplicates == ["암로디핀정5mg"]
        assert len(_active_schedules(session, pt.id)) == 1

    def test_different_drug_names_never_collide(self, session: Session):
        pt = _make_patient(session)
        record1 = _make_record(session, pt.id, "2026-07-01")
        item1 = _make_ocr_item(session, record1.id, drug_name="암로디핀정5mg")
        _create_schedules_from_ocr(record1, [item1], session)

        record2 = _make_record(session, pt.id, "2026-07-01")
        item2 = _make_ocr_item(session, record2.id, drug_name="메트포르민정500mg")
        duplicates = _create_schedules_from_ocr(record2, [item2], session)

        assert duplicates == []
        assert len(_active_schedules(session, pt.id)) == 2
