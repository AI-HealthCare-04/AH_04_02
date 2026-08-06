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
import asyncio
import logging
import threading
import time
from unittest.mock import AsyncMock, patch

import anyio
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

    def test_schedules_the_isolated_dispatch_wrapper_not_the_raw_function(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """[2026-08-05 추가, perf 회귀 수정] create_record가 background_tasks.add_task에
        _prefetch_drug_info를 직접 넘기지 않고 _dispatch_prefetch_drug_info(anyio 공유
        풀을 안 타는 async 래퍼)를 넘기는지 배선 자체를 확인한다 — 누군가 이 배선을
        되돌리면(원 함수를 직접 등록) 여기서 바로 잡힌다. _prefetch_drug_info만 patch하는
        위 테스트는 래퍼를 거치든 안 거치든 결국 원 함수가 호출되므로 이 배선 자체는
        구분해내지 못한다."""
        monkeypatch.setenv("OCR_PROVIDER", "mock")
        pt = _make_patient(session)
        token = create_access_token(pt.id, "patient")

        mock_dispatch = AsyncMock()
        with patch("routers.records_router._dispatch_prefetch_drug_info", mock_dispatch):
            r = _upload(client, pt.id, token)

        assert r.status_code == 200, r.text
        mock_dispatch.assert_called_once()
        called_record_id, called_names = mock_dispatch.call_args.args
        assert called_record_id == r.json()["record_id"]
        assert called_names == [m["drug_name"] for m in r.json()["medications"]]

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


class TestPrefetchDispatchIsolatedFromAnyioSharedPool:
    """[2026-08-05 추가, perf 회귀 수정] BackgroundTasks에 _prefetch_drug_info를 직접
    등록하면 Starlette이 anyio 공유 스레드풀(list_records/drug_info 등 모든 동기 def
    엔드포인트가 쓰는 그 풀, 기본 40개)로 실행한다 — 실측으로 확인된 문제(사전조회 여러
    건이 겹치면 이 풀이 소진되어 GET /records가 최대 26초까지 지연)를 막기 위해
    _dispatch_prefetch_drug_info(async 래퍼) + 전용 _prefetch_dispatch_executor로
    분리했다. 이 클래스는 그 분리가 실제로 유지되는지 검증한다."""

    def test_dispatch_wrapper_is_async_so_backgroundtasks_skips_anyio_threadpool(self):
        """Starlette의 BackgroundTask.__call__은 등록된 함수가 async면(is_async_callable)
        스레드풀을 거치지 않고 이벤트 루프에서 직접 await한다(starlette/background.py) —
        이 전제가 깨지면(누군가 async def를 없애면) 다시 anyio 공유 풀을 타게 된다."""
        from routers.records_router import _dispatch_prefetch_drug_info
        from starlette._utils import is_async_callable

        assert is_async_callable(_dispatch_prefetch_drug_info), (
            "_dispatch_prefetch_drug_info가 async def가 아니면 BackgroundTasks가 다시 "
            "anyio 공유 스레드풀로 실행한다 — 회귀"
        )

    def test_dispatch_does_not_borrow_anyio_shared_thread_limiter(self):
        """_dispatch_prefetch_drug_info 실행 중 anyio의 공유 스레드풀(list_records 등
        모든 동기 엔드포인트가 쓰는 바로 그 풀)에서 토큰을 빌리지 않는지 직접 확인한다 —
        전용 executor만 쓴다는 핵심 주장의 가장 직접적인 검증."""
        from routers.records_router import _dispatch_prefetch_drug_info

        block = threading.Event()
        release = threading.Event()

        def blocking_drug_info(name):
            release.set()
            block.wait(timeout=10)
            return {"drug_name": name}

        async def run():
            limiter = anyio.to_thread.current_default_thread_limiter()
            baseline_borrowed = limiter.borrowed_tokens
            with patch("routers.records_router.drug_info", side_effect=blocking_drug_info):
                task = asyncio.create_task(_dispatch_prefetch_drug_info(1, ["약1"]))
                for _ in range(100):
                    if release.is_set():
                        break
                    await asyncio.sleep(0.05)
                assert release.is_set(), "drug_info가 제한 시간 내에 실행되지 않았다"
                during_borrowed = limiter.borrowed_tokens
                block.set()
                await task
            return baseline_borrowed, during_borrowed

        baseline_borrowed, during_borrowed = asyncio.run(run())
        assert during_borrowed == baseline_borrowed, (
            "사전조회 디스패치가 anyio 공유 스레드풀에서 토큰을 빌리면 안 된다 — 빌렸다면 "
            "list_records 등 다른 동기 엔드포인트가 그만큼 대기하게 되는 회귀다"
        )

    def test_dispatch_never_delays_other_anyio_work_even_with_a_single_slot_pool(self):
        """가장 직접적인 재현: anyio 공유 풀을 극단적으로 1개로 줄여도(list_records 등
        "다른 동기 작업" 역할을 run_in_threadpool로 흉내낸다), 사전조회 디스패치가
        (drug_info가 멈춰 있는 동안에도) 그 하나뿐인 자리를 두고 경쟁하지 않아야 한다 —
        경쟁했다면 다른 작업은 사전조회가 끝날 때까지 기다렸을 것이다(실제로 26초까지
        재현된 문제)."""
        from routers.records_router import _dispatch_prefetch_drug_info
        from starlette.concurrency import run_in_threadpool

        block = threading.Event()

        def blocking_drug_info(name):
            block.wait(timeout=10)
            return {"drug_name": name}

        async def run():
            limiter = anyio.to_thread.current_default_thread_limiter()
            original_total = limiter.total_tokens
            limiter.total_tokens = 1
            try:
                with patch("routers.records_router.drug_info", side_effect=blocking_drug_info):
                    dispatch_task = asyncio.create_task(_dispatch_prefetch_drug_info(1, ["약1"]))
                    await asyncio.sleep(0.2)  # drug_info에서 멈춰 있는 상태를 만든다

                    t0 = time.perf_counter()
                    other_work_result = await run_in_threadpool(lambda: "list_records 대역")
                    elapsed = time.perf_counter() - t0

                    block.set()
                    await dispatch_task
            finally:
                limiter.total_tokens = original_total
            return other_work_result, elapsed

        result, elapsed = asyncio.run(run())
        assert result == "list_records 대역"
        assert elapsed < 1.0, (
            f"anyio 공유 풀이 1개뿐인 상태에서 다른 동기 작업이 {elapsed:.2f}초 걸렸다 — "
            "사전조회 디스패치가 그 풀을 다시 점유하게 된 회귀일 수 있다"
        )


class TestGetRecordsNotDelayedByPrefetchDispatch:
    """[2026-08-05 추가, perf 회귀 수정] 실제 재현: PR #164 배포 후 GET /records?patient_id=81이
    최대 26초까지 걸리던 문제 — 사전조회가 anyio 공유 스레드풀을 점유해서 벌어졌다
    (실제 uvicorn 서버로 재현·측정 완료). 전용 풀로 분리한 뒤에는 사전조회가 얼마나
    오래 걸리든(여기서는 아예 멈춰 있게 만듦) GET /records가 전혀 지연되면 안 된다."""

    def test_get_records_stays_fast_while_prefetch_dispatch_is_blocked(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("OCR_PROVIDER", "mock")
        pt = _make_patient(session)
        token = create_access_token(pt.id, "patient")
        headers = {"Authorization": f"Bearer {token}"}

        block = threading.Event()
        release = threading.Event()

        def blocking_drug_info(name):
            release.set()
            block.wait(timeout=10)
            return {"drug_name": name, "patient_summary": None}

        with patch("routers.records_router.drug_info", side_effect=blocking_drug_info):
            post_thread = threading.Thread(target=_upload, args=(client, pt.id, token))
            post_thread.start()
            try:
                assert release.wait(timeout=5), "사전조회(drug_info)가 제한 시간 내에 시작되지 않았다"

                t0 = time.perf_counter()
                r = client.get("/records", params={"patient_id": pt.id}, headers=headers)
                elapsed = time.perf_counter() - t0
            finally:
                block.set()
                post_thread.join(timeout=10)

        assert r.status_code == 200
        assert elapsed < 2.0, (
            f"사전조회가 진행 중(멈춰 있음)인데도 GET /records가 {elapsed:.2f}초 걸렸다 — "
            "anyio 공유 스레드풀을 다시 점유하게 된 회귀일 수 있다"
        )
