"""
chat_router.py — 추천 질문(GET /chat/questions) 동적 생성 테스트 (2026-07-19 추가)

팀 회의에서 "앱을 켤 때마다 같은 기본 질문이 뜬다"고 보고된 현상 — 실제로는 캐시 버그가
아니라 PRESET_QUESTIONS가 완전히 정적인 리스트라 생기는 당연한 결과였다(원인 조사 결과는
docs/status-report 참고). 환자가 실제 등록한 약 기반으로 질문을 생성하도록 바꾼 뒤,
(1) 등록 약 있음/OCR만 있음/둘 다 없음 세 갈래 폴백과 (2) 새로 patient_id를 받게 된
GET /chat/questions의 IDOR 보호, (3) POST /ask가 동적 question_id를 정상 해석하는지를
검증한다.

[2026-07-23 수정] "챗봇 고정질문 약품 맥락 분리"(어느 화면에서 들어왔는지에 따라 다른 약
이름을 쓰도록 한 수정) 이후, GET /chat/questions는 더 이상 자체적으로 "환자의 최근 약"을
DB에서 조회하지 않는다 — 호출부(Chat.tsx)가 넘겨준 drug_name 쿼리 파라미터만 그대로
템플릿에 채워 넣고, drug_name이 없으면 PRESET_QUESTIONS로 폴백한다. 예전엔 이 DB 조회
로직이 _build_dynamic_questions(patient_id, session) 안에 있었지만, 이제 그 책임은
_patient_registered_drug_names(patient_id, session)로 옮겨갔다(여전히 LLM 컨텍스트
구성에 쓰인다) — 세 갈래 폴백 테스트는 그 함수를 직접 검증하도록 옮겼다.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import routers.chat_router as chat_router
from core.auth import create_access_token
from core.database import get_session
from fastapi.testclient import TestClient
from main import app
from models import (
    Caregiver,
    CaregiverPatient,
    GuideResult,
    MedicalRecord,
    OcrResult,
    Patient,
    PatientMedication,
)
from routers.chat_router import (
    PRESET_QUESTIONS,
    _build_dynamic_questions,
    _build_patient_context,
    _patient_registered_drug_names,
)
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _install_mock_llm(monkeypatch: pytest.MonkeyPatch, answer: str) -> MagicMock:
    """_CHAT_LLM_AVAILABLE=True(실 LLM 사용 조건)를 흉내내고 ChatOpenAI를 가짜로 바꿔
    실제 호출 없이 호출 여부/호출 인자만 검증한다. 반환값으로 assert_(not_)called()."""
    import langchain_openai

    response = MagicMock()
    response.content = answer
    instance = MagicMock()
    instance.invoke.return_value = response
    chat_cls = MagicMock(return_value=instance)

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", chat_cls)
    monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", True)
    monkeypatch.setattr(
        chat_router, "_rag_settings",
        SimpleNamespace(OPENAI_MODEL="gpt-test", OPENAI_API_KEY="test-key"),
        raising=False,
    )
    return chat_cls


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _make_patient(session: Session, name: str = "환자A") -> Patient:
    pt = Patient(hashed_password="x")
    pt.name = name
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return pt


def _make_caregiver(session: Session, name: str = "보호자A") -> Caregiver:
    cg = Caregiver(hashed_password="x")
    cg.name = name
    session.add(cg)
    session.commit()
    session.refresh(cg)
    return cg


def _token(subject_id: int, role: str) -> str:
    return create_access_token(subject_id, role)


class TestBuildDynamicQuestions:
    """[2026-07-23 수정] 이 템플릿 채우기 자체는 이제 drug_name 문자열 하나만 받는
    순수 함수라 DB 조회 폴백과 무관하다 — 채워지는 값만 확인한다."""

    def test_fills_all_three_templates_with_given_drug_name(self):
        questions = _build_dynamic_questions("암로디핀정5밀리그램")
        assert len(questions) == 3
        assert all("암로디핀정5밀리그램" in q["text"] for q in questions)
        assert all("암로디핀정5밀리그램" in q["answer"] for q in questions)
        assert all(q["id"].startswith("dyn:") for q in questions)


class TestPatientRegisteredDrugNamesFallback:
    """[2026-07-23 이전엔 _build_dynamic_questions(patient_id, session)가 담당하던 세 갈래
    폴백(등록 약 우선 → 없으면 OCR → 둘 다 없으면 빈 목록) — 이제 이 책임은
    _patient_registered_drug_names로 옮겨갔고, 여전히 LLM 컨텍스트 구성에 쓰인다."""

    def test_no_registered_medication_returns_empty(self, session: Session):
        pt = _make_patient(session, "빈환자")
        assert _patient_registered_drug_names(pt.id, session) == []

    def test_registered_medication_is_returned(self, session: Session):
        pt = _make_patient(session, "약등록환자")
        session.add(
            PatientMedication(
                patient_id=pt.id,
                medication_name="암로디핀정5밀리그램",
                source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()

        assert _patient_registered_drug_names(pt.id, session) == ["암로디핀정5밀리그램"]

    def test_inactive_or_deleted_medication_is_ignored(self, session: Session):
        pt = _make_patient(session, "탈퇴약환자")
        session.add(
            PatientMedication(
                patient_id=pt.id,
                medication_name="비활성약",
                source_type="manual",
                verification_status="user_confirmed",
                is_active=False,
            )
        )
        session.commit()

        assert _patient_registered_drug_names(pt.id, session) == []  # 활성 등록 약이 없으니 빈 목록

    def test_no_patient_medication_falls_back_to_latest_ocr_drug_name(self, session: Session):
        pt = _make_patient(session, "OCR환자")
        record = MedicalRecord(patient_id=pt.id, image_path="x.jpg", status="completed")
        session.add(record)
        session.commit()
        session.refresh(record)
        session.add(
            OcrResult(
                record_id=record.id,
                drug_name="타이레놀정500mg",
                dosage="500mg",
                frequency="1일 3회",
                diagnosis="두통",
            )
        )
        session.commit()

        assert _patient_registered_drug_names(pt.id, session) == ["타이레놀정500mg"]


class TestPatientContextExposesRegisteredDrugDurRefs:
    """[2026-08-05 추가, 실제 배포 사고 재현] 환자가 이미 등록한 처방의 DUR 경고
    ([DUR 임부금기] 등)가 챗봇 프롬프트 텍스트에는 들어가지만, 화면 "참고 자료"에
    "식약처 DUR 데이터" 출처로는 안 뜨던 문제 — _build_patient_context()가 텍스트만
    반환하고 구조화된 refs는 버렸던 게 원인이었다(Langfuse trace
    a963db7359bc3f3dc119e8b77d7f138f, source_ref_count=0인데 dur_context_count=1)."""

    def test_pregnancy_dur_warning_is_returned_as_structured_ref(self, session: Session):
        pt = _make_patient(session, "durRefPat")
        record = MedicalRecord(patient_id=pt.id, image_path="x.jpg", status="completed")
        session.add(record)
        session.commit()
        session.refresh(record)
        session.add(
            GuideResult(
                record_id=record.id,
                medication_guide="[]",
                lifestyle_guide="{}",
                source_refs=json.dumps(
                    [
                        {
                            "drug_name": "자누비아정50밀리그램",
                            "dur_category": "임부금기",
                            "dur_detail": "태아 발육에 필수적인 콜레스테롤의 생합성 감소 가능성.",
                        }
                    ],
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()

        context_text, dur_refs = _build_patient_context(pt.id, session)

        assert "[DUR 임부금기] 자누비아정50밀리그램" in context_text
        assert dur_refs == [
            {
                "drug_name": "자누비아정50밀리그램",
                "dur_category": "임부금기",
                "dur_detail": "태아 발육에 필수적인 콜레스테롤의 생합성 감소 가능성.",
            }
        ]


class TestQuestionsEndpointAuth:
    def test_owner_caregiver_ok(self, client: TestClient, session: Session):
        cg = _make_caregiver(session, "qOwnerCg")
        pt = _make_patient(session, "qPatA")
        session.add(CaregiverPatient(caregiver_id=cg.id, patient_id=pt.id))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(cg.id, 'caregiver')}"}
        r = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_other_caregiver_403(self, client: TestClient, session: Session):
        cg_owner = _make_caregiver(session, "qOwnerCg2")
        cg_other = _make_caregiver(session, "qOtherCg")
        pt = _make_patient(session, "qPatB")
        session.add(CaregiverPatient(caregiver_id=cg_owner.id, patient_id=pt.id))
        session.commit()
        headers = {"Authorization": f"Bearer {_token(cg_other.id, 'caregiver')}"}
        r = client.get("/chat/questions", params={"patient_id": pt.id}, headers=headers)
        assert r.status_code == 403

    def test_no_auth_401(self, client: TestClient, session: Session):
        pt = _make_patient(session, "qPatC")
        r = client.get("/chat/questions", params={"patient_id": pt.id})
        assert r.status_code in (401, 403)


class TestAskWithDynamicQuestionId:
    def test_ask_resolves_dynamic_question_id(self, client: TestClient, session: Session):
        pt = _make_patient(session, "askDynPat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        # [2026-07-23 수정] drug_name은 이제 DB에서 자동으로 안 채워진다 — Chat.tsx가
        # 이 화면이 실제로 어느 약 맥락에서 열렸는지 쿼리로 넘겨줘야 동적 질문이 나온다.
        listed = client.get(
            "/chat/questions", params={"patient_id": pt.id, "drug_name": "메트포르민정500mg"}, headers=headers
        )
        dyn_id = listed.json()[0]["id"]
        assert dyn_id.startswith("dyn:")

        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": dyn_id}, headers=headers)
        assert r.status_code == 200
        assert "메트포르민정500mg" in r.json()["answer"]

    def test_ask_unrecognized_template_key_404s(self, client: TestClient, session: Session):
        """[2026-07-23 수정] question_id에 박힌 약 이름 자체는 더 이상 검증하지 않는다(맥락
        분리 설계상 의도된 것 — GET /chat/questions?drug_name=X도 X를 검증하지 않는 것과
        같은 원칙). 다만 템플릿 key(예: meal_timing/side_effect/interaction) 자체가 존재하지
        않으면 여전히 404여야 한다."""
        pt = _make_patient(session, "askUnknownPat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        r = client.post(
            "/chat/ask",
            json={"patient_id": pt.id, "question_id": "dyn:no_such_template_key:아무약"},
            headers=headers,
        )
        assert r.status_code == 404


class TestAskLlmGating:
    """버그1(/ask): preset/dynamic 고정 답변이 매칭되면 _CHAT_LLM_AVAILABLE이 True여도
    LLM을 호출하지 않고 고정 답변을 그대로 내보내야 한다. LLM은 freeform일 때만."""

    def test_preset_question_does_not_call_llm_even_when_available(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "이건 LLM 답변이면 안 됩니다")
        pt = _make_patient(session, "presetGatePat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": "q1"}, headers=headers)
        assert r.status_code == 200

        chat_cls.assert_not_called()
        body = r.json()
        assert body["answer_source"] == "preset"
        assert body["answer"] == PRESET_QUESTIONS[0]["answer"]

    def test_dynamic_question_does_not_call_llm_even_when_available(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "LLM 답변이면 안 됩니다")
        pt = _make_patient(session, "dynGatePat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}
        dyn_id = client.get(
            "/chat/questions", params={"patient_id": pt.id, "drug_name": "메트포르민정500mg"}, headers=headers
        ).json()[0]["id"]

        r = client.post("/chat/ask", json={"patient_id": pt.id, "question_id": dyn_id}, headers=headers)
        assert r.status_code == 200

        chat_cls.assert_not_called()
        body = r.json()
        assert body["answer_source"] == "preset"
        assert "메트포르민정500mg" in body["answer"]

    def test_freeform_question_calls_llm(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "자유질문에 대한 LLM 답변")
        pt = _make_patient(session, "freeformGatePat")
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        r = client.post(
            "/chat/ask", json={"patient_id": pt.id, "question": "이 앱은 뭐하는 앱이야?"}, headers=headers
        )
        assert r.status_code == 200

        chat_cls.assert_called()  # freeform은 여전히 LLM 호출(회귀 방지)
        body = r.json()
        assert body["answer_source"].startswith("llm")
        assert body["answer"] == "자유질문에 대한 LLM 답변"


class TestPatientContextIncludesRegisteredMeds:
    """버그2: 처방전 OCR 없이 '내 약 등록'(PatientMedication)만 한 환자도 그 약 이름이
    LLM 컨텍스트에 들어가야 한다(예전엔 _build_patient_context가 PatientMedication을
    아예 안 봐서 "등록된 처방전 정보가 없습니다"만 넘어갔다)."""

    def test_build_patient_context_includes_registered_medication_without_ocr(self, session: Session):
        pt = _make_patient(session, "ctxMedPat")
        session.add(
            PatientMedication(
                patient_id=pt.id, medication_name="로수바스타틴정10mg", source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()

        context, _dur_refs = _build_patient_context(pt.id, session)
        assert "로수바스타틴정10mg" in context
        assert context != "아직 등록된 처방전 정보가 없습니다."

    def test_freeform_passes_registered_drug_name_to_llm(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        chat_cls = _install_mock_llm(monkeypatch, "LLM 답변")
        pt = _make_patient(session, "ctxLlmPat")
        session.add(
            PatientMedication(
                patient_id=pt.id, medication_name="로수바스타틴정10mg", source_type="manual",
                verification_status="user_confirmed",
            )
        )
        session.commit()
        headers = {"Authorization": f"Bearer {_token(pt.id, 'patient')}"}

        r = client.post(
            "/chat/ask", json={"patient_id": pt.id, "question": "내가 먹는 약 알려줘"}, headers=headers
        )
        assert r.status_code == 200
        chat_cls.assert_called()

        # ChatOpenAI().invoke(messages, ...) 호출 인자에 등록 약 이름이 들어있는지 확인
        instance = chat_cls.return_value
        messages = instance.invoke.call_args.args[0]
        prompt_text = "\n".join(m["content"] for m in messages)
        assert "로수바스타틴정10mg" in prompt_text
