"""
chat_router.py — 담당: 김영혜 (Day6 계획)

schedule_v6 확정 방식: 자유 대화 아님. 고정 질문 3개를 누르면 미리 준비된 답변이 나갑니다.
지금은 "고정 답변"이지만, 나중에 실제 LLM(gpt-4o-mini) 연동 시
ask() 안의 PRESET_QUESTIONS 매칭 부분만 실제 호출로 바꿔 끼우면 됩니다.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models import ChatMessage, Patient

router = APIRouter(prefix="/chat", tags=["Chat"])

# TODO(김영혜): 실제 LLM 연동 시 이 목록 대신 gpt-4o-mini 호출 결과로 교체
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


@router.get("/questions")
def list_questions():
    """Chat.tsx의 추천 질문 버튼에 쓸 목록"""
    return [{"id": q["id"], "text": q["text"]} for q in PRESET_QUESTIONS]


class ChatAsk(BaseModel):
    patient_id: int
    question_id: str


@router.post("/ask")
def ask(payload: ChatAsk, session: Session = Depends(get_session)):
    match = next((q for q in PRESET_QUESTIONS if q["id"] == payload.question_id), None)
    if not match:
        raise HTTPException(404, "존재하지 않는 질문이에요")
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    msg = ChatMessage(
        patient_id=payload.patient_id,
        question_id=match["id"],
        question_text=match["text"],
        answer_text=match["answer"],
    )
    session.add(msg)
    session.commit()
    session.refresh(msg)

    return {"question": match["text"], "answer": match["answer"], "created_at": msg.created_at.isoformat()}


@router.get("/history")
def history(patient_id: int, session: Session = Depends(get_session)):
    """지난 대화 이력 (마이페이지 등에서 참고용으로 쓸 수 있음)"""
    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.patient_id == patient_id)
        .order_by(ChatMessage.created_at)
    ).all()
