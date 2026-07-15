"""
scripts/purge_expired_accounts.py — 탈퇴 유예기간(30일) 지난 계정 개인정보 영구 삭제
(2026-07-15 추가, REQ-035)

실행:
    python scripts/purge_expired_accounts.py --dry-run       # 무엇을 지울지만 미리 확인
    python scripts/purge_expired_accounts.py --yes-i-am-sure  # 실제 삭제(둘 다 없으면 거부)

자동 실행되지 않는 수동 스크립트입니다(사용자 확인 — 서버 기동 시 자동 점검 대신 이
스크립트를 직접, 또는 팀이 원하는 주기로 cron 등에 등록해 실행). PrivacyPurgeAudit
(status="pending")인 행 중 scheduled_purge_at이 지난 계정을 찾아 개인정보 필드(이름·
전화번호·이메일·생년월일·비밀번호 해시 등)만 지운다 — Patient/Caregiver 행 자체나
medical_records/patient_medications 등 연관 데이터는 삭제하지 않는다(FK 참조가 끊기는
문제와 "임의로 데이터를 지우지 않는다"는 팀 방침 때문 — 개인정보만 비식별화).
완료되면 감사기록(PrivacyPurgeAudit)의 status를 completed로 남긴다(이 행 자체는 원래도
PII를 담지 않으므로 그대로 보존 — 삭제 증빙 역할).

로그인 자체는 이미 deactivated_at으로 막혀 있으므로, 이 스크립트를 늦게 돌리더라도
추가로 새는 보안 구멍은 없다 — 순수하게 "보존 의무 없는 개인정보"를 실제로 지우는
역할만 한다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import database  # noqa: E402
import models  # noqa: E402
from core.security import encrypt_pii  # noqa: E402

_PURGED_NAME_PLACEHOLDER = "(탈퇴 회원)"


def _scrub_patient(patient: models.Patient) -> None:
    # name_encrypted는 빈 문자열(Fernet 암호문 아님)로 두면 .name 프로퍼티가 나중에 이
    # 값을 복호화하려다 예외를 던진다 — 진짜 이름 대신 안전한 placeholder를 암호화해서 넣는다.
    patient.name_encrypted = encrypt_pii(_PURGED_NAME_PLACEHOLDER)
    patient.phone_encrypted = None
    patient.phone_hash = None
    patient.email = None
    patient.birth_date = None
    patient.hashed_password = None
    patient.note = None


def _scrub_caregiver(caregiver: models.Caregiver) -> None:
    caregiver.name_encrypted = encrypt_pii(_PURGED_NAME_PLACEHOLDER)
    caregiver.phone_encrypted = None
    caregiver.phone_hash = None
    caregiver.email = None
    caregiver.birth_date = None
    caregiver.hashed_password = None
    caregiver.org_name = None
    caregiver.org_type = None
    caregiver.business_reg_no = None
    caregiver.manager_name = None
    caregiver.manager_phone = None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="실제로 지우지 않고 무엇을 지울지만 출력")
    parser.add_argument(
        "--yes-i-am-sure",
        action="store_true",
        help="실제 삭제를 실행하려면 반드시 필요 (안전장치 — migrate_local_data.py의 "
        "--yes-i-have-a-backup과 동일한 취지, 없으면 실행 거부)",
    )
    args = parser.parse_args()

    # [2026-07-15 추가, PR #48 팀원 리뷰 반영 — MEDIUM] --dry-run 없이 실행하면 곧바로
    # 실제 삭제부터 되던 게 이 저장소의 다른 스크립트(migrate_local_data.py)와 반대로
    # "안전한 동작이 기본값이 아닌" 상태였다 — 이제 --dry-run도 --yes-i-am-sure도 없으면
    # 아무것도 하지 않고 거부한다.
    if not args.dry_run and not args.yes_i_am_sure:
        print("❌ 실제 삭제를 실행하려면 --yes-i-am-sure를 함께 주세요(안전장치).")
        print("   먼저 확인: python scripts/purge_expired_accounts.py --dry-run")
        print("   실제 실행: python scripts/purge_expired_accounts.py --yes-i-am-sure")
        sys.exit(1)

    now = datetime.now()
    with Session(database.engine) as session:
        due_audits = session.exec(
            select(models.PrivacyPurgeAudit)
            .where(models.PrivacyPurgeAudit.status == "pending")
            .where(models.PrivacyPurgeAudit.scheduled_purge_at <= now)
        ).all()

        if not due_audits:
            print("삭제 대상 없음 — 유예기간 지난 pending 탈퇴 계정이 없습니다.")
            return

        print(f"삭제 대상 {len(due_audits)}건 발견 (scheduled_purge_at <= {now.isoformat()})")

        for audit in due_audits:
            model = models.Patient if audit.subject_type == "patient" else models.Caregiver
            account = session.get(model, audit.subject_id)
            if not account:
                print(
                    f"  ⚠ {audit.subject_type}_id={audit.subject_id} 계정을 찾을 수 없음"
                    "(이미 삭제됨?) — 감사기록만 completed 처리"
                )
                if not args.dry_run:
                    audit.status = "completed"
                    audit.completed_at = now
                    session.add(audit)
                continue

            print(
                f"  - {audit.subject_type}_id={audit.subject_id} 개인정보 삭제"
                f"{'(dry-run)' if args.dry_run else ''}"
            )
            if args.dry_run:
                continue

            if audit.subject_type == "patient":
                _scrub_patient(account)
            else:
                _scrub_caregiver(account)
            session.add(account)

            audit.status = "completed"
            audit.completed_at = now
            session.add(audit)

        if args.dry_run:
            print("\n--dry-run이라 아무것도 지우지 않았습니다.")
            return

        session.commit()
        print(f"\n완료: {len(due_audits)}건 처리됨.")


if __name__ == "__main__":
    main()
