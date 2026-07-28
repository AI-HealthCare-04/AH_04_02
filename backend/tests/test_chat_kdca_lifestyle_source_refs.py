"""test_chat_kdca_lifestyle_source_refs.py — 챗봇이 생활습관 질문에 질병관리청
국가건강정보포털 문서로 답할 때, source_refs가 그 출처를 실제로 실어 나르는지 검증
(2026-07-24 신규). 기존 TestSourceRefs(test_chat_ask_stream.py)는 의약품(item_name) 인용
모양만 커버해서, KDCA 인용 모양(disease/source)의 회귀는 잡아내지 못했다."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import routers.chat_router as chat_router
from conftest import make_test_engine
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import Patient
from sqlmodel import Session


def _install_mock_llm(monkeypatch, answer: str):
    import langchain_openai

    instance = MagicMock()

    async def _astream(messages, config=None):
        for piece in answer.split():
            chunk = MagicMock()
            chunk.content = piece + " "
            yield chunk

    instance.astream = _astream
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", MagicMock(return_value=instance))
    monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", True)
    monkeypatch.setattr(
        chat_router, "_rag_settings",
        SimpleNamespace(OPENAI_MODEL="gpt-test", OPENAI_API_KEY="test-key"),
        raising=False,
    )


@pytest.fixture(name="session")
def session_fixture():
    engine = make_test_engine()
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def _parse_sse(body: str):
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_lifestyle_freeform_question_surfaces_kdca_source_ref(client: TestClient, session: Session, monkeypatch):
    """실제 유저 시나리오: 자유 텍스트로 생활습관(음식) 질문 -> 질병관리청 문서가 RAG로
    검색됨 -> /ask/stream의 done 이벤트 source_refs에 질병관리청 출처가 실려오는지 확인."""
    pt = Patient(hashed_password="x")
    pt.name = "환자"
    session.add(pt)
    session.commit()
    session.refresh(pt)

    _install_mock_llm(monkeypatch, "저염식 위주로 식사하시는 게 좋아요.")

    kdca_doc = SimpleNamespace(
        page_content="채소와 저염식 위주로 드세요.",
        metadata={
            "doc_type": "kdca_health_info",
            "title": "고혈압",
            "section_name": "식이요법",
            "source": "질병관리청 국가건강정보포털",
            "source_url": "http://x",
        },
    )
    monkeypatch.setattr("rag.vectorstore.similarity_search", lambda *a, **k: [kdca_doc])

    headers = {"Authorization": f"Bearer {create_access_token(pt.id, 'patient')}"}
    r = client.post(
        "/chat/ask/stream",
        json={"patient_id": pt.id, "question": "고혈압에 좋은 음식이 뭐야?"},
        headers=headers,
    )
    assert r.status_code == 200
    done = next(e for e in _parse_sse(r.text) if e.get("done"))
    assert done["source_refs"] == [{"disease": "고혈압", "source": "질병관리청 국가건강정보포털"}]
