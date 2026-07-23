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

import asyncio
import json
import os
import re
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.database import get_session
from core.dependencies import Actor, get_current_actor, require_actor_patient_access
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from models import (
    ChatMessage,
    GuideResult,
    MedicalRecord,
    NotificationSetting,
    OcrResult,
    Patient,
    PatientMedication,
)
from pydantic import BaseModel
from services.langfuse_tracing import (
    flush_langfuse,
    get_langchain_callback_handler,
    mask_for_langfuse,
    now_ms,
    optional_observation,
    update_observation,
)
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

# [2026-07-19 추가] PRESET_QUESTIONS는 완전히 고정된 값이라, 앱을 켤 때마다 누구에게나
# 항상 똑같은 질문(특히 q1 "이 약 식사 전에 먹어도 되나요?")이 뜬다는 게 팀 회의에서
# "매번 같은 기본 질문이 뜨는 버그처럼 보인다"고 지적됨 — 실제로는 캐시/상태 버그가
# 아니라 이 리스트 자체가 정적이라 생기는 현상이었다(docs/status-report 참고). 환자가
# 실제로 등록한 약 이름을 넣어 질문을 생성하도록 바꿔서, 매번 똑같이 느껴지는 문제와
# "이 챗봇이 내 약을 실제로 아는지" 둘 다 개선한다.
_DYNAMIC_QUESTION_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "meal_timing",
        "{drug} 식사 전후 언제 먹어야 하나요?",
        "{drug}은 약마다 복용 시점이 달라요. 처방전에 표시된 복용법을 꼭 확인하시고, 헷갈리면 처방하신 의사나 약사에게 확인해 주세요.",
    ),
    (
        "side_effect",
        "{drug} 복용 중 부작용이 있으면 어떻게 하나요?",
        "{drug} 복용 중 어지러움, 발진, 심한 속쓰림처럼 평소와 다른 증상이 나타나면 복용을 멈추고 가까운 병원이나 약국에 문의해 주세요. 증상이 심하면 바로 응급실을 방문하세요.",
    ),
    (
        "interaction",
        "{drug}을 다른 약과 같이 먹어도 되나요?",
        "{drug}을 다른 약과 함께 드실 때는 조합에 따라 주의가 필요할 수 있어요. 정확한 상호작용은 처방하신 의사나 약사에게 확인하시는 게 가장 안전해요.",
    ),
]


def _patient_registered_drug_names(patient_id: int, session: Session, limit: int = 3) -> list[str]:
    """환자가 실제로 등록·확정한 약 이름 — '내 약 등록'(PatientMedication, 사용자 확정값)을
    우선하고, 없으면 최근 처방전 OCR 결과로 폴백한다(_latest_ocr_drug_names는 아래 정의됨,
    이 함수보다 먼저 호출되는 곳이 없어 순서 문제 없음)."""
    meds = session.exec(
        select(PatientMedication)
        .where(PatientMedication.patient_id == patient_id)
        .where(PatientMedication.is_active == True)  # noqa: E712
        .where(PatientMedication.deleted_at.is_(None))
        .order_by(PatientMedication.created_at.desc())
    ).all()
    names = [m.medication_name for m in meds if m.medication_name]
    if names:
        return names[:limit]
    return _latest_ocr_drug_names(patient_id, session)[:limit]


def _build_dynamic_questions(drug_name: str) -> list[dict]:
    """[2026-07-23 수정] 예전엔 patient_id로 "환자의 최근 약"을 자체 조회해서 항상 그
    약 이름으로 질문을 만들었다 — 그래서 어느 약 상세화면에서 챗봇에 들어가든, 심지어
    우측 하단 플로팅 버튼으로 들어가도 늘 같은(가장 최근 등록된) 약 이름이 붙었다.
    이제는 호출부(list_questions)가 이 화면이 실제로 어떤 약 맥락에서 열렸는지 넘겨준
    drug_name만 그대로 채워 넣는다 — 맥락이 없으면 애초에 이 함수를 호출하지 않는다."""
    return [
        {
            "id": f"dyn:{key}:{drug_name}",
            "text": text_tpl.format(drug=drug_name),
            "answer": answer_tpl.format(drug=drug_name),
        }
        for key, text_tpl, answer_tpl in _DYNAMIC_QUESTION_TEMPLATES
    ]


def _resolve_dynamic_question_by_id(question_id: str) -> dict | None:
    """question_id 형식 "dyn:{key}:{drug_name}"엔 약 이름이 이미 포함돼 있으므로,
    /ask에서 답을 재구성할 때 patient_id로 "지금 환자의 최근 약"을 다시 조회할 필요가
    없다 — 그 사이 최근 약이 바뀌었으면 재조회 방식은 다른 약 이름으로 어긋난 id를
    만들어 매칭에 실패했다(잠재 버그, 이번에 같이 해결)."""
    parts = question_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "dyn":
        return None
    _, key, drug_name = parts
    template = next((t for t in _DYNAMIC_QUESTION_TEMPLATES if t[0] == key), None)
    if not template:
        return None
    _, text_tpl, answer_tpl = template
    return {"id": question_id, "text": text_tpl.format(drug=drug_name), "answer": answer_tpl.format(drug=drug_name)}

