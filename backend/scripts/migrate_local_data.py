"""
scripts/migrate_local_data.py — 기존 로컬 DB(회원/환자 의약품)를 공통 개발 DB로 이전 (2026-07-14 추가)

실행 예:
    python scripts/migrate_local_data.py \\
        --source-url "sqlite:///./app.db" \\
        --target-url "mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE" \\
        --dry-run

--source-url/--target-url/PII 키 4종은 코드에 하드코딩하지 않는다 — 인자로 직접 주거나,
아래 환경변수로도 줄 수 있다(인자가 없으면 환경변수를 읽음):
    SOURCE_DATABASE_URL / TARGET_DATABASE_URL
    SOURCE_PII_ENCRYPTION_KEY / SOURCE_PII_HASH_SECRET
    TARGET_PII_ENCRYPTION_KEY / TARGET_PII_HASH_SECRET

[왜 PII 키가 4개(소스 2 + 타깃 2)나 필요한가]
Patient/Caregiver의 name/phone은 Fernet으로 암호화돼 있는데(security.py), 각 로컬 환경마다
서로 다른 PII_ENCRYPTION_KEY를 쓰고 있을 가능성이 높다. 암호문을 그대로 복사하면 타깃 DB의
키로는 복호화가 안 되는 "영구히 못 읽는 값"이 된다 — 그래서 반드시 [소스 키로 복호화 →
타깃 키로 재암호화] 과정을 거친다. bcrypt 비밀번호 해시(hashed_password)는 원래 단방향이라
복호화 자체가 불가능하고 필요하지도 않으므로 그대로(불투명한 문자열로) 복사한다 — 절대
복호화하거나 평문으로 바꾸지 않는다.

[이전 범위]
caregivers → patients → caregiver_patients → patient_medications → medication_schedules
→ medication_records 순서로만 옮긴다. medical_records/ocr_results/guide_results/
medication_logs 등 OCR·RAG 이력은 이 스크립트의 범위 밖이다(요청 범위인 "회원가입 데이터 +
환자 의약품 데이터"에 집중) — 필요해지면 별도로 확장할 것.

[안전장치]
- --dry-run: 타깃에 아무것도 쓰지 않고 무엇을 할지만 출력한다.
- 실제 실행(--dry-run 없이)은 --yes-i-have-a-backup 플래그가 없으면 거부한다 — 이 스크립트가
  백업을 대신 떠주지 않으니, 실행 전 타깃 DB를 반드시 백업해두라는 의도적인 안전장치.
- 타깃에는 오직 INSERT만 한다 — 기존 타깃 행은 절대 수정/삭제하지 않는다.
- 재실행해도 중복 적재되지 않도록, 각 테이블마다 자연키(이메일/phone_hash 등)나 이미 옮긴
  적 있는 조합으로 "이미 있으면 건너뛴다"를 확인한다 (아래 각 _migrate_* 함수 docstring 참고).
- 실패한 행은 예외를 던지지 않고 failed_rows 로그 파일에 남기고 나머지 계속 진행한다.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from sqlmodel import Session, SQLModel, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402 — sys.path 조정 이후에 import (테이블 정의를 metadata에 등록)


# ══════════════════════════════════════════
# PII 재암호화 헬퍼 — security.py와 동일한 알고리즘을 독립적으로 구현
# (security.py는 프로세스당 키 1쌍만 전제하는 싱글턴이라, 소스/타깃 두 키를 동시에
# 쓸 수 없어서 이 스크립트 안에서 별도로 구현했다)
# ══════════════════════════════════════════
@dataclass
class PiiKeys:
    encryption_key: str
    hash_secret: str

    def __post_init__(self):
        self._fernet = Fernet(self.encryption_key.encode())
        self._hash_secret_bytes = self.hash_secret.encode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.decrypt(value.encode()).decode()

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def hash_phone(self, phone: str) -> str:
        normalized = phone.replace("-", "").replace(" ", "")
        return hmac.new(self._hash_secret_bytes, normalized.encode(), hashlib.sha256).hexdigest()


def normalize_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


# ══════════════════════════════════════════
# 실행 결과 집계
# ══════════════════════════════════════════
@dataclass
class MigrationStats:
    migrated: int = 0
    skipped_existing: int = 0
    failed: int = 0
    failed_rows: list[dict] = field(default_factory=list)

    def report(self, table_name: str) -> None:
        print(
            f"  [{table_name}] 이전 {self.migrated}건 / 중복(건너뜀) {self.skipped_existing}건 "
            f"/ 실패 {self.failed}건"
        )


def _write_failed_log(log_path: Path, all_failed: dict[str, list[dict]]) -> None:
    if not any(all_failed.values()):
        return
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(all_failed, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n⚠️  실패한 행이 있습니다 — 상세 내용: {log_path}")


# ══════════════════════════════════════════
# 테이블별 이전 함수 (users → patients → medications → schedules → records 순서)
# ══════════════════════════════════════════
def _migrate_caregivers(
    source: Session, target: Session, source_keys: PiiKeys, target_keys: PiiKeys, dry_run: bool
) -> tuple[MigrationStats, dict[int, int]]:
    """caregivers 이전. 자연키: 정규화된 email(유니크 제약과 동일 기준) — 같은 이메일이
    타깃에 이미 있으면 건너뛴다(재실행 안전). email이 없는 caregiver는 이 프로젝트에서
    사실상 없다고 가정(로그인 식별자 필수)하지만, 혹시 있으면 그대로 새로 만든다(중복
    감지 불가 — 재실행 시 중복될 수 있음을 failed_rows가 아니라 stdout 경고로 알린다)."""
    stats = MigrationStats()
    id_map: dict[int, int] = {}

    for row in source.exec(select(models.Caregiver)).all():
        try:
            email = normalize_email(row.email)
            if email:
                existing = target.exec(select(models.Caregiver).where(models.Caregiver.email == email)).first()
                if existing:
                    id_map[row.id] = existing.id
                    stats.skipped_existing += 1
                    continue
            else:
                print(f"    ⚠️ caregiver id={row.id}: email 없음 — 중복 감지 불가, 항상 새로 생성됨")

            name_plain = source_keys.decrypt(row.name_encrypted) if row.name_encrypted else ""
            phone_plain = source_keys.decrypt(row.phone_encrypted) if row.phone_encrypted else None

            new_row = models.Caregiver(
                email=email,
                hashed_password=row.hashed_password,  # bcrypt 해시 — 그대로 복사, 복호화 금지
                relation_type=row.relation_type,
                birth_date=row.birth_date,
                push_enabled=row.push_enabled,
                sms_enabled=row.sms_enabled,
                email_opt_in=row.email_opt_in,
                org_name=row.org_name,
                org_type=row.org_type,
                business_reg_no=row.business_reg_no,
                manager_name=row.manager_name,
                manager_phone=row.manager_phone,
                created_at=row.created_at,
            )
            new_row.name_encrypted = target_keys.encrypt(name_plain) if name_plain else ""
            if phone_plain:
                new_row.phone_encrypted = target_keys.encrypt(phone_plain)
                new_row.phone_hash = target_keys.hash_phone(phone_plain)

            if dry_run:
                stats.migrated += 1
                id_map[row.id] = -row.id  # dry-run 표시용 임시값(실제 FK 이전엔 안 씀)
                continue

            target.add(new_row)
            target.commit()
            target.refresh(new_row)
            id_map[row.id] = new_row.id
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001 — 이 행만 실패 처리하고 나머지는 계속 진행
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "caregivers", "error": str(exc)})

    return stats, id_map


def _migrate_patients(
    source: Session, target: Session, source_keys: PiiKeys, target_keys: PiiKeys, dry_run: bool
) -> tuple[MigrationStats, dict[int, int]]:
    """patients 이전. 자연키: 정규화된 email(있으면) → 없으면 phone_hash(있으면) → 그것도
    없으면 자연키가 아예 없어 중복 감지가 불가능하니 항상 새로 생성하고 경고를 남긴다."""
    stats = MigrationStats()
    id_map: dict[int, int] = {}

    for row in source.exec(select(models.Patient)).all():
        try:
            email = normalize_email(row.email)
            phone_plain = source_keys.decrypt(row.phone_encrypted) if row.phone_encrypted else None
            existing = None
            if email:
                existing = target.exec(select(models.Patient).where(models.Patient.email == email)).first()
            elif phone_plain:
                target_phone_hash = target_keys.hash_phone(phone_plain)
                existing = target.exec(
                    select(models.Patient).where(models.Patient.phone_hash == target_phone_hash)
                ).first()
            else:
                print(f"    ⚠️ patient id={row.id}: email/phone 둘 다 없음 — 중복 감지 불가, 항상 새로 생성됨")

            if existing:
                id_map[row.id] = existing.id
                stats.skipped_existing += 1
                continue

            name_plain = source_keys.decrypt(row.name_encrypted) if row.name_encrypted else ""

            new_row = models.Patient(
                email=email,
                note=row.note,
                birth_date=row.birth_date,
                hashed_password=row.hashed_password,  # bcrypt 해시 — 그대로 복사, 복호화 금지
                push_enabled=row.push_enabled,
                sms_enabled=row.sms_enabled,
                email_opt_in=row.email_opt_in,
                created_at=row.created_at,
            )
            new_row.name_encrypted = target_keys.encrypt(name_plain) if name_plain else ""
            if phone_plain:
                new_row.phone_encrypted = target_keys.encrypt(phone_plain)
                new_row.phone_hash = target_keys.hash_phone(phone_plain)

            if dry_run:
                stats.migrated += 1
                id_map[row.id] = -row.id
                continue

            target.add(new_row)
            target.commit()
            target.refresh(new_row)
            id_map[row.id] = new_row.id
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "patients", "error": str(exc)})

    return stats, id_map


def _migrate_caregiver_patients(
    source: Session,
    target: Session,
    caregiver_id_map: dict[int, int],
    patient_id_map: dict[int, int],
    dry_run: bool,
) -> MigrationStats:
    """caregiver_patients(다대다 연결) 이전. 자연키: (타깃 caregiver_id, 타깃 patient_id)
    조합 — 이미 같은 연결이 타깃에 있으면 건너뛴다."""
    stats = MigrationStats()

    for row in source.exec(select(models.CaregiverPatient)).all():
        try:
            target_caregiver_id = caregiver_id_map.get(row.caregiver_id)
            target_patient_id = patient_id_map.get(row.patient_id)
            if target_caregiver_id is None or target_patient_id is None:
                stats.failed += 1
                stats.failed_rows.append(
                    {"source_id": row.id, "table": "caregiver_patients", "error": "caregiver/patient 이전 실패로 연결 불가"}
                )
                continue

            if dry_run:
                stats.migrated += 1
                continue

            existing = target.exec(
                select(models.CaregiverPatient)
                .where(models.CaregiverPatient.caregiver_id == target_caregiver_id)
                .where(models.CaregiverPatient.patient_id == target_patient_id)
            ).first()
            if existing:
                stats.skipped_existing += 1
                continue

            target.add(
                models.CaregiverPatient(
                    caregiver_id=target_caregiver_id,
                    patient_id=target_patient_id,
                    created_at=row.created_at,
                )
            )
            target.commit()
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "caregiver_patients", "error": str(exc)})

    return stats


def _migrate_patient_medications(
    source: Session, target: Session, patient_id_map: dict[int, int], dry_run: bool
) -> tuple[MigrationStats, dict[int, int]]:
    """patient_medications 이전. 자연키가 없어(같은 약을 두 번 등록하는 것도 정상 케이스라
    유니크 제약을 걸 수 없음) "타깃 patient_id + medication_name + item_seq + start_date +
    source_raw_text"가 전부 같은 행이 이미 있으면 재실행으로 보고 건너뛰는 휴리스틱을 쓴다.
    완벽하진 않지만(진짜 같은 약을 두 번 등록한 경우와 재실행을 구분 못 할 수 있음),
    --dry-run으로 먼저 검토하는 것을 권장한다."""
    stats = MigrationStats()
    id_map: dict[int, int] = {}

    for row in source.exec(select(models.PatientMedication)).all():
        try:
            target_patient_id = patient_id_map.get(row.patient_id)
            if target_patient_id is None:
                stats.failed += 1
                stats.failed_rows.append(
                    {"source_id": row.id, "table": "patient_medications", "error": "patient 이전 실패로 연결 불가"}
                )
                continue

            if not dry_run:
                existing = target.exec(
                    select(models.PatientMedication)
                    .where(models.PatientMedication.patient_id == target_patient_id)
                    .where(models.PatientMedication.medication_name == row.medication_name)
                    .where(models.PatientMedication.item_seq == row.item_seq)
                    .where(models.PatientMedication.start_date == row.start_date)
                    .where(models.PatientMedication.source_raw_text == row.source_raw_text)
                ).first()
                if existing:
                    id_map[row.id] = existing.id
                    stats.skipped_existing += 1
                    continue

            new_row = models.PatientMedication(
                patient_id=target_patient_id,
                drug_id=row.drug_id,
                item_seq=row.item_seq,
                product_code=row.product_code,
                medication_name=row.medication_name,
                manufacturer_name=row.manufacturer_name,
                dosage_amount=row.dosage_amount,
                dosage_unit=row.dosage_unit,
                frequency_per_day=row.frequency_per_day,
                administration_route=row.administration_route,
                start_date=row.start_date,
                end_date=row.end_date,
                prescription_id=None,  # medical_records는 이 스크립트 범위 밖이라 연결 안 함
                source_type=row.source_type,
                source_raw_text=row.source_raw_text,
                verification_status=row.verification_status,
                is_active=row.is_active,
                created_at=row.created_at,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
            )

            if dry_run:
                stats.migrated += 1
                id_map[row.id] = -row.id
                continue

            target.add(new_row)
            target.commit()
            target.refresh(new_row)
            id_map[row.id] = new_row.id
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "patient_medications", "error": str(exc)})

    return stats, id_map


def _migrate_medication_schedules(
    source: Session,
    target: Session,
    patient_id_map: dict[int, int],
    patient_medication_id_map: dict[int, int],
    dry_run: bool,
) -> tuple[MigrationStats, dict[int, int]]:
    """medication_schedules 이전. patient_medication_id가 있는 행(신규 플로우)만 이
    스크립트가 확실히 추적할 수 있다 — patient_medication_id가 없는 과거 스타일 일정도
    함께 옮기되, 자연키가 없어 "타깃 patient_id + drug_name + time_slot"이 이미 있으면
    건너뛰는 휴리스틱을 쓴다."""
    stats = MigrationStats()
    id_map: dict[int, int] = {}

    for row in source.exec(select(models.MedicationSchedule)).all():
        try:
            target_patient_id = patient_id_map.get(row.patient_id)
            if target_patient_id is None:
                stats.failed += 1
                stats.failed_rows.append(
                    {"source_id": row.id, "table": "medication_schedules", "error": "patient 이전 실패로 연결 불가"}
                )
                continue

            target_patient_medication_id = None
            if row.patient_medication_id is not None:
                target_patient_medication_id = patient_medication_id_map.get(row.patient_medication_id)

            if not dry_run:
                existing = target.exec(
                    select(models.MedicationSchedule)
                    .where(models.MedicationSchedule.patient_id == target_patient_id)
                    .where(models.MedicationSchedule.drug_name == row.drug_name)
                    .where(models.MedicationSchedule.time_slot == row.time_slot)
                ).first()
                if existing:
                    id_map[row.id] = existing.id
                    stats.skipped_existing += 1
                    continue

            new_row = models.MedicationSchedule(
                patient_id=target_patient_id,
                drug_name=row.drug_name,
                time_slot=row.time_slot,
                dose_timing=row.dose_timing,
                caregiver_alert=row.caregiver_alert,
                memo=row.memo,
                active=row.active,
                created_at=row.created_at,
                patient_medication_id=target_patient_medication_id,
                meal_relation=row.meal_relation,
                instructions=row.instructions,
                timezone=row.timezone,
                days_of_week=row.days_of_week,
            )

            if dry_run:
                stats.migrated += 1
                id_map[row.id] = -row.id
                continue

            target.add(new_row)
            target.commit()
            target.refresh(new_row)
            id_map[row.id] = new_row.id
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "medication_schedules", "error": str(exc)})

    return stats, id_map


def _migrate_medication_records(
    source: Session,
    target: Session,
    patient_medication_id_map: dict[int, int],
    schedule_id_map: dict[int, int],
    dry_run: bool,
) -> MigrationStats:
    """medication_records 이전. 자연키: (타깃 patient_medication_id, scheduled_at, status)
    조합이 이미 있으면 건너뛴다."""
    stats = MigrationStats()

    for row in source.exec(select(models.MedicationRecord)).all():
        try:
            target_patient_medication_id = patient_medication_id_map.get(row.patient_medication_id)
            if target_patient_medication_id is None:
                stats.failed += 1
                stats.failed_rows.append(
                    {"source_id": row.id, "table": "medication_records", "error": "patient_medication 이전 실패로 연결 불가"}
                )
                continue

            target_schedule_id = None
            if row.schedule_id is not None:
                target_schedule_id = schedule_id_map.get(row.schedule_id)

            if not dry_run:
                existing = target.exec(
                    select(models.MedicationRecord)
                    .where(models.MedicationRecord.patient_medication_id == target_patient_medication_id)
                    .where(models.MedicationRecord.scheduled_at == row.scheduled_at)
                    .where(models.MedicationRecord.status == row.status)
                ).first()
                if existing:
                    stats.skipped_existing += 1
                    continue

            new_row = models.MedicationRecord(
                patient_medication_id=target_patient_medication_id,
                schedule_id=target_schedule_id,
                scheduled_at=row.scheduled_at,
                taken_at=row.taken_at,
                status=row.status,
                verification_method=row.verification_method,
                evidence_image_url=row.evidence_image_url,
                memo=row.memo,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

            if dry_run:
                stats.migrated += 1
                continue

            target.add(new_row)
            target.commit()
            stats.migrated += 1
        except Exception as exc:  # noqa: BLE001
            target.rollback()
            stats.failed += 1
            stats.failed_rows.append({"source_id": row.id, "table": "medication_records", "error": str(exc)})

    return stats


# ══════════════════════════════════════════
# 진입점
# ══════════════════════════════════════════
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-url", default=os.environ.get("SOURCE_DATABASE_URL"), help="기존 로컬 DB URL")
    parser.add_argument("--target-url", default=os.environ.get("TARGET_DATABASE_URL"), help="공통 개발 DB URL")
    parser.add_argument(
        "--source-pii-encryption-key", default=os.environ.get("SOURCE_PII_ENCRYPTION_KEY"),
        help="소스 환경의 PII_ENCRYPTION_KEY (name/phone 복호화용)",
    )
    parser.add_argument(
        "--source-pii-hash-secret", default=os.environ.get("SOURCE_PII_HASH_SECRET"),
        help="소스 환경의 PII_HASH_SECRET",
    )
    parser.add_argument(
        "--target-pii-encryption-key", default=os.environ.get("TARGET_PII_ENCRYPTION_KEY"),
        help="타깃 환경의 PII_ENCRYPTION_KEY (name/phone 재암호화용)",
    )
    parser.add_argument(
        "--target-pii-hash-secret", default=os.environ.get("TARGET_PII_HASH_SECRET"),
        help="타깃 환경의 PII_HASH_SECRET",
    )
    parser.add_argument("--dry-run", action="store_true", help="타깃에 아무것도 쓰지 않고 무엇을 할지만 출력")
    parser.add_argument(
        "--yes-i-have-a-backup", action="store_true",
        help="실제 실행(--dry-run 없이) 시 필수 — 타깃 DB를 미리 백업했다는 확인",
    )
    parser.add_argument(
        "--failed-log", default=None,
        help="실패한 행을 남길 로그 파일 경로 (기본값: migrate_local_data_failed_<timestamp>.json)",
    )
    args = parser.parse_args()

    if not args.source_url or not args.target_url:
        parser.error("--source-url/--target-url이 필요합니다 (또는 SOURCE_DATABASE_URL/TARGET_DATABASE_URL 환경변수)")
    for key_name in (
        "source_pii_encryption_key", "source_pii_hash_secret",
        "target_pii_encryption_key", "target_pii_hash_secret",
    ):
        if not getattr(args, key_name):
            parser.error(f"--{key_name.replace('_', '-')}가 필요합니다 (PII 재암호화를 위해 4개 키 모두 필수)")

    if not args.dry_run and not args.yes_i_have_a_backup:
        print(
            "❌ 실제 실행(--dry-run 없이)은 --yes-i-have-a-backup 없이는 거부됩니다.\n"
            "   먼저 타깃 DB를 백업한 뒤, 확인했다는 의미로 --yes-i-have-a-backup을 함께 주세요.\n"
            "   (이 스크립트는 타깃에 INSERT만 하고 기존 행은 건드리지 않지만, 안전을 위한 절차입니다.)"
        )
        return 1

    source_engine = create_engine(args.source_url)
    target_engine = create_engine(args.target_url)
    # 타깃에 테이블이 없으면(신규 공통 DB) 만들어준다 — 이미 있으면 그대로 둠.
    # [주의] 이건 create_all()이라 Alembic 마이그레이션을 대신하지 않는다 — 타깃 DB는
    # 이 스크립트 실행 전에 `alembic upgrade head`로 스키마를 맞춰두는 게 정석이다.
    SQLModel.metadata.create_all(target_engine)

    source_keys = PiiKeys(args.source_pii_encryption_key, args.source_pii_hash_secret)
    target_keys = PiiKeys(args.target_pii_encryption_key, args.target_pii_hash_secret)

    mode = "DRY-RUN (아무것도 쓰지 않음)" if args.dry_run else "실제 실행"
    print(f"=== 데이터 이전 시작 [{mode}] ===")
    print(f"source: {args.source_url}")
    print(f"target: {args.target_url}\n")

    all_failed: dict[str, list[dict]] = {}

    with Session(source_engine) as source, Session(target_engine) as target:
        print("1) caregivers")
        stats, caregiver_id_map = _migrate_caregivers(source, target, source_keys, target_keys, args.dry_run)
        stats.report("caregivers")
        all_failed["caregivers"] = stats.failed_rows

        print("2) patients")
        stats, patient_id_map = _migrate_patients(source, target, source_keys, target_keys, args.dry_run)
        stats.report("patients")
        all_failed["patients"] = stats.failed_rows

        print("3) caregiver_patients (연결)")
        stats = _migrate_caregiver_patients(source, target, caregiver_id_map, patient_id_map, args.dry_run)
        stats.report("caregiver_patients")
        all_failed["caregiver_patients"] = stats.failed_rows

        print("4) patient_medications")
        stats, patient_medication_id_map = _migrate_patient_medications(source, target, patient_id_map, args.dry_run)
        stats.report("patient_medications")
        all_failed["patient_medications"] = stats.failed_rows

        print("5) medication_schedules")
        stats, schedule_id_map = _migrate_medication_schedules(
            source, target, patient_id_map, patient_medication_id_map, args.dry_run
        )
        stats.report("medication_schedules")
        all_failed["medication_schedules"] = stats.failed_rows

        print("6) medication_records")
        stats = _migrate_medication_records(source, target, patient_medication_id_map, schedule_id_map, args.dry_run)
        stats.report("medication_records")
        all_failed["medication_records"] = stats.failed_rows

    failed_log_path = Path(args.failed_log) if args.failed_log else Path(
        f"migrate_local_data_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    _write_failed_log(failed_log_path, all_failed)

    print(f"\n=== 완료 [{mode}] ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
