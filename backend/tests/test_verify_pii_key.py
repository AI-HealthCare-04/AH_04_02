"""
test_verify_pii_key.py — verify_pii_key_against_db() 단위 테스트

실제 사고 원인: "형식은 유효하지만 기존 DB와 맞지 않는 다른 키"가 들어가도
기동 시점에 검출되지 않아 로그인 실패로만 드러났던 케이스를 재현해 검증한다.

PR #112 리뷰 반영: patients만 확인하던 로직을 caregivers까지 검증하도록 수정한 뒤,
해당 케이스(patients 비어있고 caregivers만 데이터 있는 경우)를 포함한 6가지 시나리오를
모두 커버한다.
"""
import models  # noqa: F401 — patients/caregivers 테이블 메타데이터 등록용
import pytest
from core.security import encrypt_pii, verify_pii_key_against_db
from cryptography.fernet import Fernet
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture()
def db_engine():
    """각 테스트마다 완전히 분리된 in-memory SQLite 엔진."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_both_tables_empty_skips_check(db_engine):
    """patients와 caregivers 모두 비어 있으면 검증 대상 없음 — 에러 없이 통과."""
    verify_pii_key_against_db(db_engine)  # raises nothing


def test_patients_has_data_correct_key(db_engine):
    """patients에 암호화 레코드가 있고 현재 키가 맞으면 통과한다."""
    with Session(db_engine) as session:
        session.add(models.Patient(name_encrypted=encrypt_pii("홍길동")))
        session.commit()
    verify_pii_key_against_db(db_engine)


def test_caregivers_only_correct_key(db_engine):
    """patients가 비어 있고 caregivers에만 암호화 레코드가 있어도 caregivers로 검증한다.
    이 케이스가 기존 구현(patients만 조회)의 오탐 케이스였다."""
    with Session(db_engine) as session:
        session.add(models.Caregiver(name_encrypted=encrypt_pii("보호자A")))
        session.commit()
    verify_pii_key_against_db(db_engine)


def test_both_tables_correct_key(db_engine):
    """patients와 caregivers 양쪽에 암호화 레코드가 있고 키가 맞으면 통과한다."""
    with Session(db_engine) as session:
        session.add(models.Patient(name_encrypted=encrypt_pii("홍길동")))
        session.add(models.Caregiver(name_encrypted=encrypt_pii("보호자A")))
        session.commit()
    verify_pii_key_against_db(db_engine)


def test_patients_wrong_key_raises(db_engine):
    """patients에 다른 키로 암호화된 레코드가 있으면 RuntimeError로 기동을 막는다."""
    other_encrypted = Fernet(Fernet.generate_key()).encrypt("홍길동".encode()).decode()
    with Session(db_engine) as session:
        patient = models.Patient()
        patient.name_encrypted = other_encrypted  # .name setter를 우회해 다른 키 암호문 직접 주입
        session.add(patient)
        session.commit()
    with pytest.raises(RuntimeError, match="PII_ENCRYPTION_KEY가 기존 데이터와 일치하지 않는"):
        verify_pii_key_against_db(db_engine)


def test_caregivers_only_wrong_key_raises(db_engine):
    """patients가 비어 있고 caregivers에 다른 키로 암호화된 레코드가 있어도 검출한다."""
    other_encrypted = Fernet(Fernet.generate_key()).encrypt("보호자A".encode()).decode()
    with Session(db_engine) as session:
        caregiver = models.Caregiver()
        caregiver.name_encrypted = other_encrypted  # .name setter를 우회해 다른 키 암호문 직접 주입
        session.add(caregiver)
        session.commit()
    with pytest.raises(RuntimeError, match="PII_ENCRYPTION_KEY가 기존 데이터와 일치하지 않는"):
        verify_pii_key_against_db(db_engine)


def test_patients_correct_caregivers_wrong_key_raises(db_engine):
    """patients 키는 맞고 caregivers에만 다른 키 암호문이 있어도 RuntimeError를 낸다.

    return을 유지하면 patients 통과 후 caregivers를 검사하지 않아 이 케이스를 놓친다 —
    재리뷰 지적(fkmc10101-hub)에서 발견된 케이스로, 두 테이블 모두 끝까지 검사해야 잡힌다.
    """
    with Session(db_engine) as session:
        session.add(models.Patient(name_encrypted=encrypt_pii("홍길동")))
        session.commit()
    other_encrypted = Fernet(Fernet.generate_key()).encrypt("보호자A".encode()).decode()
    with Session(db_engine) as session:
        caregiver = models.Caregiver()
        caregiver.name_encrypted = other_encrypted
        session.add(caregiver)
        session.commit()
    with pytest.raises(RuntimeError, match="PII_ENCRYPTION_KEY가 기존 데이터와 일치하지 않는"):
        verify_pii_key_against_db(db_engine)
