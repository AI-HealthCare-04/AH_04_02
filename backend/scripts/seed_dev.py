"""
scripts/seed_dev.py — 개발자 테스트용 가상 데이터 시드 (2026-07-14 추가)

실행:
    python scripts/seed_dev.py

DATABASE_URL 환경변수(또는 .env)가 가리키는 DB에 가상의 보호자 1명 + 환자 2명 +
의약품/스케줄/복약기록 몇 건을 만든다. 실제 환자 개인정보는 전혀 쓰지 않는다 —
이름·전화번호·이메일 전부 가상의 예시 값이다.

이미 같은 이메일의 시드 계정이 있으면 건너뛴다(재실행 안전 — migrate_local_data.py와
동일한 원칙). 팀 공통 개발 DB(APP_ENV=development)에도 안전하게 실행할 수 있도록,
실제 DB 이름(dbname)에 "prod"가 들어 있으면 실행을 거부한다(운영 DB 오염 방지).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database  # noqa: E402
import models  # noqa: E402
from core.auth import hash_password  # noqa: E402
from core.security import normalize_email  # noqa: E402

SEED_CAREGIVER_EMAIL = normalize_email("seed.guardian@example.test")
SEED_PATIENTS = [
    {"email": "seed.patient1@example.test", "name": "홍길동(테스트)", "phone": "010-0000-0001"},
    {"email": "seed.patient2@example.test", "name": "김순자(테스트)", "phone": "010-0000-0002"},
]
SEED_PASSWORD = "seed-password-1234"


def _guard_against_production(database_url: str) -> None:
    url = make_url(database_url)
    db_name = (url.database or "").lower()
    if "prod" in db_name:
        print(f"❌ DATABASE_URL의 DB 이름({url.database})에 'prod'가 포함돼 있어 실행을 거부합니다.")
        print("   seed_dev.py는 개발/테스트 DB 전용입니다 — 운영 DB에는 절대 실행하지 마세요.")
        sys.exit(1)


def main() -> None:
    _guard_against_production(database.DATABASE_URL)

    with Session(database.engine) as session:
        existing = session.exec(
            select(models.Caregiver).where(models.Caregiver.email == SEED_CAREGIVER_EMAIL)
        ).first()
        if existing:
            print(f"이미 시드돼 있습니다(caregiver email={SEED_CAREGIVER_EMAIL}) — 건너뜁니다.")
            return

        caregiver = models.Caregiver(
            email=SEED_CAREGIVER_EMAIL,
            hashed_password=hash_password(SEED_PASSWORD),
            relation_type="guardian",
        )
        caregiver.name = "테스트 보호자(seed)"
        caregiver.phone = "010-0000-0000"
        session.add(caregiver)
        session.commit()
        session.refresh(caregiver)
        print(f"caregiver 생성: id={caregiver.id} email={caregiver.email} password={SEED_PASSWORD}")

        for i, p_data in enumerate(SEED_PATIENTS, start=1):
            patient = models.Patient(
                email=normalize_email(p_data["email"]),
                hashed_password=hash_password(SEED_PASSWORD),
            )
            patient.name = p_data["name"]
            patient.phone = p_data["phone"]
            session.add(patient)
            session.commit()
            session.refresh(patient)
            print(f"patient{i} 생성: id={patient.id} email={patient.email} password={SEED_PASSWORD}")

            session.add(models.CaregiverPatient(caregiver_id=caregiver.id, patient_id=patient.id))
            session.commit()

            # 가상 의약품 1~2건 (manual로 등록한 것처럼)
            med1 = models.PatientMedication(
                patient_id=patient.id,
                medication_name="암로디핀정5밀리그램(가상)",
                dosage_amount="1",
                dosage_unit="정",
                frequency_per_day=1,
                administration_route="경구",
                start_date=date.today().isoformat(),
                source_type="manual",
                verification_status="user_confirmed",
                is_active=True,
            )
            session.add(med1)
            session.commit()
            session.refresh(med1)

            med2 = models.PatientMedication(
                patient_id=patient.id,
                medication_name="메트포르민(가상, OCR 원문 예시)",
                source_type="prescription_ocr",
                source_raw_text="메트포르민 500mg 1일 2회 (OCR 인식 원문 예시)",
                verification_status="unverified",
                is_active=True,
            )
            session.add(med2)
            session.commit()
            session.refresh(med2)

            schedule = models.MedicationSchedule(
                patient_id=patient.id,
                patient_medication_id=med1.id,
                drug_name=med1.medication_name,
                time_slot="08:00",
                meal_relation="식후",
                caregiver_alert=True,
            )
            session.add(schedule)
            session.commit()
            session.refresh(schedule)

            record = models.MedicationRecord(
                patient_medication_id=med1.id,
                schedule_id=schedule.id,
                scheduled_at=datetime.now() - timedelta(hours=2),
                taken_at=datetime.now() - timedelta(hours=2),
                status="taken",
                verification_method="self_report",
            )
            session.add(record)
            session.commit()

            print(f"  └ 의약품 2건 + 스케줄 1건 + 복약기록 1건 생성 완료")

    print("\n=== 시드 완료 ===")
    print(f"로그인 테스트: identifier={SEED_CAREGIVER_EMAIL} 또는 patient 이메일, password={SEED_PASSWORD}")


if __name__ == "__main__":
    main()
