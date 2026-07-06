from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.care import CareRelationCreateRequest, PatientSummaryResponse
from app.models.users import User
from app.services.care import CareRelationService

care_router = APIRouter(prefix="/care", tags=["care"])


@care_router.get("/patients", response_model=list[PatientSummaryResponse], status_code=status.HTTP_200_OK)
async def list_my_patients(
    user: Annotated[User, Depends(get_request_user)],
    care_service: Annotated[CareRelationService, Depends(CareRelationService)],
) -> Response:
    patients = await care_service.list_my_patients(user)
    return Response(
        [PatientSummaryResponse.model_validate(patient).model_dump() for patient in patients],
        status_code=status.HTTP_200_OK,
    )


@care_router.post("/patients", status_code=status.HTTP_201_CREATED)
async def link_patient(
    request: CareRelationCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    care_service: Annotated[CareRelationService, Depends(CareRelationService)],
) -> Response:
    await care_service.link_patient(user, request.patient_id)
    return Response(content={"detail": "환자가 연결되었습니다."}, status_code=status.HTTP_201_CREATED)


@care_router.delete("/patients/{patient_id}", status_code=status.HTTP_200_OK)
async def unlink_patient(
    patient_id: int,
    user: Annotated[User, Depends(get_request_user)],
    care_service: Annotated[CareRelationService, Depends(CareRelationService)],
) -> Response:
    await care_service.unlink_patient(user, patient_id)
    return Response(content={"detail": "연결이 해제되었습니다."}, status_code=status.HTTP_200_OK)
