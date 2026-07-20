"""
test_rag_cache.py — REQ-020 가이드 캐시 단위 테스트

테스트 대상: routers/rag_router.py의 캐시 헬퍼 + run_rag() 캐시 흐름
1. 첫 요청 → cached=False, DB에 GuideCache 저장
2. 같은 조합 재요청 → cached=True, _generate_via_rag 재호출 안 됨
3. 만료된 캐시 → cached=False, 재생성·재저장
4. 다른 약물 조합 → 별도 캐시 항목 (서로 다른 cache_key)
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from core.database import get_session
from main import app
from models import (
    Caregiver,
    CaregiverPatient,
    GuideCache,
    MedicalRecord,
    OcrResult,
    Patient,
)
from routers.rag_router import (
    GUIDE_DATA_VERSION,
    _lookup_cache,
    _make_cache_key,
    _save_cache,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

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
    def _override():
        return session

    app.dependency_overrides[get_session] = _override
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _setup_record(session: Session) -> tuple[Caregiver, Patient, MedicalRecord, list[OcrResult]]:
    cg = Caregiver(password_hash="x")
    cg.name = "보호자"
    session.add(cg)
    pt = Patient(password_hash="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(cg)
    session.refresh(pt)
    session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
    rec = MedicalRecord(patient_id=pt.id, image_path="t.jpg", status="pending")
    session.add(rec)
    session.commit()
    session.refresh(rec)
    items = [
        OcrResult(record_id=rec.id, drug_name="메트포르민정500mg", diagnosis="당뇨", confidence=0.9, review_required=False),
        OcrResult(record_id=rec.id, drug_name="암로디핀정5mg", diagnosis="고혈압", confidence=0.9, review_required=False),
    ]
    for item in items:
        session.add(item)
    session.commit()
    for item in items:
        session.refresh(item)
    return cg, pt, rec, items


# ── 캐시 키 생성 ──────────────────────────────────────────────────────────────

def test_make_cache_key_deterministic(session: Session):
    """같은 약물+진단 조합은 항상 동일한 키를 반환한다."""
    _, _, _, items = _setup_record(session)
    key1 = _make_cache_key(items, GUIDE_DATA_VERSION)
    key2 = _make_cache_key(items, GUIDE_DATA_VERSION)
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex


def test_make_cache_key_differs_by_drug(session: Session):
    """약물이 다르면 캐시 키도 달라야 한다."""
    _, _, rec, items = _setup_record(session)
    other = OcrResult(record_id=rec.id, drug_name="전혀다른약", diagnosis="당뇨", confidence=0.9, review_required=False)
    session.add(other)
    session.commit()
    session.refresh(other)
    key_orig = _make_cache_key(items, GUIDE_DATA_VERSION)
    key_other = _make_cache_key([other], GUIDE_DATA_VERSION)
    assert key_orig != key_other


def test_make_cache_key_differs_by_version(session: Session):
    """data_version이 다르면 캐시 키도 달라야 한다."""
    _, _, _, items = _setup_record(session)
    key_v1 = _make_cache_key(items, "v1.0")
    key_v2 = _make_cache_key(items, "v2.0")
    assert key_v1 != key_v2


# ── 캐시 헬퍼 단위 테스트 ─────────────────────────────────────────────────────

def test_lookup_cache_miss(session: Session):
    """캐시에 없으면 None 반환."""
    result = _lookup_cache("nonexistent-key", session)
    assert result is None


def test_save_and_lookup_cache(session: Session):
    """저장 후 조회하면 동일 엔트리 반환."""
    _, _, _, items = _setup_record(session)
    key = _make_cache_key(items, GUIDE_DATA_VERSION)
    mg = {"drugs": [{"drug_name": "메트포르민정500mg"}]}
    lg = {"diagnosis": "당뇨"}
    sr = [{"item_name": "메트포르민정500mg"}]

    expires_at = _save_cache(key, items, GUIDE_DATA_VERSION, mg, lg, sr, session)
    assert expires_at > datetime.now()

    entry = _lookup_cache(key, session)
    assert entry is not None
    stored = json.loads(entry.guide_result)
    assert stored["medication_guide"] == mg


def test_lookup_expired_cache_returns_none(session: Session):
    """만료된 캐시는 None 반환 (재생성 트리거)."""
    _, _, _, items = _setup_record(session)
    key = _make_cache_key(items, GUIDE_DATA_VERSION)
    # 이미 만료된 엔트리 직접 삽입
    expired = GuideCache(
        cache_key=key,
        diagnosis="당뇨",
        drug_names=json.dumps(["메트포르민정500mg"]),
        data_version=GUIDE_DATA_VERSION,
        guide_result=json.dumps({"medication_guide": {}, "lifestyle_guide": {}, "source_refs": []}),
        expires_at=datetime.now() - timedelta(seconds=1),
    )
    session.add(expired)
    session.commit()

    result = _lookup_cache(key, session)
    assert result is None


def test_save_cache_upsert(session: Session):
    """동일 키 재저장 시 기존 엔트리를 덮어쓴다 (중복 없음)."""
    _, _, _, items = _setup_record(session)
    key = _make_cache_key(items, GUIDE_DATA_VERSION)
    mg1 = {"v": 1}
    mg2 = {"v": 2}
    _save_cache(key, items, GUIDE_DATA_VERSION, mg1, {}, [], session)
    _save_cache(key, items, GUIDE_DATA_VERSION, mg2, {}, [], session)

    entries = session.exec(select(GuideCache).where(GuideCache.cache_key == key)).all()
    assert len(entries) == 1
    assert json.loads(entries[0].guide_result)["medication_guide"] == mg2


# ── run_rag() 통합 플로우 테스트 ──────────────────────────────────────────────

_FAKE_PAYLOAD = (
    {"drugs": [{"drug_name": "메트포르민정500mg"}]},
    {"diagnosis": "당뇨"},
    [],
)


def _run(coro):
    """asyncio.run() 래퍼 — pytest-asyncio 없이 async 함수 테스트."""
    return asyncio.run(coro)


def test_run_rag_first_call_not_cached(session: Session):
    """첫 요청 → cached=False, GuideCache에 엔트리 생성."""
    _, _, rec, _ = _setup_record(session)

    with patch("routers.rag_router._RAG_AVAILABLE", False), \
         patch("routers.rag_router._fake_guide_payload", return_value=_FAKE_PAYLOAD):
        from routers.rag_router import run_rag
        guide, from_cache, expires_at = _run(run_rag(rec.id, session))

    assert from_cache is False
    assert expires_at is not None and expires_at > datetime.now()
    entries = session.exec(select(GuideCache)).all()
    assert len(entries) == 1


def test_run_rag_second_call_cached(session: Session):
    """같은 조합 재요청 → cached=True, _fake_guide_payload 재호출 없음."""
    _, _, rec, _ = _setup_record(session)

    fake_fn = MagicMock(return_value=_FAKE_PAYLOAD)
    with patch("routers.rag_router._RAG_AVAILABLE", False), \
         patch("routers.rag_router._fake_guide_payload", fake_fn):
        from routers.rag_router import run_rag
        _run(run_rag(rec.id, session))          # 1st — miss
        guide, from_cache, _ = _run(run_rag(rec.id, session))  # 2nd — hit

    assert from_cache is True
    assert fake_fn.call_count == 1  # 재호출 없음


def test_run_rag_expired_cache_regenerates(session: Session):
    """만료 캐시 → cached=False, 재생성·재저장."""
    _, _, rec, items = _setup_record(session)
    key = _make_cache_key(items, GUIDE_DATA_VERSION)

    session.add(GuideCache(
        cache_key=key,
        drug_names=json.dumps([]),
        data_version=GUIDE_DATA_VERSION,
        guide_result=json.dumps({"medication_guide": {"old": True}, "lifestyle_guide": {}, "source_refs": []}),
        expires_at=datetime.now() - timedelta(seconds=1),
    ))
    session.commit()

    with patch("routers.rag_router._RAG_AVAILABLE", False), \
         patch("routers.rag_router._fake_guide_payload", return_value=_FAKE_PAYLOAD):
        from routers.rag_router import run_rag
        guide, from_cache, _ = _run(run_rag(rec.id, session))

    assert from_cache is False
    entry = session.exec(select(GuideCache).where(GuideCache.cache_key == key)).first()
    assert entry is not None
    assert entry.expires_at > datetime.now()


def test_run_rag_different_combination_separate_cache(session: Session):
    """약물 조합이 다르면 별도 캐시 엔트리가 생성된다."""
    cg, pt, rec, _ = _setup_record(session)

    rec2 = MedicalRecord(patient_id=pt.id, image_path="t2.jpg", status="pending")
    session.add(rec2)
    session.commit()
    session.refresh(rec2)
    item2 = OcrResult(record_id=rec2.id, drug_name="전혀다른약명", diagnosis="고혈압", confidence=0.9, review_required=False)
    session.add(item2)
    session.commit()

    with patch("routers.rag_router._RAG_AVAILABLE", False), \
         patch("routers.rag_router._fake_guide_payload", return_value=_FAKE_PAYLOAD):
        from routers.rag_router import run_rag
        _, from_cache1, _ = _run(run_rag(rec.id, session))
        _, from_cache2, _ = _run(run_rag(rec2.id, session))

    assert from_cache1 is False
    assert from_cache2 is False
    entries = session.exec(select(GuideCache)).all()
    assert len(entries) == 2
    assert entries[0].cache_key != entries[1].cache_key