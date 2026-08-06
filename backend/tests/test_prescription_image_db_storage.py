import asyncio
from io import BytesIO

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi import UploadFile
from fastapi.testclient import TestClient
from main import app
from models import MedicalRecordImage, Patient
from routers.ocr_router import run_ocr
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _make_patient(session: Session) -> Patient:
    patient = Patient(password_hash="x")
    patient.name = "처방전 이미지 테스트 환자"
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def _upload_mock_image(session: Session, patient_id: int, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    image_bytes = b"fake-prescription-image-bytes"
    upload = UploadFile(filename="prescription.png", file=BytesIO(image_bytes))
    record = asyncio.run(run_ocr(patient_id, upload, session))
    return record, image_bytes


def test_run_ocr_stores_original_image_in_database(
    session: Session, monkeypatch: pytest.MonkeyPatch
):
    patient = _make_patient(session)
    record, image_bytes = _upload_mock_image(session, patient.id, monkeypatch)

    stored = session.get(MedicalRecordImage, record.id)
    assert record.image_path == "database"
    assert stored is not None
    assert stored.content == image_bytes
    assert stored.content_type == "image/png"
    assert stored.byte_size == len(image_bytes)


def test_image_endpoint_serves_database_blob(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
):
    patient = _make_patient(session)
    record, image_bytes = _upload_mock_image(session, patient.id, monkeypatch)
    token = create_access_token(patient.id, "patient")

    response = client.get(
        f"/records/{record.id}/image",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.content == image_bytes
    assert response.headers["content-type"] == "image/png"


def test_deleting_record_removes_database_blob(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
):
    patient = _make_patient(session)
    record, _ = _upload_mock_image(session, patient.id, monkeypatch)
    record_id = record.id
    token = create_access_token(patient.id, "patient")

    response = client.delete(
        f"/records/{record_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert session.get(MedicalRecordImage, record_id) is None


def test_upload_rejects_image_larger_than_ten_megabytes(
    session: Session, monkeypatch: pytest.MonkeyPatch
):
    patient = _make_patient(session)
    upload = UploadFile(
        filename="too-large.jpg",
        file=BytesIO(b"x" * (10 * 1024 * 1024 + 1)),
    )

    with pytest.raises(Exception) as exc_info:
        asyncio.run(run_ocr(patient.id, upload, session))

    assert getattr(exc_info.value, "status_code", None) == 413
    assert session.get(MedicalRecordImage, 1) is None
