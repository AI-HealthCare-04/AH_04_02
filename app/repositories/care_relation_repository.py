from app.models.care import CareRelation
from app.models.users import User, UserRole


class CareRelationRepository:
    def __init__(self):
        self._model = CareRelation

    async def exists(self, medication_subject_id: int, caregiver_id: int) -> bool:
        return await self._model.filter(
            medication_subject_id=medication_subject_id, caregiver_id=caregiver_id
        ).exists()

    async def create(self, medication_subject_id: int, caregiver_id: int, relation_type: UserRole) -> CareRelation:
        return await self._model.create(
            medication_subject_id=medication_subject_id,
            caregiver_id=caregiver_id,
            relation_type=relation_type,
        )

    async def delete(self, medication_subject_id: int, caregiver_id: int) -> bool:
        deleted_count = await self._model.filter(
            medication_subject_id=medication_subject_id, caregiver_id=caregiver_id
        ).delete()
        return deleted_count > 0

    async def list_patients_of_caregiver(self, caregiver_id: int) -> list[User]:
        relations = await self._model.filter(caregiver_id=caregiver_id).prefetch_related("medication_subject")
        return [relation.medication_subject for relation in relations]

    async def list_caregivers_of_patient(self, medication_subject_id: int) -> list[User]:
        relations = await self._model.filter(medication_subject_id=medication_subject_id).prefetch_related("caregiver")
        return [relation.caregiver for relation in relations]
