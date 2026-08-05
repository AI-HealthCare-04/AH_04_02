"""
records_router.py — POST /records 백그라운드 drug-info 사전조회 테스트
(2026-08-05 신규, perf)

처방전 등록(POST /records) 응답 이후, 확인 화면(PrescriptionReview.tsx)이 약마다
GET /ocr/drug-info로 조회할 내용을 백그라운드에서 미리 조회해 캐시를 채워두는 기능의
회귀 테스트. _prefetch_drug_info()는 BackgroundTasks로 등록돼 응답이 이미 클라이언트로
전송된 뒤 실행되므로(ocr_router._drug_info_lock_for/diskcache와 마찬가지로 세션 의존이
없음), 이 파일은 (1) POST /records가 올바른 약 이름 목록으로 백그라운드 작업을
예약하는지, (2) 그 백그라운드 함수 자체가 개별 실패에도 안전하고 동시 실행 수를
제한하며 로그를 남기는지를 나눠서 검증한다.
"""
import logging
from unittest.mock import patch

import pytest
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Patient
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
    pt = Patient(password_hash="x")
    pt.name = "사전조회테스트환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _upload(client: TestClient, patient_id: int, token: str):
    return client.post(
        "/records",
        params={"patient_id": patient_id},
        files={"file": ("prescription.png", b"fake-prescription-bytes", "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )


class TestBackgroundPrefetchScheduling:
    """POST /records가 응답 생성 후 올바른 약 이름 목록으로 백그라운드 사전조회를
    예약하는지 — 실제 조회(drug_info)는 patch로 대체해 여기서는 "무엇을, 몇 번" 호출을
    예약했는지만 검증한다."""

    def test_prefetch_scheduled_with_deduped_nonempty_drug_names_matching_response(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("OCR_PROVIDER", "mock")
        pt = _make_patient(session)
        token = create_access_token(pt.id, "patient")

        calls = []
        with patch(
            "routers.records_router._prefetch_drug_info",
            side_effect=lambda record_id, drug_names: calls.append((record_id, drug_names)),
        ):
            r = _upload(client, pt.id, token)

        assert r.status_code == 200, r.text
        body = r.json()
        assert len(calls) == 1, "약이 있는 처방전이면 백그라운드 사전조회가 정확히 1번 예약돼야 한다"
        called_record_id, called_names = calls[0]
        assert called_record_id == body["record_id"]
        assert called_names == [m["drug_name"] for m in body["medications"]]
        assert called_names == list(dict.fromkeys(called_names)), "중복 제거가 안 됐다"
        assert all(called_names), "빈 문자열 약 이름이 섞여 있으면 안 된다"

    def test_no_prefetch_scheduled_when_no_drug_names_present(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """모든 항목의 drug_name이 빈 문자열(예: 수동 입력 초기 상태)이면 사전조회를
        아예 예약하지 않아야 한다 — 빈 문자열로 drug_info를 부르는 낭비를 막는다."""
        monkeypatch.setenv("OCR_PROVIDER", "mock")
        pt = _make_patient(session)
        token = create_access_token(pt.id, "patient")

        calls = []
        with (
            patch(
                "routers.records_router._prefetch_drug_info",
                side_effect=lambda record_id, drug_names: calls.append((record_id, drug_names)),
            ),
            patch("routers.records_router._build_record_response", return_value={
                "record_id": 1, "status": "review_required", "failure_reason": None,
                "created_at": "2026-08-05T00:00:00", "uploaded_by_name": None,
                "caregiver_review_status": None, "has_image": False,
                "medications": [{"id": 1, "drug_name": "", "drug_code": "", "dosage": "",
                                  "dose_amount": "", "frequency": "", "total_days": "",
                                  "diagnosis": "", "drug_class": "", "confidence": 0.0,
                                  "review_required": True, "field_flags": []}],
                "guide": None, "duplicate_drug_names": [],
            }),
        ):
            r = _upload(client, pt.id, token)

        assert r.status_code == 200, r.text
        assert calls == [], "약 이름이 전부 빈 문자열이면 백그라운드 사전조회를 예약하면 안 된다"


class TestPrefetchDrugInfoFunction:
    """_prefetch_drug_info() 자체의 동작 — 개별 약 실패 격리, 동시 실행 수 제한, 로그."""

    def test_one_drug_failing_does_not_stop_others_and_never_raises(self):
        from routers.records_router import _prefetch_drug_info

        calls = []

        def fake_drug_info(drug_name):
            calls.append(drug_name)
            if drug_name == "실패약":
                raise RuntimeError("정부 API/LLM 호출 실패")
            return {"drug_name": drug_name}

        with patch("routers.records_router.drug_info", side_effect=fake_drug_info):
            _prefetch_drug_info(123, ["실패약", "정상약1", "정상약2"])  # 예외 없이 끝나야 함

        assert sorted(calls) == sorted(["실패약", "정상약1", "정상약2"])

    def test_concurrency_is_capped_at_configured_max_workers(self):
        import threading
        import time

        from routers.records_router import _DRUG_INFO_PREFETCH_MAX_WORKERS, _prefetch_drug_info

        state = {"active": 0, "max_active": 0}
        state_lock = threading.Lock()

        def fake_drug_info(drug_name):
            with state_lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.05)
            with state_lock:
                state["active"] -= 1
            return {"drug_name": drug_name}

        drug_names = [f"약{i}" for i in range(10)]
        with patch("routers.records_router.drug_info", side_effect=fake_drug_info):
            _prefetch_drug_info(1, drug_names)

        assert state["max_active"] <= _DRUG_INFO_PREFETCH_MAX_WORKERS, (
            f"ThreadPoolExecutor max_workers={_DRUG_INFO_PREFETCH_MAX_WORKERS}를 넘는 "
            f"동시 실행({state['max_active']})은 외부 API를 무제한으로 때리는 것과 같다"
        )
        assert state["max_active"] > 1, "테스트 자체가 병렬 실행을 관찰하지 못하면 위 assert가 무의미하다"

    def test_logs_prefetch_start_and_completion(self, caplog: pytest.LogCaptureFixture):
        from routers.records_router import _prefetch_drug_info

        with patch("routers.records_router.drug_info", return_value={"drug_name": "로그테스트약"}):
            with caplog.at_level(logging.INFO, logger="routers.records_router"):
                _prefetch_drug_info(42, ["로그테스트약"])

        assert "사전조회 시작" in caplog.text
        assert "사전조회 완료" in caplog.text
        assert "42" in caplog.text
