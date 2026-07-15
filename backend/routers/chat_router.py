"""
chat_router.py — 담당: 김영혜

[7/8] 고정 질문 3개는 그대로 버튼으로 유지하되, 답변은 하드코딩이 아니라 **그 환자의
최근 처방전(OcrResult/GuideResult)을 참고해 GPT가 실제로 생성**하도록 바꿨습니다.
[7/10] CHAT_PROVIDER=real이 실제로 동작 확인된 뒤 — 고정 질문 3개 제한을 풀고
자유 텍스트 질문(question)도 같은 방식(환자 컨텍스트 + GPT)으로 답변하게 확장했습니다.
[7/10] 서비스 메뉴 안내(MENU_MAP) 추가 — "OO 하려면 어디로 가야 하나요?" 같은 질문에
해당 화면 경로를 안내할 수 있도록, 환자별 컨텍스트와 별개로 항상 포함되는 고정 정보를
프롬프트에 추가했습니다.

CHAT_PROVIDER=real (OCR_PROVIDER/RAG_PROVIDER와 동일 컨벤션)을 .env에 켜야 LLM을
시도합니다. 기본값(미설정)이거나, rag 의존성이 없거나, LLM 호출이 실패하면
고정 질문은 PRESET_QUESTIONS 답변으로, 자유 질문은 "지금은 어렵다"는 안내로 조용히
폴백합니다 — 챗봇 자체가 죽는 것보단 뭐라도 답이 나가는 게 낫다는 판단.

[7/14] POST /ask, GET /history가 patient_id를 검증 없이 그대로 신뢰하던 IDOR을
monitoring_router.py/care_router.py와 동일한 `get_current_actor`/
`require_actor_patient_access` 패턴으로 막았습니다(issue #21 잔여 범위).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from fastapi import APIRouter, Depends, HTTPException
from models import ChatMessage, GuideResult, MedicalRecord, NotificationSetting, OcrResult, Patient
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter(prefix="/chat", tags=["Chat"])

PRESET_QUESTIONS = [
    {
        "id": "q1",
        "text": "이 약 식사 전에 먹어도 되나요?",
        "answer": "약마다 다릅니다. 대부분의 혈압·당뇨약은 식후 복용이 원칙이며, 공복에 드시면 속이 불편할 수 있어요. 처방전에 표시된 복용법을 꼭 확인해 주세요.",
    },
    {
        "id": "q2",
        "text": "혈압약과 함께 먹어도 되나요?",
        "answer": "대부분의 경우 함께 복용해도 안전하지만, 약 조합에 따라 주의가 필요한 경우도 있어요. 정확한 상호작용은 처방하신 의사나 약사에게 확인하시는 게 가장 안전해요.",
    },
    {
        "id": "q3",
        "text": "부작용이 있으면 어떻게 하나요?",
        "answer": "어지러움, 발진, 심한 속쓰림 등 평소와 다른 증상이 나타나면 복용을 멈추고 가까운 병원이나 약국에 문의해 주세요. 증상이 심하면 바로 응급실을 방문하세요.",
    },
]

CHAT_SYSTEM_PROMPT = """\
당신은 고령 만성질환 환자와 보호자를 위한 복약 상담 챗봇입니다.

"본태성 고혈압이 뭐야?", "이 약은 어떤 효능이 있어?"처럼 질병명·약효분류 등에 대한
일반적인 의학 상식을 묻는 질문에는, 당신이 원래 알고 있는 지식으로 쉽게 설명해도 됩니다.
다만 "이 약을 먹어도 되나요", "부작용이 있나요"처럼 이 환자 개인에게 적용되는 판단은
반드시 아래 [환자 정보]에 있는 내용만 근거로 답하세요 — 거기 없는 내용을 이 환자에게
해당되는 것처럼 지어내지 마세요. 개인별 판단에 확신이 없으면 모른다고 솔직히 말하고,
반드시 의사나 약사와 상담하도록 안내하세요. 쉬운 말로, 고령자도 이해할 수 있게 2~4문장
이내로 짧게 답하세요.

