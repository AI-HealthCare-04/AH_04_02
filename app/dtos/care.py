from datetime import date

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.models.users import Gender


class CareRelationCreateRequest(BaseModel):
    patient_id: int


class PatientSummaryResponse(BaseSerializerModel):
    id: int
    name: str
    gender: Gender
    birthday: date