CHAT_SYSTEM_PROMPT = """\
당신은 고령 만성질환 환자와 보호자를 위한 복약 상담 챗봇입니다.

"본태성 고혈압이 뭐야?", "이 약은 어떤 효능이 있어?"처럼 질병명·약효분류 등에 대한
일반적인 의학 상식을 묻는 질문에는, 당신이 원래 알고 있는 지식으로 쉽게 설명해도 됩니다.
다만 "이 약을 먹어도 되나요", "부작용이 있나요"처럼 이 환자 개인에게 적용되는 판단은
반드시 아래 [환자 정보]에 있는 내용만 근거로 답하세요 — 거기 없는 내용을 이 환자에게
해당되는 것처럼 지어내지 마세요. 개인별 판단에 확신이 없으면 모른다고 솔직히 말하고,
반드시 의사나 약사와 상담하도록 안내하세요. 쉬운 말로, 고령자도 이해할 수 있게 2~4문장
이내로 짧게 답하세요.

병용금기, 노인주의, 연령금기, 임부금기/임신·수유 관련 주의사항은 질병관리청 건강정보가
아니라 [환자 정보] 안의 [DUR ...] 항목 또는 [DUR 보강조회] 항목만 근거로 답하세요.
[DUR 보강조회]는 질문에 나온 의약품명을 e약은요/허가정보로 확인한 뒤 DUR API로 다시
조회한 결과입니다. 두 항목 모두 없으면 "현재 확인된 DUR 경고는 보이지 않는다"고 말하되,
그 약이 안전하다고 확정하지 말고 약사나 의사에게 확인하라고 안내하세요. 질병관리청
생활정보로 DUR 여부를 추정하지 마세요.

[메뉴 안내]에 있는 화면 목록은 환자 개인 정보가 아니라 서비스 자체의 고정된 안내이니,
"OO 하려면 어디로 가야 하나요?" 같은 질문에는 이 목록만 근거로 화면 이름을 안내해도 됩니다
(예: "복약 일정은 화면 상단의 '전체메뉴'에서 '복약 일정'으로 들어가면 확인할 수 있어요").
메뉴 위치를 안내할 때는 반드시 "상단" 또는 "상단 전체메뉴"라고 말하고, 하단 메뉴라고
말하지 마세요. [메뉴 안내]에 없는 기능을 지어내지는 마세요.
[서비스 안내]도 환자 개인 정보가 아니라 이 앱의 고정 정보입니다. "이 앱은 뭐야?",
"무엇을 할 수 있어?", "어떻게 써?" 같은 질문에는 [서비스 안내]와 [메뉴 안내]만 근거로
답하세요.

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


SERVICE_INFO = {
    "name": "스마트 복약·생활지도 서비스",
    "target": "고령 만성질환 환자와 보호자",
    "purpose": "처방전 등록 후 복약 안내, 생활습관 가이드, 복약 일정·알림, 보호자 모니터링을 돕는 서비스",
    "data_scope": "등록된 처방전 OCR 결과, RAG로 생성된 복약·생활지도, DUR 주의정보, 앱 화면 정보를 참고",
    "safety": "챗봇 답변은 참고용이며 최종 복약 판단은 담당 의사나 약사에게 확인해야 함",
}


def _service_info_text() -> str:
    return "\n".join(
        [
            f"- 서비스명: {SERVICE_INFO['name']}",
            f"- 대상: {SERVICE_INFO['target']}",
            f"- 목적: {SERVICE_INFO['purpose']}",
            f"- 참고 정보 범위: {SERVICE_INFO['data_scope']}",
            f"- 안전 안내: {SERVICE_INFO['safety']}",
        ]
    )


def _menu_map_text() -> str:
    return "\n".join(
        [
            "- 메뉴 위치: 화면 상단 NavBar의 '전체메뉴' 드롭다운에서 접근합니다. 모바일에서도 상단 메뉴 버튼을 엽니다.",
            *[f"- {m['name']}({m['path']}): {m['desc']}" for m in MENU_MAP],
        ]
    )

# CHAT_PROVIDER=real일 때만 실제 LLM을 시도한다 (OCR_PROVIDER/RAG_PROVIDER와 동일 패턴).
# 기본값은 항상 PRESET_QUESTIONS 고정 답변 — 의존성 유무만으로 동작이 바뀌지 않는다.
_CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "stub")

# DUR 보강조회와 Chroma 검색은 rag/ 패키지의 클라이언트 모듈을 재사용하므로, LLM 사용 여부와
# 무관하게 import 경로를 먼저 열어둔다.
_RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
if _RAG_DIR.is_dir() and str(_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(_RAG_DIR))

_CHAT_LLM_AVAILABLE = False
if _CHAT_PROVIDER == "real":
    # rag/의 OpenAI 설정(.env의 OPENAI_API_KEY/OPENAI_MODEL)과 langchain-openai를
    # 재사용한다 — 키를 backend에 따로 둘 필요 없이 한 곳(rag/.env)만 관리하면 됨.
    try:
        from langchain_openai import (
            ChatOpenAI,  # noqa: F401 — 임포트 가능 여부만 확인(실사용은 지연 임포트)
        )
        from rag.config import settings as _rag_settings

        _CHAT_LLM_AVAILABLE = bool(_rag_settings.OPENAI_API_KEY)
    except Exception:  # noqa: BLE001 — 의존성 미설치/키 없음 등 어떤 이유로든 실패하면 폴백
        _CHAT_LLM_AVAILABLE = False


def _summarize_ocr_items(ocr_items: Sequence[OcrResult]) -> list[str]:
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
    """마찬가지로 스텁(diet/exercise 구조) vs 실제 파이프라인(guides 리스트) 두 모양 다 처리.

    [2026-07-21 회의 반영] 실제 파이프라인의 "guides"는 이제 문자열 배열이 아니라 진단명별
    {diagnosis, guide} 객체 배열이다(의약품별이 아니라 진단명 기준으로 생성이 바뀌었기 때문) —
    각 항목의 guide 텍스트만 뽑아 합친다. 옛 문자열 배열 항목이 섞여 들어와도(구 캐시 등)
    죽지 않도록 문자열 원소는 그대로 쓴다.
    """
    try:
        lifestyle_guide = json.loads(lifestyle_guide_json)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []

    guides = lifestyle_guide.get("guides")
    if guides:
        texts = [g.get("guide", "") if isinstance(g, dict) else str(g) for g in guides]
        texts = [t for t in texts if t]
        if texts:
            return ["[생활습관 안내] " + " ".join(texts)]

    lines = []
    diet = lifestyle_guide.get("diet") or {}
    exercise = lifestyle_guide.get("exercise") or {}
    if diet.get("avoid"):
        lines.append("[생활습관 안내] 피해야 할 음식: " + ", ".join(diet["avoid"]))
    if exercise:
        lines.append(f"운동 권장: {exercise.get('type', '')} {exercise.get('duration', '')}".strip())
    return lines


def _build_patient_context(patient_id: int, session: Session) -> str:
    """환자의 가장 최근 처방전(OcrResult/GuideResult)을 텍스트로 요약합니다.

    [버그 수정] 처방전 사진 없이 '내 약 등록'(PatientMedication)만 한 환자는 예전엔
    MedicalRecord가 없어 "아직 등록된 처방전 정보가 없습니다"만 나갔다 — 질문 문구엔
    약 이름이 있는데 정작 LLM 컨텍스트엔 빠지는 사각지대였다. 그래서 처방전 유무와
    무관하게 환자가 직접 등록한 약 이름(_patient_registered_drug_names)을 함께 넣는다."""
    lines: list[str] = []

    record = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).first()
    if record:
        ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
        lines.extend(_summarize_ocr_items(ocr_items))

        guide = session.exec(
            select(GuideResult).where(GuideResult.record_id == record.id).order_by(GuideResult.id.desc())
        ).first()
        if guide:
            lines.extend(_summarize_medication_guide(guide.medication_guide))
            lines.extend(_summarize_lifestyle_guide(guide.lifestyle_guide))
            lines.extend(_summarize_source_refs(guide.source_refs))

    registered_drug_names = _patient_registered_drug_names(patient_id, session)
    if registered_drug_names:
        lines.append(f"환자가 직접 등록한 약: {', '.join(registered_drug_names)}")

    return "\n".join(lines) if lines else "아직 등록된 처방전 정보가 없습니다."


def _latest_ocr_drug_names(patient_id: int, session: Session) -> list[str]:
    record = session.exec(
        select(MedicalRecord)
        .where(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    ).first()
    if not record:
        return []
    ocr_items = session.exec(select(OcrResult).where(OcrResult.record_id == record.id)).all()
    return [item.drug_name for item in ocr_items if item.drug_name]


_DUR_ONLY_KEYWORDS = (
    "dur",
    "병용금기",
    "병용 금기",
    "병용",
    "먹으면 안",
    "먹으면안",
    "안되는",
    "복용",
    "병용 가능",
    "병용가능",
    "병용해도",
    "같이 복용",
    "함께 복용",
    "드셔도",
    "드시면",
    "같이 먹",
    "함께 먹",
    "상호작용",
    "임부",
    "임신",
    "수유",
    "노인주의",
    "노인 주의",
    "고령",
    "연령금기",
    "연령 금기",
    "금기",
)

_DUR_QUERY_STOPWORDS = {
    "의약품",
    "정보",
    "알려줘",
    "뭐야",
    "있어",
    "없어",
    "확인",
    "가능",
    "가능해",
    "가능한가요",
    "가능한지",
    "가능할까요",
    "처방전",
    "약",
    "등록",
    "현재",
    "먹으면",
    "먹어도",
    "복용",
    "복용해도",
    "드셔도",
    "드시면",
    "고령자",
    "되나요",
    "괜찮나요",
    "되는",
    "안되는",
    "같이",
    "함께",
    "병용",
    "금기",
    "병용금기",
    "주의",
    "임부주의",
    "노인주의",
    "연령금기",
}

_DUR_TABOO_KEYWORDS = (
    "병용",
    "상호작용",
    "같이",
    "함께",
    "먹으면 안",
    "먹으면안",
    "안되는",
)

_DUR_CAUTION_KEYWORDS = (
    "임부",
    "임신",
    "수유",
    "노인주의",
    "노인 주의",
    "고령",
    "연령금기",
    "연령 금기",
)

_DRUG_RAG_QUERY_STOPWORDS = _DUR_QUERY_STOPWORDS | {
    "효능",
    "효과",
    "부작용",
    "주의사항",
    "복약",
    "가이드",
    "하단",
    "상단",
}

_DRUG_PARTICLE_SUFFIXES = (
    "이랑",
    "랑",
    "하고",
    "와",
    "과",
    "은",
    "는",
    "을",
    "를",
    "이",
    "가",
)

_DRUG_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+(?:정|캡슐|주|시럽|액|산|겔|크림|연고|패치)?")


def _should_answer_from_dur_only(question_text: str) -> bool:
    normalized = question_text.lower().replace(" ", "")
    return any(keyword.replace(" ", "") in normalized for keyword in _DUR_ONLY_KEYWORDS)


def _dur_lookup_modes(question_text: str) -> tuple[bool, bool]:
    """질문 의도에 맞는 DUR API만 조회한다.

    DUR API는 병용금기/노인주의/연령금기/임부금기가 서로 다른 엔드포인트다. 예전에는
    모든 DUR 질문에서 4종 API를 전부 조회해 병용금기 질문도 임부·연령·노인주의 API까지
    호출했다. 질문이 특정 카테고리를 가리키면 해당 계열만 조회하고, 애매하면 안전하게
    둘 다 조회한다.
    """
    normalized = question_text.replace(" ", "")
    needs_taboo = any(keyword.replace(" ", "") in normalized for keyword in _DUR_TABOO_KEYWORDS)
    needs_cautions = any(keyword.replace(" ", "") in normalized for keyword in _DUR_CAUTION_KEYWORDS)
    if not needs_taboo and not needs_cautions:
        return True, True
    return needs_taboo, needs_cautions


def _asks_for_taboo_list(question_text: str) -> bool:
    normalized = question_text.replace(" ", "")
    return any(
        keyword in normalized
        for keyword in (
            "먹으면안",
            "먹으면안되는",
            "먹으면안돼",
            "먹으면안되",
            "같이먹으면안",
            "함께먹으면안",
            "같이복용하면안",
            "함께복용하면안",
            "병용금기",
            "금기의약품",
            "금기약",
        )
    )


def _strip_drug_particle(token: str) -> str:
    stripped = token.strip(" ?!.~,，。")
    for suffix in _DRUG_PARTICLE_SUFFIXES:
        if stripped.endswith(suffix) and len(stripped) > len(suffix) + 1:
            return stripped[: -len(suffix)]
    return stripped


def _extract_dur_candidate_drug_names(question_text: str, registered_drug_names: list[str]) -> list[str]:
    normalized = question_text.replace(" ", "")
    candidates: list[str] = []

    for drug_name in registered_drug_names:
        short_name = drug_name.replace(" ", "")
        if short_name and (short_name in normalized or any(alias in normalized for alias in short_name.split("/"))):
            candidates.append(drug_name)

    for token in _DRUG_TOKEN_RE.findall(question_text):
        candidate = _strip_drug_particle(token)
        if len(candidate) >= 3 and candidate not in _DUR_QUERY_STOPWORDS:
            candidates.append(candidate)

    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        key = name.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result[:5]


def _extract_question_drug_candidate_names(question_text: str) -> list[str]:
    """일반 RAG 질문에서 사용자가 직접 언급한 약 이름 후보를 추출한다.

    doc_type=drug 유사도 검색은 질문 의도(예: "효능")에 끌려 다른 약 문서를 가져올 수
    있으므로, 질문에 약명이 명시돼 있으면 그 약과 맞는 문서만 참고자료로 쓴다.
    """
    candidates: list[str] = []
    for token in _DRUG_TOKEN_RE.findall(question_text):
        candidate = _strip_drug_particle(token)
        if len(candidate) >= 3 and candidate not in _DRUG_RAG_QUERY_STOPWORDS:
            candidates.append(candidate)

    seen: set[str] = set()
    result: list[str] = []
    for name in candidates:
        key = name.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result[:5]


def _normalize_drug_name_for_match(value: str) -> str:
    return re.sub(r"[\s()（）\-/·,]", "", value or "").replace("밀리그램", "밀리그람").lower()


def _doc_matches_question_drug(doc, drug_names: list[str]) -> bool:
    item_name = doc.metadata.get("item_name") or ""
    if not item_name:
        return False
    item_norm = _normalize_drug_name_for_match(item_name)
    return any(
        (candidate_norm := _normalize_drug_name_for_match(candidate))
        and (candidate_norm in item_norm or item_norm in candidate_norm)
        for candidate in drug_names
    )


def _resolve_one_dur_lookup_name(raw_name: str) -> list[str]:
    """raw_name 하나를 e약은요/허가정보로 확인해 후보 이름 목록을 만든다.

    [2026-07-21 분리] _resolve_dur_lookup_names()가 raw_names를 순차로 돌던 것을
    ThreadPoolExecutor로 병렬 호출하기 위해, raw_name 1개 처리 단위를 별도 함수로 뽑았다.
    """
    from rag.mfds_client import search_by_name, search_permit_info

    found: list[str] = [raw_name]
    try:
        for drug in search_by_name(raw_name, num_of_rows=5):
            found.append(drug.item_name)
    except Exception:  # noqa: BLE001
        pass
    try:
        for permit in search_permit_info(raw_name, num_of_rows=5):
            found.append(permit.item_name)
            if permit.ingr_name:
                for ingredient in re.split(r"[,;/+· ]+", permit.ingr_name):
                    ingredient = ingredient.strip()
                    if len(ingredient) >= 3:
                        found.append(ingredient)
    except Exception:  # noqa: BLE001
        pass
    return found


def _resolve_dur_lookup_names(raw_names: list[str]) -> list[str]:
    """질문에 나온 표현을 e약은요/의약품 허가정보로 확인해 DUR 조회어를 확장한다.

    사용자가 성분명(예: 심바스타틴)이나 제품명 일부를 입력할 수 있으므로, 원문 조회어만
    DUR에 던지지 않고 e약은요 품목명과 허가정보의 품목명/주성분명을 함께 후보로 삼는다.

    [2026-07-21 수정] raw_name마다 순차로 e약은요+허가정보 live API를 호출하던 걸
    ThreadPoolExecutor로 병렬화했다 — 정부 공공데이터포털 API가 개별 호출당 수백ms~수초
    걸릴 수 있어, 챗봇 DUR 질문 하나가 이 단계에서만 최대 10회(5개 후보 x 2개 API)
    순차 호출로 여러 초가 걸리던 문제(사용자 보고 "챗봇 답변 느림")의 핵심 원인이었다.
    """
    try:
        from rag.mfds_client import search_by_name, search_permit_info  # noqa: F401
    except Exception:  # noqa: BLE001
        return raw_names

    if len(raw_names) == 1:
        resolved = _resolve_one_dur_lookup_name(raw_names[0])
    else:
        with ThreadPoolExecutor(max_workers=min(len(raw_names), 8)) as executor:
            resolved = [name for names in executor.map(_resolve_one_dur_lookup_name, raw_names) for name in names]

    seen: set[str] = set()
    result: list[str] = []
    for name in resolved:
        key = name.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result[:6]


def _search_dur_taboo(item_name: str):
    from rag.dur_master import search_usjnt_taboo

    return search_usjnt_taboo(item_name, num_of_rows=20)


def _search_dur_cautions(item_name: str):
    from rag.dur_master import search_age_taboo, search_elderly_caution, search_pregnancy_taboo

    return [
        *search_elderly_caution(item_name, num_of_rows=20),
        *search_age_taboo(item_name, num_of_rows=20),
        *search_pregnancy_taboo(item_name, num_of_rows=20),
    ]


def _matches_drug_name(left: str, right: str) -> bool:
    left_norm = left.replace(" ", "")
    right_norm = right.replace(" ", "")
    return bool(left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm))


def _build_on_demand_dur_context(question_text: str, registered_drug_names: list[str]) -> list[str]:
    if not _should_answer_from_dur_only(question_text):
        return []

    # [2026-07-21 추가] 이 경로(DUR 전용 질문)는 _retrieve_chat_rag_docs가 ChromaDB를
    # 아예 건너뛰므로(DUR 데이터는 Chroma에 없음) Langfuse에 retriever 스팬이 하나도 안
    # 남았다 — 실제 조회(e약은요/허가정보 이름 확인 + DUR API 4종)는 여기서 일어나는데
    # 그게 하나도 안 보이니 "DUR 관련 질문인데 조회 기록이 없다"는 오해를 샀다.
    # vectorstore.similarity_search()와 동일한 as_type="retriever" 패턴으로 span을 남긴다.
    with optional_observation(
        as_type="retriever",
        name="retrieve-dur-lookup",
        input={"question": mask_for_langfuse(question_text)},
    ) as observation:
        with optional_observation(as_type="span", name="dur-extract-candidates") as extract_observation:
            raw_candidate_names = _extract_dur_candidate_drug_names(question_text, registered_drug_names)
            needs_taboo, needs_cautions = _dur_lookup_modes(question_text)
            update_observation(
                extract_observation,
                output={
                    "raw_candidate_names": raw_candidate_names,
                    "needs_taboo": needs_taboo,
                    "needs_cautions": needs_cautions,
                },
            )

        if not raw_candidate_names:
            lines = [
                "[DUR 보강조회] 질문에서 조회할 의약품명을 특정하지 못했습니다. 약 이름을 정확히 입력받아 DUR 병용금기/주의정보를 확인해야 합니다."
            ]
            update_observation(
                observation,
                output={"lookup_names": [], "retrieved_line_count": len(lines), "status": "missing-drug-name"},
            )
            flush_langfuse()
            return lines

        with optional_observation(
            as_type="span",
            name="dur-resolve-lookup-names",
            input={"raw_candidate_count": len(raw_candidate_names)},
        ) as resolve_observation:
            lookup_names = _resolve_dur_lookup_names(raw_candidate_names)
            update_observation(
                resolve_observation,
                output={"lookup_names": lookup_names, "lookup_name_count": len(lookup_names)},
            )

        # [2026-07-21 수정] drug_name마다 병용금기(1회) + 노인주의/연령금기/임부금기(3회)를
        # 순차 live API 호출로 조회하던 걸 ThreadPoolExecutor로 병렬화했다 — lookup_names가
        # 최대 10개라 순차로는 최대 40회 호출이 직렬로 쌓였다(_resolve_dur_lookup_names의
        # 병렬화와 같은 이유).
        def _lookup_one(drug_name: str) -> tuple[str, list, list, Exception | None]:
            try:
                taboos = _search_dur_taboo(drug_name) if needs_taboo else []
                cautions = _search_dur_cautions(drug_name) if needs_cautions else []
                return drug_name, taboos, cautions, None
            except Exception as exc:  # noqa: BLE001
                return drug_name, [], [], exc

        with optional_observation(
            as_type="span",
            name="dur-query-api",
            input={
                "lookup_name_count": len(lookup_names),
                "needs_taboo": needs_taboo,
                "needs_cautions": needs_cautions,
            },
        ) as query_observation:
            if len(lookup_names) == 1:
                lookup_results = [_lookup_one(lookup_names[0])]
            else:
                with ThreadPoolExecutor(max_workers=min(len(lookup_names), 8)) as executor:
                    lookup_results = list(executor.map(_lookup_one, lookup_names))
            update_observation(
                query_observation,
                output={
                    "result_count": len(lookup_results),
                    "error_count": sum(1 for _, _, _, error in lookup_results if error is not None),
                    "taboo_count": sum(len(taboos) for _, taboos, _, _ in lookup_results),
                    "caution_count": sum(len(cautions) for _, _, cautions, _ in lookup_results),
                },
            )

        lines: list[str] = []
        for drug_name, taboos, cautions, lookup_error in lookup_results:
            if lookup_error is not None:
                lines.append(f"[DUR 보강조회] {drug_name}: DUR API 조회에 실패했습니다. 약사나 의사에게 확인이 필요합니다.")
                continue

            display_name = drug_name
            for caution in cautions[:5]:
                detail = f": {caution.detail}" if caution.detail else ""
                extra = f" ({caution.extra})" if caution.extra else ""
                lines.append(f"[DUR 보강조회] {display_name} - {caution.category}{extra}{detail}")

            partner_names = [name for name in [*registered_drug_names, *lookup_names] if name != drug_name]
            if _asks_for_taboo_list(question_text):
                matched_taboos = taboos
            else:
                matched_taboos = [
                    taboo
                    for taboo in taboos
                    if any(_matches_drug_name(taboo.mixture_item_name, partner) for partner in partner_names)
                ]
            for taboo in matched_taboos[:5]:
                content = f": {taboo.prohbt_content}" if taboo.prohbt_content else ""
                lines.append(f"[DUR 보강조회] {display_name} - {taboo.mixture_item_name} 병용금기{content}")

        update_observation(
            observation,
            output={"lookup_names": lookup_names, "retrieved_line_count": len(lines)},
        )
        flush_langfuse()

    if not lines:
        joined = ", ".join(raw_candidate_names)
        return [f"[DUR 보강조회] {joined}: DUR API에서 확인된 노인주의/연령금기/임부금기 또는 질문 내 약물 간 병용금기 항목을 찾지 못했습니다. 미등재·검색어 불일치 가능성이 있어 안전 판단으로 확정하지 마세요."]
    return lines


_LIFESTYLE_KEYWORDS = (
    "음식",
    "식단",
    "식이",
    "먹으면 좋",
    "먹지 말",
    "먹지말",
    "운동",
    "생활습관",
    "생활 습관",
    "생활지침",
    "금연",
    "담배",
    "음주",
    "절주",
    "체중",
    "다이어트",
    "합병증 예방",
    "합병증예방",
)


def _is_lifestyle_question(question_text: str) -> bool:
    """[2026-07-21 추가] 생활습관(음식/운동/주의사항) 질문인지 판별한다 — 이런 질문은 의약품
    문서보다 질병관리청 건강정보(doc_type="kdca_health_info")를 우선 조회해야 한다
    (_should_answer_from_dur_only와 동일한 키워드 기반 분류 방식)."""
    normalized = question_text.replace(" ", "")
    return any(keyword.replace(" ", "") in normalized for keyword in _LIFESTYLE_KEYWORDS)


def _retrieve_chat_rag_docs(question_text: str) -> list:
    """챗봇 자유질문의 실제 ChromaDB 근거 문서를 검색한다.

    처방전 등록 시 생성된 GuideResult만 읽으면 이미 저장된 요약에는 답할 수 있지만,
    Langfuse에서 실제 retrieval이 보이지 않고 최신 ChromaDB 근거도 다시 확인하지 못한다.
    조회 실패는 챗봇 전체 실패로 보지 않고 빈 리스트로 처리한다.

    [2026-07-20] 예전엔 이 함수가 LLM 프롬프트용 문자열만 만들고 실제 검색된 문서 정보
    (title/source/item_name)를 API 응답에 전혀 안 내려줬다 — 프론트가 answer_source("llm
    (gpt-4o-mini)" 등, 생성 "방법" 라벨일 뿐)를 "출처"로 오인해 보여주고 있었다. 이제
    Document 자체를 반환해서 호출부가 프롬프트용 문자열(_rag_docs_to_prompt_lines)과
    실제 인용 데이터(_rag_docs_to_source_refs) 양쪽을 같은 조회 결과에서 만든다.

    [2026-07-21 수정] doc_type 필터 없이 컬렉션 전체를 한 번에 유사도 검색하면 의약품/생활습관
    문서가 뒤섞여 나와 우선순위가 없었다 — rag_chain.py._build_context()와 동일한 원칙으로,
    생활습관(음식/운동/주의사항) 질문은 질병관리청 건강정보(doc_type="kdca_health_info")를
    최우선으로, 그 외(의약품 관련) 질문은 doc_type="drug"(e약은요/HIRA 기반 문서)를 최우선으로
    조회하고 못 찾을 때만 필터 없는 전체 검색으로 넘어간다.
    """
    if _should_answer_from_dur_only(question_text):
        return []

    # Langfuse retriever span records query metadata. Do not include stored
    # patient context here; it can contain diagnoses and medication history.
    query = question_text.strip()
    if not query:
        return []

    try:
        from rag.rag_chain import resolve_drug_name_candidates
        from rag.vectorstore import search_by_item_name, similarity_search

        primary_filter = {"doc_type": "kdca_health_info"} if _is_lifestyle_question(query) else {"doc_type": "drug"}
        question_drug_names = [] if _is_lifestyle_question(query) else _extract_question_drug_candidate_names(query)
        for drug_name in question_drug_names:
            for candidate in resolve_drug_name_candidates(drug_name):
                exact_docs = search_by_item_name(candidate)
                if exact_docs:
                    return exact_docs[:3]

        docs = similarity_search(query[:1000], k=3, filter=primary_filter)
        if question_drug_names:
            docs = [doc for doc in docs if _doc_matches_question_drug(doc, question_drug_names)]
        if not docs:
            docs = similarity_search(query[:1000], k=3)
            if question_drug_names:
                docs = [doc for doc in docs if _doc_matches_question_drug(doc, question_drug_names)]
        return docs
    except Exception:  # noqa: BLE001 — RAG 조회 실패 시에도 챗봇 답변 폴백/LLM 답변은 유지
        return []


def _rag_docs_to_prompt_lines(docs: list) -> list[str]:
    lines = []
    for idx, doc in enumerate(docs, start=1):
        title = doc.metadata.get("title") or doc.metadata.get("item_name") or doc.metadata.get("disease") or "자료"
        source = doc.metadata.get("source") or doc.metadata.get("field_label") or doc.metadata.get("field") or ""
        label = f"{title} / {source}" if source else title
        lines.append(f"[{idx}] {label}\n{doc.page_content}")
    return lines


def _rag_docs_to_source_refs(docs: list) -> list[dict]:
    """실제 검색된 문서의 title/source/item_name 등을 프론트에서 확인할 수 있는 형태로
    변환한다. frontend/src/api/records.ts의 기존 SourceRef 타입/formatSourceRef와 필드명을
    맞춰 재사용한다(의약품 인용에 이미 쓰이는 관례 — 새 타입 안 만듦)."""
    refs = []
    for doc in docs:
        ref = {
            k: v
            for k, v in {
                "item_name": doc.metadata.get("item_name"),
                "field": doc.metadata.get("field_label") or doc.metadata.get("field"),
                "disease": doc.metadata.get("disease") or doc.metadata.get("title"),
                "category": doc.metadata.get("category"),
                "source": doc.metadata.get("source"),
            }.items()
            if v
        }
        if ref:
            refs.append(ref)
    return refs


def _build_chat_messages(
    bot_name: str,
    context_text: str,
    question_text: str,
    rag_context_text: str = "",
    dur_context_text: str = "",
) -> list[dict]:
    """/ask(비스트리밍)와 /ask/stream(REQ-021 SSE)이 공유하는 프롬프트 조립 — 전달 방식만
    다르고 LLM에 주는 내용은 완전히 동일해야 하므로 여기 한 곳에서만 만든다."""
    rag_section = f"\n\n[RAG 참고자료]\n{rag_context_text}" if rag_context_text else ""
    dur_section = f"\n\n[DUR 보강조회]\n{dur_context_text}" if dur_context_text else ""
    return [
        {"role": "system", "content": f"당신의 이름은 '{bot_name}'입니다. 이름을 물어보면 이렇게 답하세요.\n\n{CHAT_SYSTEM_PROMPT}"},
        {
            "role": "user",
            "content": (
                f"[서비스 안내]\n{_service_info_text()}\n\n"
                f"[메뉴 안내]\n{_menu_map_text()}\n\n"
                f"[환자 정보]\n{context_text}\n\n[질문]\n{question_text}"
                f"{rag_section}"
                f"{dur_section}"
            ),
        },
    ]


def _generate_llm_answer(
    question_text: str,
    context_text: str,
    bot_name: str,
    rag_context_text: str = "",
    dur_context_text: str = "",
) -> str:
    from langchain_openai import ChatOpenAI
    from rag.config import settings as rag_settings

    chat = ChatOpenAI(model=rag_settings.OPENAI_MODEL, api_key=rag_settings.OPENAI_API_KEY, temperature=0.4)
    messages = _build_chat_messages(bot_name, context_text, question_text, rag_context_text, dur_context_text)
    callback_handler = get_langchain_callback_handler()
    invoke_config = {"callbacks": [callback_handler]} if callback_handler else None
    response = chat.invoke(messages, config=invoke_config)
    content = response.content
    return content.strip() if isinstance(content, str) else str(content)


def _resolve_question(payload: ChatAsk, session: Session) -> tuple[str, str, str, str, bool]:
    """question_id(고정/동적 질문) 또는 question(자유 텍스트) 중 하나를 해석해
    (question_id, question_text, answer, source, use_llm)을 반환한다.
    /ask, /ask/stream이 완전히 동일한 해석 규칙을 써야 하므로 여기서 공유한다.

    마지막 use_llm은 두 엔드포인트가 LLM 호출 여부를 동일하게 판단하도록 여기서 한 번만
    결정한다: preset/dynamic 질문이 매칭되면 이미 검수된 고정 답변이 있으므로 LLM을
    호출하지 않고(use_llm=False) 그 답변을 그대로 내보내고, 자유입력(freeform)일 때만
    LLM을 호출한다(use_llm=True). (버그: 예전엔 종류와 무관하게 _CHAT_LLM_AVAILABLE이면
    무조건 LLM을 태워 고정 답변이 LLM으로 새어나갔다.)"""
    if payload.question_id:
        match = (
            _resolve_dynamic_question_by_id(payload.question_id)
            if payload.question_id.startswith("dyn:")
            else None
        )
        if not match:
            match = next((q for q in PRESET_QUESTIONS if q["id"] == payload.question_id), None)
        if not match:
            raise HTTPException(404, "존재하지 않는 질문이에요")
        return match["id"], match["text"], match["answer"], "preset", False
    if payload.question and payload.question.strip():
        return (
            "freeform",
            payload.question.strip(),
            "죄송해요, 지금은 이 질문에 실시간으로 답변드리기 어려워요. 담당 의사나 약사에게 확인해주세요.",
            "unsupported",
            True,
        )
    raise HTTPException(422, "question_id 또는 question 중 하나는 필요해요")


def _gather_llm_inputs(
    patient_id: int, question_text: str, session: Session
) -> tuple[str, list[str], list[str], str, list[dict]]:
    """환자 컨텍스트 + DUR 보강조회 + RAG 근거 + 챗봇 이름 + RAG 인용 데이터를 모은다 —
    /ask, /ask/stream 공용. DUR/RAG는 리스트로 반환해 호출부가 각자 필요한 형태(개수 집계
    vs 그냥 join)로 쓴다.

    [2026-07-20 추가] rag_refs — 실제 검색된 문서(title/source/item_name)를 API 응답의
    source_refs로 내려주기 위해 한 번의 조회(_retrieve_chat_rag_docs)에서 프롬프트용
    문자열과 함께 만든다(중복 조회 없음)."""
    context_text = _build_patient_context(patient_id, session)
    # DUR 조회용 약 이름: 처방전 OCR 약 이름 + 환자가 직접 등록한 약 이름을 합친다.
    # (버그: OCR만 보면 처방전 없이 '내 약 등록'만 한 환자는 DUR 조회에서 통째로 빠졌다.)
    registered_drug_names = list(
        dict.fromkeys(
            [*_patient_registered_drug_names(patient_id, session), *_latest_ocr_drug_names(patient_id, session)]
        )
    )
    dur_context_lines = _build_on_demand_dur_context(question_text, registered_drug_names)
    rag_docs = _retrieve_chat_rag_docs(question_text)
    rag_context_lines = _rag_docs_to_prompt_lines(rag_docs)
    rag_refs = _rag_docs_to_source_refs(rag_docs)
    setting = session.get(NotificationSetting, patient_id)
    bot_name = setting.chatbot_name if setting else "약콩이"
    return context_text, dur_context_lines, rag_context_lines, bot_name, rag_refs


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/questions")
def list_questions(
    patient_id: int,
    drug_name: str | None = None,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
):
    """Chat.tsx의 추천 질문 버튼에 쓸 목록.

    [2026-07-23 수정] 예전엔 어느 화면에서 들어왔든 항상 "환자가 최근 등록한 약" 기준으로
    질문을 만들었다 — 그래서 A약 상세에서 들어가도, 우측 하단 플로팅 챗봇으로 들어가도
    같은(최근) 약 이름이 붙는 문제가 있었다. 이제는 Chat.tsx가 실제로 어느 약 맥락에서
    열렸는지(location.state.drugName) 그대로 넘겨준 drug_name만 쓴다 — 맥락 없이(플로팅
    버튼) 들어왔으면 특정 약을 지어내지 않고 고정 질문(PRESET_QUESTIONS)을 보여준다.
    [2026-07-19 추가] patient_id를 받게 되면서 다른 환자 정보 유추에 악용되지 않도록
    require_actor_patient_access로 막는다(다른 인가된 엔드포인트와 동일 패턴)."""
    require_actor_patient_access(patient_id, actor, session)
    questions = _build_dynamic_questions(drug_name) if drug_name else PRESET_QUESTIONS
    return [{"id": q["id"], "text": q["text"]} for q in questions]


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

    question_id, question_text, fallback_answer, fallback_source, use_llm = _resolve_question(payload, session)

    started_ms = now_ms()
    answer_text, answer_source = fallback_answer, fallback_source
    context_line_count = 0
    rag_context_count = 0
    dur_context_count = 0
    source_refs: list[dict] = []

    with optional_observation(
        as_type="span",
        name="chat-ask",
        input={
            "question": mask_for_langfuse(question_text),
            "question_id": question_id,
            "patient_id": payload.patient_id,
            "chat_provider": _CHAT_PROVIDER,
            "llm_available": _CHAT_LLM_AVAILABLE,
        },
    ) as trace:
        if _CHAT_LLM_AVAILABLE and use_llm:
            try:
                context_text, dur_context_lines, rag_context_lines, bot_name, source_refs = _gather_llm_inputs(
                    payload.patient_id, question_text, session
                )
                context_line_count = len([line for line in context_text.splitlines() if line.strip()])
                dur_context_count = len(dur_context_lines)
                dur_context_text = "\n".join(dur_context_lines)
                rag_context_count = len(rag_context_lines)
                rag_context_text = "\n\n".join(rag_context_lines)
                with optional_observation(
                    as_type="generation",
                    name="chat-llm-answer",
                    model=_rag_settings.OPENAI_MODEL,
                    input={
                        "question": mask_for_langfuse(question_text),
                        "context_line_count": context_line_count,
                        "rag_context_count": rag_context_count,
                        "dur_context_count": dur_context_count,
                    },
                ) as generation:
                    answer_text = _generate_llm_answer(
                        question_text,
                        context_text,
                        bot_name,
                        rag_context_text,
                        dur_context_text,
                    )
                    answer_source = f"llm ({_rag_settings.OPENAI_MODEL})"
                    update_observation(generation, output={"answer": mask_for_langfuse(answer_text)})
            except Exception as exc:  # noqa: BLE001 — LLM 실패해도 챗봇 자체는 응답해야 함
                answer_text, answer_source = fallback_answer, f"{fallback_source}_fallback ({type(exc).__name__})"
                source_refs = []  # 실제 표시되는 답변은 폴백 문구라 방금 조회한 인용은 무관함

        update_observation(
            trace,
            output={
                "answer": mask_for_langfuse(answer_text),
                "answer_source": answer_source,
                "context_line_count": context_line_count,
                "rag_context_count": rag_context_count,
                "dur_context_count": dur_context_count,
                "latency_ms": round(now_ms() - started_ms, 2),
            },
        )
        flush_langfuse()

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
        "source_refs": source_refs,
        "created_at": msg.created_at.isoformat(),
    }


@router.post("/ask/stream")
async def ask_stream(
    payload: ChatAsk, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)
):
    """REQ-021 — /ask와 같은 질문·답변 로직이지만 SSE(text/event-stream)로 토큰이 도착하는
    대로 흘려보낸다. 응답 전체가 완성될 때까지 기다리지 않아도 되므로 체감 응답속도가
    낮아진다(긴 답변일수록 효과가 큼).

    [2026-07-19] 스트리밍 바디(_stream) 안에서도 이 요청의 Depends(get_session) session을
    그대로 쓴다 — FastAPI는 StreamingResponse의 body_iterator가 끝까지 소진될 때까지
    generator 의존성(Depends(get_session))을 정리하지 않으므로 안전하고, 무엇보다
    이 프로젝트의 모든 라우터 테스트가 의존하는 `app.dependency_overrides[get_session]`
    패턴과 호환된다(처음엔 core/scheduler.py처럼 별도 Session(engine)을 열었다가, 그러면
    테스트가 오버라이드한 세션과 완전히 다른 DB를 보게 되어 응답이 통째로 비어버리는 걸
    확인하고 이 방식으로 되돌렸다).
    """
    require_actor_patient_access(payload.patient_id, actor, session)
    if not session.get(Patient, payload.patient_id):
        raise HTTPException(404, "해당 환자를 찾을 수 없어요")

    question_id, question_text, fallback_answer, fallback_source, use_llm = _resolve_question(payload, session)
    patient_id = payload.patient_id

    async def _stream():
        answer_text, answer_source = fallback_answer, fallback_source
        source_refs: list[dict] = []
        chunks: list[str] = []
        started_ms = now_ms()

        with optional_observation(
            as_type="span",
            name="chat-ask-stream",
            input={
                "question": mask_for_langfuse(question_text),
                "question_id": question_id,
                "patient_id": patient_id,
                "chat_provider": _CHAT_PROVIDER,
                "llm_available": _CHAT_LLM_AVAILABLE,
            },
        ) as trace:
            if _CHAT_LLM_AVAILABLE and use_llm:
                try:
                    from langchain_openai import ChatOpenAI
                    from rag.config import settings as rag_settings

                    context_text, dur_lines, rag_lines, bot_name, source_refs = await asyncio.to_thread(
                        _gather_llm_inputs, patient_id, question_text, session
                    )
                    context_line_count = len([line for line in context_text.splitlines() if line.strip()])
                    rag_context_count = len(rag_lines)
                    dur_context_count = len(dur_lines)
                    messages = _build_chat_messages(
                        bot_name, context_text, question_text, "\n\n".join(rag_lines), "\n".join(dur_lines)
                    )
                    chat = ChatOpenAI(
                        model=rag_settings.OPENAI_MODEL, api_key=rag_settings.OPENAI_API_KEY, temperature=0.4
                    )
                    callback_handler = get_langchain_callback_handler()
                    invoke_config = {"callbacks": [callback_handler]} if callback_handler else None

                    with optional_observation(
                        as_type="generation",
                        name="chat-stream-llm-answer",
                        model=rag_settings.OPENAI_MODEL,
                        input={
                            "question": mask_for_langfuse(question_text),
                            "context_line_count": context_line_count,
                            "rag_context_count": rag_context_count,
                            "dur_context_count": dur_context_count,
                        },
                    ) as generation:
                        async for chunk in chat.astream(messages, config=invoke_config):
                            piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                            if piece:
                                chunks.append(piece)
                                yield _sse_event({"delta": piece})

                        answer_text = "".join(chunks).strip() or fallback_answer
                        update_observation(generation, output={"answer": mask_for_langfuse(answer_text)})
                    answer_source = f"llm ({rag_settings.OPENAI_MODEL})"
                except Exception as exc:  # noqa: BLE001 — 스트리밍 실패해도 뭐라도 답은 남겨야 함
                    if chunks:
                        # 이미 실제 답변 일부를 내보낸 뒤 실패한 경우 — 폴백 문구를 이어붙이면
                        # 서로 다른 두 답이 섞여 보이므로, 지금까지 나간 내용만 최종 답으로
                        # 확정한다(추가 delta 없이 done 이벤트의 partial=true로만 알림).
                        answer_text = "".join(chunks).strip()
                        answer_source = f"llm_partial ({type(exc).__name__})"
                    else:
                        answer_text, answer_source = fallback_answer, f"{fallback_source}_fallback ({type(exc).__name__})"
                        source_refs = []  # 실제 표시되는 답변은 폴백 문구라 방금 조회한 인용은 무관함
                        yield _sse_event({"delta": answer_text})
            else:
                yield _sse_event({"delta": answer_text})

            update_observation(
                trace,
                output={
                    "answer": mask_for_langfuse(answer_text),
                    "answer_source": answer_source,
                    "latency_ms": round(now_ms() - started_ms, 2),
                },
            )
            flush_langfuse()

        msg = ChatMessage(
            patient_id=patient_id, question_id=question_id, question_text=question_text, answer_text=answer_text
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        created_at = msg.created_at.isoformat()

        yield _sse_event(
            {
                "done": True,
                "answer_source": answer_source,
                "source_refs": source_refs,
                "created_at": created_at,
                "partial": answer_source.startswith("llm_partial"),
            }
        )

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/history")
def history(patient_id: int, actor: Actor = Depends(get_current_actor), session: Session = Depends(get_session)):
    """지난 대화 이력 (마이페이지 등에서 참고용으로 쓸 수 있음)"""
    require_actor_patient_access(patient_id, actor, session)
    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.patient_id == patient_id)
        .order_by(ChatMessage.created_at)
    ).all()