[메뉴 안내]에 있는 화면 목록은 환자 개인 정보가 아니라 서비스 자체의 고정된 안내이니,
"OO 하려면 어디로 가야 하나요?" 같은 질문에는 이 목록만 근거로 화면 이름을 안내해도 됩니다
(예: "복약 일정은 하단의 '일정' 메뉴에서 확인하실 수 있어요"). [메뉴 안내]에 없는 기능을
지어내지는 마세요.

[2026-07-14 추가] 답변 문장 안에 "출처:", "(식약처 ...)", "(대한OO학회 ...)" 같은 출처·자료명은
언급하지 마세요 — 출처는 복약 가이드 화면에 별도로 표시되므로, 챗봇 답변은 내용 자체만
전달하면 됩니다.
"""

# [7/10 추가] 서비스 메뉴 지도 — "OO 어디서 해요?" 질문에 답하기 위한 고정 정보.
# 환자별 컨텍스트(_build_patient_context)와 달리 모든 대화에 항상 포함된다.
# frontend/src/App.tsx의 라우트와 동기화 — 화면이 추가/삭제되면 여기도 같이 갱신할 것.
MENU_MAP: list[dict[str, str]] = [
    {"name": "처방전 등록", "path": "/upload", "desc": "처방전 사진을 찍거나 올려서 새로 등록"},
    {"name": "처방전 기록", "path": "/records", "desc": "지금까지 등록한 처방전 목록 확인"},
    {"name": "복약 지도", "path": "/records/:recordId/guide", "desc": "등록한 처방전의 복약·생활습관 안내(이 화면)"},
    {"name": "복약 일정", "path": "/schedule", "desc": "하루 복용 시간표 확인 및 복용 체크"},
    {"name": "알림 설정", "path": "/notification", "desc": "복약 알림 켜고 끄기"},
    {"name": "복약 대시보드", "path": "/dashboard", "desc": "오늘의 복약 현황 요약"},
    {"name": "마이페이지", "path": "/mypage", "desc": "내 정보·계정 설정"},
    {"name": "환자 관리", "path": "/patients", "desc": "(보호자용) 돌보는 환자 등록·관리"},
    {"name": "보호자 연결", "path": "/connect", "desc": "환자-보호자 연결/연결 해제"},
    {"name": "모니터링", "path": "/monitoring", "desc": "(보호자용) 환자의 복약 현황 확인"},
    {"name": "돌봄 교육자료", "path": "/care-education", "desc": "보호자를 위한 돌봄 안내 자료"},
]


def _menu_map_text() -> str:
    return "\n".join(f"- {m['name']}({m['path']}): {m['desc']}" for m in MENU_MAP)

# CHAT_PROVIDER=real일 때만 실제 LLM을 시도한다 (OCR_PROVIDER/RAG_PROVIDER와 동일 패턴).
# 기본값은 항상 PRESET_QUESTIONS 고정 답변 — 의존성 유무만으로 동작이 바뀌지 않는다.
_CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "stub")

_CHAT_LLM_AVAILABLE = False
if _CHAT_PROVIDER == "real":
    # rag/의 OpenAI 설정(.env의 OPENAI_API_KEY/OPENAI_MODEL)과 langchain-openai를
    # 재사용한다 — 키를 backend에 따로 둘 필요 없이 한 곳(rag/.env)만 관리하면 됨.
    _RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
    if _RAG_DIR.is_dir() and str(_RAG_DIR) not in sys.path:
        sys.path.insert(0, str(_RAG_DIR))

    try:
        from langchain_openai import ChatOpenAI  # noqa: F401 — 임포트 가능 여부만 확인(실사용은 지연 임포트)
        from rag.config import settings as _rag_settings

        _CHAT_LLM_AVAILABLE = bool(_rag_settings.OPENAI_API_KEY)
    except Exception:  # noqa: BLE001 — 의존성 미설치/키 없음 등 어떤 이유로든 실패하면 폴백
        _CHAT_LLM_AVAILABLE = False


def _summarize_ocr_items(ocr_items: list[OcrResult]) -> list[str]:
    if not ocr_items:
        return []
    lines = []
    drugs = ", ".join(f"{item.drug_name}({item.dosage or '용량 미상'}, {item.frequency or '복용법 미상'})" for item in ocr_items)
    lines.append(f"복용 중인 약: {drugs}")
    if ocr_items[0].diagnosis:
        lines.append(f"진단명: {ocr_items[0].diagnosis}")
    low_confidence = [item.drug_name for item in ocr_items if item.review_required]
    if low_confidence:
        lines.append(f"인식 신뢰도가 낮아 보호자 확인이 필요한 약: {', '.join(low_confidence)}")
    return lines


def _summarize_medication_guide(medication_guide_json: str) -> list[str]:
    """RAG_PROVIDER 설정에 따라 모양이 다를 수 있어(스텁 vs 실제 파이프라인) 방어적으로 읽는다.

    [2026-07-14] precautions(주의사항 목록)가 medication_guide 텍스트와 별개의 구조화
    필드인데 지금까지 빠져 있었다 — "부작용 있으면 어떻게 하나요?" 같은 질문에 챗봇이
    반드시 참고해야 할 정보라 함께 넣는다.
    """
    try:
        medication_guide = json.loads(medication_guide_json)
        drugs = medication_guide.get("drugs", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []

    lines = []
    for drug in drugs:
        drug_name = drug.get("drug_name", "약")
        text = drug.get("medication_guide") or drug.get("caution")
        if text:
            lines.append(f"[{drug_name} 복약 안내] {text}")
        precautions = drug.get("precautions") or []
        if precautions:
            lines.append(f"[{drug_name} 주의사항] " + " / ".join(precautions))
    return lines


def _summarize_source_refs(source_refs_json: str) -> list[str]:
    """[2026-07-14 추가] DUR(의약품안전사용서비스) 병용금기/노인주의/연령금기/임부금기 경고를
    챗봇 컨텍스트에 추가한다. 지금까지 source_refs(DUR 포함)가 통째로 챗봇 컨텍스트에서
    빠져 있어, "부작용 있으면?" 같은 질문에 DUR 데이터가 전혀 반영되지 않는 문제가 있었다
    (복약가이드 화면에는 표시되지만 챗봇은 못 보는 상태). 의약품·생활지침 인용은 이미
    medication_guide/lifestyle_guide 텍스트에 녹아 있으므로 여기서는 DUR만 추가한다.
    """
    try:
        refs = json.loads(source_refs_json)
    except (json.JSONDecodeError, TypeError):
        return []

    lines = []
    for ref in refs:
        if ref.get("mixture_item_name"):
            content = f" ({ref['prohbt_content']})" if ref.get("prohbt_content") else ""
            lines.append(f"[DUR 병용금기] {ref.get('drug_name', '약')}은(는) {ref['mixture_item_name']}와 병용금기{content}")
        elif ref.get("dur_category"):
            detail = f": {ref['dur_detail']}" if ref.get("dur_detail") else ""
            extra = f" ({ref['dur_extra']})" if ref.get("dur_extra") else ""
            lines.append(f"[DUR {ref['dur_category']}] {ref.get('drug_name', '약')}{extra}{detail}")
    return lines


def _summarize_lifestyle_guide(lifestyle_guide_json: str) -> list[str]:
    """마찬가지로 스텁(diet/exercise 구조) vs 실제 파이프라인(guides 리스트) 두 모양 다 처리."""
    try:
        lifestyle_guide = json.loads(lifestyle_guide_json)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []

    if lifestyle_guide.get("guides"):
        return ["[생활습관 안내] " + " ".join(lifestyle_guide["guides"])]

    lines = []
    diet = lifestyle_guide.get("diet") or {}
    exercise = lifestyle_guide.get("exercise") or {}
    if diet.get("avoid"):
        lines.append("[생활습관 안내] 피해야 할 음식: " + ", ".join(diet["avoid"]))
    if exercise:
        lines.append(f"운동 권장: {exercise.get('type', '')} {exercise.get('duration', '')}".strip())
    return lines


def _build_patient_context(patient_id: int, session: Session) -> str:
    """환자의 가장 최근 처방전(OcrResult/GuideResult)을 텍스트로 요약합니다."""
    record = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).first()
    if not record:
        return "아직 등록된 처방전 정보가 없습니다."

    ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
    lines = _summarize_ocr_items(ocr_items)

    guide = session.exec(
        select(GuideResult).where(GuideResult.record_id == record.id).order_by(GuideResult.id.desc())
    ).first()
    if guide:
        lines.extend(_summarize_medication_guide(guide.medication_guide))
        lines.extend(_summarize_lifestyle_guide(guide.lifestyle_guide))
        lines.extend(_summarize_source_refs(guide.source_refs))

    return "\n".join(lines) if lines else "아직 등록된 처방전 정보가 없습니다."


def _generate_llm_answer(question_text: str, context_text: str, bot_name: str) -> str:
    from langchain_openai import ChatOpenAI
    from rag.config import settings as rag_settings

    chat = ChatOpenAI(model=rag_settings.OPENAI_MODEL, api_key=rag_settings.OPENAI_API_KEY, temperature=0.4)
    response = chat.invoke(
        [
            {"role": "system", "content": f"당신의 이름은 '{bot_name}'입니다. 이름을 물어보면 이렇게 답하세요.\n\n{CHAT_SYSTEM_PROMPT}"},
            {
                "role": "user",
                "content": (
                    f"[메뉴 안내]\n{_menu_map_text()}\n\n"
                    f"[환자 정보]\n{context_text}\n\n[질문]\n{question_text}"
                ),
            },
        ]
    )
    return response.content.strip()


@router.get("/questions")
def list_questions():
    """Chat.tsx의 추천 질문 버튼에 쓸 목록"""
    return [{"id": q["id"], "text": q["text"]} for q in PRESET_QUESTIONS]


class ChatAsk(BaseModel):
    patient_id: int
    question_id: str | None = None  # 고정 질문 버튼 (q1/q2/q3)
    question: str | None = None  # [7/10 추가] 자유 텍스트 질문 — 입력창에서 직접 타이핑한 경우


@router.post("/ask")
def ask(payload: ChatAsk, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)):
    """고정 질문(question_id) 또는 자유 텍스트(question) 중 하나로 묻는다.
    CHAT_PROVIDER=real이면 그 환자의 최근 처방전을 참고해 GPT가 답변을 생성하고,
    아니거나 실패하면 고정 질문은 PRESET_QUESTIONS 답변으로, 자유 질문은 안내 문구로 나간다.
    """
    require_actor_patient_access(payload.patient_id, actor, session)
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    if payload.question_id:
        match = next((q for q in PRESET_QUESTIONS if q["id"] == payload.question_id), None)
        if not match:
            raise HTTPException(404, "존재하지 않는 질문이에요")
        question_id, question_text = match["id"], match["text"]
        fallback_answer, fallback_source = match["answer"], "preset"
    elif payload.question and payload.question.strip():
        question_id, question_text = "freeform", payload.question.strip()
        fallback_answer = "죄송해요, 지금은 이 질문에 실시간으로 답변드리기 어려워요. 담당 의사나 약사에게 확인해주세요."
        fallback_source = "unsupported"
    else:
        raise HTTPException(422, "question_id 또는 question 중 하나는 필요해요")

    answer_text, answer_source = fallback_answer, fallback_source

    if _CHAT_LLM_AVAILABLE:
        try:
            context_text = _build_patient_context(payload.patient_id, session)
            setting = session.get(NotificationSetting, payload.patient_id)
            bot_name = setting.chatbot_name if setting else "약콩이"
            answer_text = _generate_llm_answer(question_text, context_text, bot_name)
            answer_source = f"llm ({_rag_settings.OPENAI_MODEL})"
        except Exception as exc:  # noqa: BLE001 — LLM 실패해도 챗봇 자체는 응답해야 함
            answer_text, answer_source = fallback_answer, f"{fallback_source}_fallback ({type(exc).__name__})"

    msg = ChatMessage(
        patient_id=payload.patient_id,
        question_id=question_id,
        question_text=question_text,
        answer_text=answer_text,
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)

    return {
        "question": question_text,
        "answer": answer_text,
        "answer_source": answer_source,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("/history")
def history(patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)):
    """지난 대화 이력 (마이페이지 등에서 참고용으로 쓸 수 있음)"""
    require_actor_patient_access(patient_id, actor, session)
    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.patient_id == patient_id)
        .order_by(ChatMessage.created_at)
    ).all()
