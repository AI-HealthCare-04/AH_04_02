"""Patient/Caregiver의 .name/.phone 프로퍼티(투명 암복호화) 테스트 (담당: 김영혜)"""
from models import Caregiver, Patient


def test_patient_name_round_trip_and_stored_encrypted():
    patient = Patient()
    patient.name = "김건강"
    assert patient.name == "김건강"
    assert patient.name_encrypted != "김건강"  # DB에는 평문으로 안 남아야 함


def test_patient_phone_round_trip_and_hash_set():
    patient = Patient()
    patient.name = "김건강"
    patient.phone = "010-1234-5678"
    assert patient.phone == "010-1234-5678"
    assert patient.phone_encrypted != "010-1234-5678"
    assert patient.phone_hash is not None
    # 다른 표기(하이픈 없이)로 같은 번호를 다시 넣어도 조회용 해시는 동일해야 함
    other = Patient()
    other.name = "다른환자"
    other.phone = "01012345678"
    assert other.phone_hash == patient.phone_hash


def test_patient_phone_none_clears_encrypted_and_hash():
    patient = Patient()
    patient.name = "김건강"
    patient.phone = "010-1234-5678"
    patient.phone = None
    assert patient.phone is None
    assert patient.phone_encrypted is None
    assert patient.phone_hash is None


def test_caregiver_name_and_phone_round_trip():
    caregiver = Caregiver()
    caregiver.name = "박보호"
    caregiver.phone = "010-9999-0000"
    assert caregiver.name == "박보호"
    assert caregiver.phone == "010-9999-0000"
    assert caregiver.name_encrypted != "박보호"
    assert caregiver.phone_encrypted != "010-9999-0000"
    assert caregiver.phone_hash is not None
