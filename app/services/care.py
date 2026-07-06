from fastapi.exceptions import HTTPException
from starlette import status
from tortoise.transactions import in_transaction

from app.models.users import User, UserRole
from app.repositories.care_relation_repository import CareRelationRepository
from app.repositories.user_repository import UserRepository


class CareRelationService:
    def __init__(self):
        self.repo = CareRelationRepository()
        self.user_repo = UserRepository()

    # ponytail: patient_id로 즉시 연결. Figma 목업은 전화번호 초대 + 환자 수락 단계를 거침 —
    # 환자 조회(전화번호) 엔드포인트와 초대/수락 플로우 필요해지면 이 메서드를 나눠야 함.
    async def link_patient(self, caregiver: User, patient_id: int) -> None:
        if caregiver.role == UserRole.MEDICATION_SUBJECT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="환자 계정은 다른 환자를 케어할 수 없습니다.")

        patient = await self.user_repo.get_user(patient_id)
        if not patient or patient.role != UserRole.MEDICATION_SUBJECT:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 환자를 찾을 수 없습니다.")

        if await self.repo.exists(medication_subject_id=patient.id, caregiver_id=caregiver.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 케어 중인 환자입니다.")

        async with in_transaction():
            await self.repo.create(
                medication_subject_id=patient.id, caregiver_id=caregiver.id, relation_type=caregiver.role
            )

    # ponytail: 즉시 hard delete. Figma 목업은 다른 승인된 보호자의 동의가 필요한
    # 해제 요청(해제요청중) 단계를 거침 — 다중 보호자 동의 로직 필요해지면 확장.
    async def unlink_patient(self, caregiver: User, patient_id: int) -> None:
        deleted = await self.repo.delete(medication_subject_id=patient_id, caregiver_id=caregiver.id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="연결된 내역이 없습니다.")

    async def list_my_patients(self, caregiver: User) -> list[User]:
        return await self.repo.list_patients_of_caregiver(caregiver.id)
