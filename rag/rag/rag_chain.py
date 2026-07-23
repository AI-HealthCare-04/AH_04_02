import json
import logging
import re

from langchain_core.documents import Document
from rag.chunking import drugs_to_documents
from rag.config import settings
from rag.dur_master import (
    search_age_taboo,
    search_elderly_caution,
    search_pregnancy_taboo,
    search_usjnt_taboo,
)
from rag.hira_master import search_by_product_name as search_hira_by_product_name
from rag.mfds_client import (
    parse_doc_sections,
    search_by_name,
    search_permit_detail,
    search_permit_info,
)
from rag.schemas import (
    DrugPermitInfo,
    DurCaution,
    DurWarning,
    GuideResponse,
    HiraDrugMasterEntry,
    LifestyleCategoryGuide,
    LifestyleGuideResult,
    LifestyleSourceRef,
    MedicationInput,
    SourceRef,
)
from rag.self_consistency import pick_consistent_answer
from rag.vectorstore import (
    add_documents,
    search_by_disease,
    search_by_item_name,
    search_kdca_health_info,
    similarity_search,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
당신은 고령 만성질환 환자와 보호자를 위한 복약 안내를 작성하는 보조자입니다.
[참고자료]는 이 의약품 하나에 대한 정보(효능·용법·주의사항·부작용 등)입니다.
생활습관·식이·운동 안내는 여기서 다루지 않습니다 — 그 내용은 진단명 기준으로 별도 생성되므로,
medication_guide/precautions에 식이·운동 같은 일반 생활습관 조언을 넣지 마세요.
아래 [참고자료]에 없는 내용은 절대로 지어내지 마세요 (hallucination 금지).
모든 문장은 [참고자료]의 번호를 근거로 작성하고, 사용한 번호를 source_refs에 정수 배열로 포함하세요.
쉬운 말로, 고령자도 이해할 수 있도록 짧은 문장으로 작성하세요.
반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트를 추가하지 마세요.

{
  "medication_guide": "복약 안내 (효능, 복용법, 핵심 주의사항 요약)",
  "precautions": ["이 약을 복용할 때 반드시 확인해야 할 주의사항 1", "..."],
  "source_refs": [1, 2]
}
"""

# [2026-07-21 회의 반영] 생활습관 안내는 의약품별이 아니라 "진단명" 기준으로 별도 생성한다 —
# 위 SYSTEM_PROMPT(의약품 전용)와 완전히 분리된 프롬프트를 써서, 같은 LLM 호출 안에서
# 두 성격이 섞이지 않게 한다(generate_lifestyle_guide_for_diagnosis 전용).
LIFESTYLE_SYSTEM_PROMPT = """\
당신은 고령 만성질환 환자와 보호자를 위한 "진단명 기준" 생활습관 안내를 작성하는 보조자입니다.
[참고자료]는 특정 진단명(질환)에 대한 생활습관 지침(질병관리청·학회 진료지침 기반)입니다.
이 안내는 특정 의약품이 아니라 진단명 자체를 기준으로 작성해야 합니다 — 약 이름은 절대 언급하지 마세요.
아래 [참고자료]에 없는 내용은 절대로 지어내지 마세요 (hallucination 금지). 근거가 없는 카테고리는
억지로 채우지 말고 recommended/avoid를 빈 배열로 두세요.
각 항목은 [참고자료]에 실제로 있는 내용만 짧은 문장 하나로 쓰세요. 항목마다 근거로 쓴 [참고자료]
번호를 모아 source_refs에 정수 배열로 포함하세요.
쉬운 말로, 고령자도 이해할 수 있도록 짧은 문장으로 작성하세요.
diet(식사)/exercise(운동)/other(그 외 — 금연·금주·스트레스 관리·정기 검진 등) 세 카테고리 각각에
recommended(권장 사항)와 avoid(피해야 할 사항) 목록을 채우세요.
반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트를 추가하지 마세요.

{
  "diet": {"recommended": ["..."], "avoid": ["..."]},
  "exercise": {"recommended": ["..."], "avoid": ["..."]},
  "other": {"recommended": ["..."], "avoid": ["..."]},
  "source_refs": [1, 2]
}
"""

# 진단명(자유 텍스트)에 등장하는 별칭 -> data/lifestyle_guidelines.json의 disease_code.
# 가장 긴 별칭이 먼저 오도록 순서를 유지할 필요는 없음 (부분 포함 여부만 검사, 중복은 제거됨).
# 여기 없는 질환(예: 관상동맥질환/위염/골관절염 등)은 생활지침 인용 0건이 정상 동작이다
# (커버 안 되는 질환을 근거 없이 지어내지 않기 위함 — 버그 아님, CONTRACT.md 4번 참고).
DIAGNOSIS_DISEASE_ALIASES: dict[str, str] = {
    "고혈압": "hypertension",
    "당뇨병": "diabetes",
    "당뇨": "diabetes",
    "이상지질혈증": "dyslipidemia",
    "고지혈증": "dyslipidemia",
    "만성콩팥병": "chronic_kidney_disease",
    "만성신부전": "chronic_kidney_disease",
    "콩팥병": "chronic_kidney_disease",
    "신장질환": "chronic_kidney_disease",
}


def _resolve_disease_codes(diagnosis: str | None) -> list[str]:
    if not diagnosis:
        return []
    codes: list[str] = []
    for alias, code in DIAGNOSIS_DISEASE_ALIASES.items():
        if alias in diagnosis and code not in codes:
            codes.append(code)
    return codes


class NoContextFoundError(RuntimeError):
    pass


def _live_fetch_and_ingest(drug_name: str) -> list[Document]:
    """벡터DB에 없는 약이면 식약처 API에서 바로 조회해 즉시 채워 넣고, 그 문서를 그대로 돌려준다.

    OCR이 처방전에서 실시간으로 뽑아내는 약은 사전 ingest 배치에 없을 수 있으므로,
    이 fallback이 없으면 방금 인식한 약을 조회할 방법이 없다.

    [2026-07-20 수정] 예전엔 인제스트만 하고 호출부가 같은 drug_name 문자열로
    search_by_item_name()을 다시 호출했는데, e약은요가 반환하는 공식 item_name이
    질의어와 다를 수 있어(예: "5mg" 질의 → 실제 저장은 "5밀리그람") 재조회가 또 실패했다.
    방금 만든 문서를 그대로 반환해 이 재조회 단계 자체를 없앤다.
    """
    found = search_by_name(drug_name, num_of_rows=settings.TOP_K)
    if not found:
        return []
    documents = drugs_to_documents(found)
    add_documents(documents)
    return documents


_DOSAGE_FORM_RE = re.compile(
    r'\s*\d+(\.\d+)?\s*'
    r'(mg|ml|mcg|μg|ug|g|mEq|IU|%|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정|액|시럽|주|크림|연고|겔|패취|패치|점안|점이)'
    r'(\s*/\s*\d+(\.\d+)?\s*(mg|ml|mcg|μg|ug|g|mEq|IU|%|정|캡슐|연질캡슐|장용정|장용캡슐|서방정|분산정))?',
    re.IGNORECASE,
)


def _strip_dosage_form(text: str) -> str:
    """용량·제형 표기를 제거한 이름 반환("암로디핀정5mg" -> "암로디핀").

    backend/services/drug_matcher.py의 _normalize()와 발상이 같지만, rag/ 패키지는
    backend를 import하지 않는 기존 관례(별도 배포 단위)를 따르기 위해 여기서 작게
    재구현한다.
    """
    normalized = _DOSAGE_FORM_RE.sub("", text).strip()
    return re.sub(r'\s+', ' ', normalized).strip()


def resolve_drug_name_candidates(drug_name: str) -> list[str]:
    """이름 표기 불일치(용량 단위 표기 차이 등) 대응용 후보 목록 — 원문 → 용량·제형 표기
    제거명 순으로, 순서대로 시도해 첫 히트에서 멈추는 fallback 체인에 쓴다.

    [2026-07-20] HIRA 약가마스터/허가정보 조회로 후보를 추가로 확장하는 안도 검토했지만,
    실제 라이브 API로 확인한 결과 HIRA/허가정보도 e약은요와 마찬가지로 브랜드/상품명
    표기이지 성분명 사전이 아니라(예: "노바스크정5밀리그람(암로디핀베실산염)"처럼 브랜드+
    용량+성분명이 한 문자열에 섞여 있음) — 실질적인 매칭 개선 효과가 불확실한 반면, 매
    호출마다 네트워크 조회가 2회씩 추가로 늘어나고 기존 _build_context 테스트들의
    "HIRA/허가정보는 정확히 1번만 조회한다"는 전제도 깨뜨린다. 그래서 네트워크 호출 없는
    로컬 정규화만 후보로 둔다 — 실제 이름 찾기는 e약은요 라이브 partial-match
    API(_live_fetch_and_ingest)가 이미 담당한다.
    """
    candidates: list[str] = []
    for name in (drug_name, _strip_dosage_form(drug_name)):
        name = (name or "").strip()
        if name and name not in candidates:
            candidates.append(name)
    return candidates


def _lookup_hira_entry(item_name: str, cache: dict[str, HiraDrugMasterEntry | None]) -> HiraDrugMasterEntry | None:
    """e약은요 item_name으로 HIRA 약가마스터를 조회한다 (호출 1회당 품목명별로 1번만 조회).

    CSV 로딩 실패 등 예기치 못한 문제가 생겨도 인용 자체(SourceRef의 e약은요 필드)는
    막지 않도록, 실패하면 조용히 None으로 넘어간다 (표준코드/ATC코드 등이 비는 정도).
    """
    if item_name in cache:
        return cache[item_name]
    try:
        results = search_hira_by_product_name(item_name, limit=1)
    except Exception:  # noqa: BLE001 — HIRA 조회 실패가 인용 생성 자체를 막으면 안 됨
        results = []
    entry = results[0] if results else None
    cache[item_name] = entry
    return entry


def _lookup_permit_entry(item_name: str, cache: dict[str, DrugPermitInfo | None]) -> DrugPermitInfo | None:
    """e약은요 item_name으로 식약처 의약품제품허가정보를 조회한다 (호출 1회당 품목명별로 1번만 조회).

    [2026-07-14 추가] HIRA(약가 등재 상태)와는 다른 개념 — 이건 제조·판매 허가 자체의
    취소여부다. API 오류 등 예기치 못한 문제가 생겨도 인용 자체(SourceRef의 e약은요 필드)는
    막지 않도록, 실패하면 조용히 None으로 넘어간다 (HIRA 조회 실패 처리와 동일한 원칙).
    """
    if item_name in cache:
        return cache[item_name]
    try:
        results = search_permit_info(item_name, num_of_rows=1)
    except Exception:  # noqa: BLE001 — 허가정보 조회 실패가 인용 생성 자체를 막으면 안 됨
        results = []
    entry = results[0] if results else None
    cache[item_name] = entry
    return entry


def _lookup_permit_precautions(
    item_name: str, cache: dict[str, list[tuple[str, str]]]
) -> list[tuple[str, str]]:
    """e약은요 item_name으로 식약처 의약품제품허가정보 상세(NB_DOC_DATA)의 사용상의주의사항을
    (섹션 제목, 본문) 목록으로 조회한다 (호출 1회당 품목명별로 1번만 조회).

    [2026-07-14 추가] 상세 API 실패·XML 파싱 실패는 조용히 빈 리스트로 넘어가 나머지 인용
    (e약은요/HIRA/허가정보)은 그대로 유효해야 한다 (HIRA/허가정보 조회 실패 처리와 동일한 원칙).
    """
    if item_name in cache:
        return cache[item_name]
    try:
        results = search_permit_detail(item_name, num_of_rows=1)
    except Exception:  # noqa: BLE001 — 상세정보 조회 실패가 인용 생성 자체를 막으면 안 됨
        results = []
    sections = parse_doc_sections(results[0].nb_doc_data) if results else []
    cache[item_name] = sections
    return sections


def _lifestyle_context_items(diagnosis: str | None) -> list[dict]:
    """진단명 기준 생활습관 컨텍스트 아이템만 뽑아온다(질병관리청 우선, 없으면 curated 학회
    요약으로 보강) — drug_name 없이 diagnosis만으로 호출 가능하도록 _build_context에서
    분리했다. idx는 호출부(_build_context 또는 generate_lifestyle_guide_for_diagnosis)가
    부여한다.

    [2026-07-21 회의 반영] 이 헬퍼는 의약품 가이드 생성(generate_guide)과 생활습관 안내
    생성(generate_lifestyle_guide_for_diagnosis) 양쪽에서 재사용된다 — 로직은 하나만
    유지하고, "누가 몇 번 호출하는지"만 호출부에서 다르게 제어한다(의약품별이 아니라
    진단명별로 한 번만 부르는 것은 generate_guides_from_medications의 책임).
    """
    items: list[dict] = []
    lifestyle_found = False
    if diagnosis:
        for doc in search_kdca_health_info(diagnosis, k=3):
            lifestyle_found = True
            items.append(
                {
                    "kind": "lifestyle",
                    "text": doc.page_content,
                    "source_ref": LifestyleSourceRef(
                        guideline_id=f"kdca-{doc.metadata['cntnts_sn']}-{doc.metadata['section_sn']}-{doc.metadata['index']}",
                        disease=doc.metadata["title"],
                        category=doc.metadata["section_name"],
                        source=doc.metadata["source"],
                    ),
                }
            )

    if not lifestyle_found:
        for disease_code in _resolve_disease_codes(diagnosis):
            for doc in search_by_disease(disease_code):
                items.append(
                    {
                        "kind": "lifestyle",
                        "text": doc.page_content,
                        "source_ref": LifestyleSourceRef(
                            guideline_id=doc.metadata["guideline_id"],
                            disease=doc.metadata["disease"],
                            category=doc.metadata["category"],
                            source=doc.metadata["source"],
                        ),
                    }
                )
    return items


def _build_context(
    drug_name: str,
    situation: str | None,
    dosage: str = "",
    diagnosis: str | None = None,
    include_lifestyle: bool = True,
) -> list[dict]:
    docs: list[Document] = []
    for candidate in resolve_drug_name_candidates(drug_name):
        docs = search_by_item_name(candidate)
        if not docs:
            docs = _live_fetch_and_ingest(candidate)
        if docs:
            break
    if not docs:
        query = " ".join(part for part in (drug_name, dosage, situation) if part).strip()
        # doc_type="drug" 필터 — 이 컬렉션엔 KDCA 생활지침 문서(item_name 메타데이터 자체가
        # 없음)도 섞여 있어, 필터 없이 검색하면 그 문서가 섞여 들어와 아래 루프가 죽을 수
        # 있었다(2026-07-20 실서버 재현 확인). chunking.py가 새로 태깅한 문서만 이 필터에
        # 걸리므로, 백필 전 기존 문서 대비 아래 .get() 방어도 함께 둔다.
        docs = similarity_search(query, k=settings.TOP_K, filter={"doc_type": "drug"})

    hira_cache: dict[str, HiraDrugMasterEntry | None] = {}
    permit_cache: dict[str, DrugPermitInfo | None] = {}
    permit_precaution_cache: dict[str, list[tuple[str, str]]] = {}
    context_items = []
    item_seqs: dict[str, str] = {}
    for doc in docs:
        item_name = doc.metadata.get("item_name")
        if item_name is None:
            logger.warning("문서에 item_name 메타데이터가 없어 건너뜁니다: %r", doc.metadata)
            continue
        item_seqs.setdefault(item_name, doc.metadata.get("item_seq", ""))
        hira_entry = _lookup_hira_entry(item_name, hira_cache)
        permit_entry = _lookup_permit_entry(item_name, permit_cache)
        context_items.append(
            {
                "kind": "drug",
                "text": doc.page_content,
                "source_ref": SourceRef(
                    item_seq=doc.metadata.get("item_seq", ""),
                    item_name=item_name,
                    field=doc.metadata.get("field_label", ""),
                    update_de=doc.metadata.get("update_de") or None,
                    hira_standard_code=hira_entry.standard_code if hira_entry else None,
                    hira_atc_code=hira_entry.atc_code if hira_entry else None,
                    hira_permit_date=hira_entry.permit_date if hira_entry else None,
                    hira_active=hira_entry.is_active if hira_entry else None,
                    permit_kind_code=permit_entry.permit_kind_code if permit_entry else None,
                    permit_active=permit_entry.is_active if permit_entry else None,
                ),
            }
        )

    # [2026-07-14 추가] 사용상의주의사항(NB_DOC_DATA) — e약은요 문서 여러 개(효능효과/용법 등)가
    # 같은 품목명을 공유하므로, 위 루프에서 모은 품목명당 한 번만 상세 API를 호출해 섹션들을
    # 추가 인용(context_items)으로 붙인다.
    for item_name, item_seq in item_seqs.items():
        hira_entry = hira_cache.get(item_name)
        permit_entry = permit_cache.get(item_name)
        for section_title, section_text in _lookup_permit_precautions(item_name, permit_precaution_cache):
            context_items.append(
                {
                    "kind": "drug",
                    "text": section_text,
                    "source_ref": SourceRef(
                        item_seq=item_seq,
                        item_name=item_name,
                        field=f"사용상의주의사항 - {section_title}",
                        hira_standard_code=hira_entry.standard_code if hira_entry else None,
                        hira_atc_code=hira_entry.atc_code if hira_entry else None,
                        hira_permit_date=hira_entry.permit_date if hira_entry else None,
                        hira_active=hira_entry.is_active if hira_entry else None,
                        permit_kind_code=permit_entry.permit_kind_code if permit_entry else None,
                        permit_active=permit_entry.is_active if permit_entry else None,
                    ),
                }
            )

    # [2026-07-21 버그수정] data/lifestyle_guidelines.json(4개 질환 curated set)은 실제로는
    # 대한고혈압학회/대한당뇨병학회/한국지질·동맥경화학회/대한신장학회 등 학회 진료지침을
    # AI 챗봇 요약 대화로 정리한 2차 가공 데이터다(README_rag.md에 "실제 서비스 반영 전 원문과
    # 반드시 대조 검증"이 필요하다고 명시된 미검증 상태) — 11건 중 단 2건만 질병관리청을
    # 인용하고 당뇨병/이상지질혈증/만성콩팥병은 질병관리청 인용이 아예 없다. 생활습관(음식/
    # 운동/주의사항) 안내는 질병관리청 국가건강정보포털 실제 수집분(search_kdca_health_info)을
    # 최우선 소스로 삼고, 그걸로 못 찾을 때만 이 curated 학회 요약으로 보강한다.
    #
    # [2026-07-21 회의 반영] include_lifestyle=False(generate_guide가 씀)면 이 약의 컨텍스트에
    # 생활습관 항목을 아예 섞지 않는다 — 생활습관 안내는 별도로(진단명당 한 번만) 생성한다.
    if include_lifestyle:
        context_items += _lifestyle_context_items(diagnosis)

    for idx, item in enumerate(context_items, start=1):
        item["idx"] = idx
    return context_items


def _context_text(context_items: list[dict]) -> str:
    return "\n".join(f"[{item['idx']}] {item['text']}" for item in context_items)


def _dry_run_guide(drug_name: str, context_items: list[dict]) -> GuideResponse:
    """[2026-07-21] generate_guide()는 이제 include_lifestyle=False로 컨텍스트를 만들므로
    context_items는 항상 전부 kind=="drug"다 — 별도 필터링이 필요 없다."""
    return GuideResponse(
        drug_name=drug_name,
        medication_guide="\n".join(item["text"] for item in context_items) or "검색된 정보가 없습니다.",
        precautions=_fallback_precautions_from_context(context_items),
        source_refs=[item["source_ref"] for item in context_items],
        disclaimer=settings.DISCLAIMER,
        self_consistency_score=None,
        review_required=True,
        review_reason="OPENAI_API_KEY 미설정 (dry-run 모드: 검색 결과만 반환)",
        review_flags=["dry_run"],
    )


def _fallback_precautions_from_context(context_items: list[dict], limit: int = 3) -> list[str]:
    """허가사항의 사용상의주의사항 근거가 있는데 LLM이 precautions를 비워 보내면 짧게 보강한다."""
    results: list[str] = []
    seen: set[str] = set()
    for item in context_items:
        source_ref = item.get("source_ref")
        field = getattr(source_ref, "field", "") if source_ref is not None else ""
        if not any(keyword in field for keyword in ("주의", "경고", "금기", "상호작용")):
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue
        if len(text) > 180:
            text = f"{text[:180].rstrip()}..."
        if text in seen:
            continue
        seen.add(text)
        results.append(text)
        if len(results) >= limit:
            break
    return results


def _fallback_lifestyle_guide_from_context(context_items: list[dict], limit: int = 3) -> list[str]:
    """생활습관 근거가 있는데 LLM이 diet/exercise/other를 전부 비워 보내면 검색 문구로 보강한다.

    [2026-07-23 수정] 카테고리 구분 없이 한 단락(str)이던 걸 목록(list[str])으로 바꿨다 —
    호출부가 이 결과를 other.recommended에 그대로 담는다(어느 카테고리인지 LLM도 못 정한
    상황이라 "그 외"로 분류)."""
    lines: list[str] = []
    seen: set[str] = set()
    for item in context_items:
        if item.get("kind") != "lifestyle":
            continue
        text = " ".join(str(item.get("text") or "").split())
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(text)
        if len(lines) >= limit:
            break
    return lines


def _llm_generate_once(
    chat,
    drug_name: str,
    situation: str | None,
    dosage: str,
    context_text: str,
    diagnosis: str | None = None,
) -> dict:
    user_prompt = (
        f"약품명: {drug_name}\n"
        f"용량: {dosage or '미상'}\n"
        + (f"진단명: {diagnosis}\n" if diagnosis else "")
        + f"환자 상황: {situation or '특이사항 없음'}\n\n"
        f"[참고자료]\n{context_text}"
    )
    response = chat.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    return json.loads(response.content)


def generate_guide(
    drug_name: str,
    situation: str | None = None,
    dosage: str = "",
    diagnosis: str | None = None,
) -> GuideResponse:
    # [2026-07-21 회의 반영] include_lifestyle=False — 이 약의 컨텍스트에 생활습관 항목을
    # 섞지 않는다. diagnosis는 여전히 situation 텍스트(진단명: ...)로 LLM에 전달돼 이 약의
    # 복약 안내 자체를 더 맥락에 맞게 만드는 데는 쓰이지만, 생활습관 안내 생성에는 관여하지
    # 않는다(그건 generate_lifestyle_guide_for_diagnosis가 진단명당 한 번만 담당).
    context_items = _build_context(drug_name, situation, dosage=dosage, diagnosis=diagnosis, include_lifestyle=False)
    if not context_items:
        raise NoContextFoundError(f"'{drug_name}'에 대한 식약처 데이터를 찾을 수 없습니다. 먼저 ingest를 실행하세요.")

    if not settings.OPENAI_API_KEY:
        return _dry_run_guide(drug_name, context_items)

    from langchain_openai import ChatOpenAI

    ref_by_idx = {item["idx"]: item for item in context_items}
    context_text = _context_text(context_items)

    chat = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.4,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    raw_candidates = [
        _llm_generate_once(chat, drug_name, situation, dosage, context_text, diagnosis=diagnosis)
        for _ in range(settings.SELF_CONSISTENCY_SAMPLES)
    ]

    candidate_texts = [c.get("medication_guide") or "" for c in raw_candidates]
    best_idx, avg_similarity = pick_consistent_answer(candidate_texts)
    best = raw_candidates[best_idx]

    # LLM이 JSON에서 해당 키를 null로 반환할 수 있으므로 (get의 default는 이때 적용되지 않음)
    # `or`로 다시 빈 값으로 정규화한다. 또한 배열 대신 단일 정수(예: "source_refs": 2)를
    # 반환하면 순회 시 TypeError로 생성이 중단되므로 리스트로 감싼다.
    raw_refs = best.get("source_refs") or []
    if not isinstance(raw_refs, list):
        raw_refs = [raw_refs]
    # 원소가 dict/list 같은 해시 불가능한 값이면 `i in ref_by_idx`가 TypeError로
    # 생성을 중단시키므로, 정수 참고번호만 대조한다 (그 외는 무시 -> 인용 없음이면 아래에서 검토 표시).
    # context_items가 전부 kind=="drug"이므로(include_lifestyle=False) kind 필터가 필요 없다.
    used_items = [ref_by_idx[i] for i in raw_refs if isinstance(i, int) and i in ref_by_idx]
    source_refs = [item["source_ref"] for item in used_items]

    # precautions는 list[str] 필드다. LLM이 항목이 하나뿐일 때 배열 대신 단일 문자열
    # (예: "precautions": "주의하세요")을 반환하면 GuideResponse 생성 시 pydantic이
    # ValidationError로 가이드 생성 전체를 중단시키므로, 리스트로 정규화한다.
    raw_precautions = best.get("precautions") or []
    if not isinstance(raw_precautions, list):
        raw_precautions = [raw_precautions]
    precautions = [str(p) for p in raw_precautions if str(p).strip()]
    if not precautions:
        precautions = _fallback_precautions_from_context(used_items or context_items)

    # hallucination 방어: 인용(source_refs)이 하나도 없으면 참고자료 근거 없이 생성된
    # 답변이므로, self-consistency 점수와 무관하게 사람이 검토하도록 표시한다.
    reasons: list[str] = []
    flags: list[str] = []
    if not used_items:
        reasons.append("참고자료 인용(source_refs)이 없어 근거를 확인할 수 없습니다.")
        flags.append("no_citation")
    if avg_similarity < settings.SELF_CONSISTENCY_SIMILARITY_THRESHOLD:
        reasons.append(
            f"self-consistency 점수({avg_similarity:.2f})가 임계값({settings.SELF_CONSISTENCY_SIMILARITY_THRESHOLD}) 미만입니다."
        )
        flags.append("low_self_consistency")

    return GuideResponse(
        drug_name=drug_name,
        medication_guide=best.get("medication_guide") or "",
        precautions=precautions,
        source_refs=source_refs,
        disclaimer=settings.DISCLAIMER,
        self_consistency_score=avg_similarity,
        review_required=bool(reasons),
        review_reason=" ".join(reasons) if reasons else None,
        review_flags=flags,
    )


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _parse_lifestyle_category(raw: object) -> LifestyleCategoryGuide:
    """LLM이 준 diet/exercise/other 중 하나를 안전하게 LifestyleCategoryGuide로 변환한다.
    형식이 어긋나면(dict가 아니거나 리스트가 아닌 값 등) 지어내지 않고 빈 카테고리로 둔다."""
    if not isinstance(raw, dict):
        return LifestyleCategoryGuide()
    return LifestyleCategoryGuide(recommended=_str_list(raw.get("recommended")), avoid=_str_list(raw.get("avoid")))


def _lifestyle_category_is_empty(category: LifestyleCategoryGuide) -> bool:
    return not category.recommended and not category.avoid


def _flatten_lifestyle_candidate(candidate: dict) -> str:
    """self-consistency 비교용 — diet/exercise/other의 모든 항목을 한 문자열로 펼친다."""
    parts: list[str] = []
    for key in ("diet", "exercise", "other"):
        raw_cat = candidate.get(key)
        if isinstance(raw_cat, dict):
            parts.extend(_str_list(raw_cat.get("recommended")))
            parts.extend(_str_list(raw_cat.get("avoid")))
    return "\n".join(parts)


def generate_lifestyle_guide_for_diagnosis(diagnosis: str | None) -> LifestyleGuideResult:
    """진단명 기준으로 생활습관 안내를 생성한다 — 의약품과 무관하며, 이 함수는 drug_name을
    받지 않는다(구조적으로 "의약품별"이 아니라 "진단명별" 생성임을 강제).

    [2026-07-21 회의 반영] generate_guides_from_medications()가 처방전의 고유 진단명마다
    이 함수를 정확히 1회씩만 호출한다 — 같은 진단명의 약이 여러 개 있어도 중복 생성하지 않는다.

    진단명이 없거나(diagnosis=None/빈 문자열) 매칭되는 생활지침을 하나도 못 찾으면, 지어내지
    않고 안전한 일반 안내 문구로 폴백한다(hallucination 방지 — SYSTEM_PROMPT와 동일한 원칙).
    """
    if not diagnosis:
        return LifestyleGuideResult(
            diagnosis="",
            other=LifestyleCategoryGuide(
                recommended=["진단명 정보가 부족해 자세한 생활습관 안내를 드리기 어려워요. 처방전에 진단명을 등록하면 더 정확한 안내를 받을 수 있어요."]
            ),
            source_refs=[],
            review_required=True,
            review_reason="진단명 미상 — 안전한 일반 안내로 대체",
            review_flags=["no_diagnosis"],
        )

    context_items = _lifestyle_context_items(diagnosis)
    for idx, item in enumerate(context_items, start=1):
        item["idx"] = idx

    if not context_items:
        return LifestyleGuideResult(
            diagnosis=diagnosis,
            other=LifestyleCategoryGuide(
                recommended=[f"'{diagnosis}'에 대한 생활습관 안내 자료를 아직 찾지 못했어요. 담당 의료진과 상담해 주세요."]
            ),
            source_refs=[],
            review_required=True,
            review_reason=f"'{diagnosis}'에 대한 생활지침 검색 결과 없음",
            review_flags=["no_lifestyle_context"],
        )

    if not settings.OPENAI_API_KEY:
        return LifestyleGuideResult(
            diagnosis=diagnosis,
            other=LifestyleCategoryGuide(recommended=[item["text"] for item in context_items]),
            source_refs=[item["source_ref"] for item in context_items],
            review_required=True,
            review_reason="OPENAI_API_KEY 미설정 (dry-run 모드: 검색 결과만 반환)",
            review_flags=["dry_run"],
        )

    from langchain_openai import ChatOpenAI

    ref_by_idx = {item["idx"]: item for item in context_items}
    context_text = _context_text(context_items)
    user_prompt = f"진단명: {diagnosis}\n\n[참고자료]\n{context_text}"

    chat = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.4,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    raw_candidates = [
        json.loads(
            chat.invoke(
                [
                    {"role": "system", "content": LIFESTYLE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            ).content
        )
        for _ in range(settings.SELF_CONSISTENCY_SAMPLES)
    ]
    candidate_texts = [_flatten_lifestyle_candidate(c) for c in raw_candidates]
    best_idx, avg_similarity = pick_consistent_answer(candidate_texts)
    best = raw_candidates[best_idx]

    raw_refs = best.get("source_refs") or []
    if not isinstance(raw_refs, list):
        raw_refs = [raw_refs]
    used_items = [ref_by_idx[i] for i in raw_refs if isinstance(i, int) and i in ref_by_idx]
    source_refs = [item["source_ref"] for item in used_items]

    reasons: list[str] = []
    flags: list[str] = []
    if not used_items:
        reasons.append("참고자료 인용(source_refs)이 없어 근거를 확인할 수 없습니다.")
        flags.append("no_citation")
    if avg_similarity < settings.SELF_CONSISTENCY_SIMILARITY_THRESHOLD:
        reasons.append(
            f"self-consistency 점수({avg_similarity:.2f})가 임계값({settings.SELF_CONSISTENCY_SIMILARITY_THRESHOLD}) 미만입니다."
        )
        flags.append("low_self_consistency")

    diet = _parse_lifestyle_category(best.get("diet"))
    exercise = _parse_lifestyle_category(best.get("exercise"))
    other = _parse_lifestyle_category(best.get("other"))

    if _lifestyle_category_is_empty(diet) and _lifestyle_category_is_empty(exercise) and _lifestyle_category_is_empty(other):
        fallback_lines = _fallback_lifestyle_guide_from_context(used_items or context_items)
        if fallback_lines:
            other = LifestyleCategoryGuide(recommended=fallback_lines)
            reasons.append("LLM이 생활습관 안내 항목을 비워 검색 근거 문구로 보강했습니다.")
            flags.append("empty_lifestyle_fallback")

    if _lifestyle_category_is_empty(diet) and _lifestyle_category_is_empty(exercise) and _lifestyle_category_is_empty(other):
        other = LifestyleCategoryGuide(
            recommended=[f"'{diagnosis}'에 대한 생활습관 안내를 생성하지 못했어요. 담당 의료진과 상담해 주세요."]
        )
        reasons.append("생활습관 안내 항목이 비어 있습니다.")
        flags.append("empty_lifestyle_guide")

    return LifestyleGuideResult(
        diagnosis=diagnosis,
        diet=diet,
        exercise=exercise,
        other=other,
        source_refs=source_refs,
        review_required=bool(reasons),
        review_reason=" ".join(reasons) if reasons else None,
        review_flags=flags,
    )


def _merge_ocr_confidence(guide: GuideResponse, confidence: float) -> GuideResponse:
    """OCR 개별 인식 신뢰도를 최종 검토 판정에 병합한다.

    OCR의 자체 review_required는 overall_confidence(전체 평균)만 보고 개별 약의 저신뢰를
    놓친다 (예: 평균 0.85는 통과해도 그 안의 특정 약 하나는 0.78일 수 있음). 이 함수는
    그 판정 한계에 대한 보완 통제(compensating control)이지, generate_guide()의 인용/
    self-consistency 로직을 대체하지 않는다 (core 시그니처는 건드리지 않음).

    OCR 계약상 confidence는 항상 float으로 채워지고 키가 생략되지 않으므로(None이 아님),
    unknown과 low를 값으로 구분한다:
      - 정확히 0.0  -> Tesseract 폴백처럼 신뢰도 자체가 제공되지 않은 경우 ("unavailable")
      - (0.0, 임계값) -> 인식은 됐지만 신뢰도가 낮은 경우 ("low")
      - CLOVA는 모든 항목에 overall_confidence를 동일하게 복제하므로, 이 경로에서
        "개별" 체크는 사실상 처방전 전체 신뢰도 체크와 같다 (무해하지만 개별성은 없음).
    """
    threshold = settings.OCR_CONFIDENCE_REVIEW_THRESHOLD
    if confidence == 0.0:
        flag, reason = "ocr_confidence_unavailable", "OCR 인식 신뢰도가 제공되지 않았습니다(미상)."
    elif confidence < threshold:
        flag, reason = "ocr_low_confidence", f"OCR 인식 신뢰도({confidence:.2f})가 임계값({threshold})보다 낮습니다."
    else:
        return guide.model_copy(update={"ocr_confidence": confidence})

    merged_reason = " ".join(part for part in (guide.review_reason, reason) if part)
    return guide.model_copy(
        update={
            "ocr_confidence": confidence,
            "review_required": True,
            "review_reason": merged_reason,
            "review_flags": [*guide.review_flags, flag],
        }
    )


def _check_dur_taboo(drug_name: str, other_drug_names: list[str]) -> list[DurWarning]:
    """이 약이 같은 처방전의 다른 약과 DUR 병용금기 관계인지 확인한다.

    DUR 병용금기는 두 약 사이의 관계이므로, 이 처방전에 실제로 함께 있는 약(other_drug_names)
    중 하나가 DUR이 알려주는 금기 상대(mixture_item_name)와 일치할 때만 경고를 만든다 —
    단순히 "이 약에 금기 상대가 존재한다"만으로는 이 환자에게 실제로 해당하는지 알 수 없다.

    [2026-07-13] DUR API는 활용신청 승인 대기라 dur_master.py의 로컬 CSV 조회를 쓴다.
    CSV 파일 부재(FileNotFoundError) 등 어떤 이유로든 조회가 실패해도 가이드 생성 자체를
    막으면 안 되므로 조용히 빈 리스트로 넘어간다 (_lookup_hira_entry와 동일한 fail-safe 원칙).
    """
    if not other_drug_names:
        return []
    taboo_entries: list = []
    for candidate in resolve_drug_name_candidates(drug_name):
        try:
            taboo_entries = search_usjnt_taboo(candidate)
        except Exception:  # noqa: BLE001 — DUR 조회 실패가 가이드 생성 자체를 막으면 안 됨
            taboo_entries = []
        if taboo_entries:
            break

    # DUR CSV는 브랜드(제품) 단위라, 같은 성분의 약이 여러 제조사 제품으로 등재돼 있으면
    # 같은 경고가 수십~수천 건 중복될 수 있다(예: "메토트렉세이트" 주사제만 제조사별로 여러 종).
    # 그래서 CSV의 브랜드명이 아니라 "이 처방전에 실제로 적힌 약 이름"으로 경고를 표시하고,
    # (그 약, 사유) 조합 기준으로 한 번만 보여준다.
    seen: set[tuple[str, str]] = set()
    warnings: list[DurWarning] = []
    for entry in taboo_entries:
        mixture_name = entry.mixture_item_name
        if not mixture_name:
            continue
        matched_other = next(
            (other for other in other_drug_names if other and (mixture_name in other or other in mixture_name)),
            None,
        )
        if matched_other is None:
            continue
        key = (matched_other, entry.prohbt_content or "")
        if key in seen:
            continue
        seen.add(key)
        warnings.append(DurWarning(mixture_item_name=matched_other, prohbt_content=entry.prohbt_content))
    return warnings


def _check_dur_cautions(drug_name: str) -> list[DurCaution]:
    """이 약 자체의 DUR 주의/금기 정보(노인주의/연령금기/임부금기)를 조회한다.

    _check_dur_taboo(병용금기)와 달리 다른 약과 무관하게 이 약 하나만으로 판단되므로
    other_drug_names가 필요 없다. 각 조회가 실패해도(CSV 부재 등) 나머지 조회와 가이드
    생성 자체는 막지 않는다 (_check_dur_taboo와 동일한 fail-safe 원칙).
    """
    cautions: list[DurCaution] = []
    candidates = resolve_drug_name_candidates(drug_name)
    for search_fn in (search_elderly_caution, search_age_taboo, search_pregnancy_taboo):
        for candidate in candidates:
            try:
                found = search_fn(candidate)
            except Exception:  # noqa: BLE001 — DUR 조회 실패가 가이드 생성 자체를 막으면 안 됨
                found = []
            if found:
                cautions.extend(found)
                break
    return cautions


def generate_guide_from_medication(medication, other_drug_names: list[str] | None = None) -> GuideResponse:
    """OCR 파트(ocr_interface.MedicationItem)의 출력을 그대로 받아 가이드를 생성하는 어댑터.

    dataclass 인스턴스, 그 dict 표현(`MedicationItem.__dict__`), 또는 동일한 필드명의
    dict 무엇이든 받는다. situation은 진단명·복용법·약효분류를 조합해 자동 구성하고,
    diagnosis는 원문 그대로 별도 전달해 만성질환 생활지침 검색(disease_code 매칭)에 사용한다.

    other_drug_names: 같은 처방전에 함께 있는 다른 약들의 이름(DUR 병용금기 대조용).
    generate_guides_from_medications()가 배치 처리 시 채워서 넘긴다 — 단일 약만 다룰 때는
    비교 대상이 없으므로 생략(None)해도 된다.
    """
    if not isinstance(medication, dict):
        medication = medication.__dict__
    item = MedicationInput.model_validate(medication)

    situation_parts = [
        f"진단: {item.diagnosis}" if item.diagnosis else None,
        f"복용법: {item.frequency}" if item.frequency else None,
        f"약효분류: {item.drug_class}" if item.drug_class else None,
    ]
    situation = ", ".join(part for part in situation_parts if part) or None

    guide = generate_guide(item.drug_name, situation=situation, dosage=item.dosage, diagnosis=item.diagnosis or None)
    guide = _merge_ocr_confidence(guide, item.confidence)

    dur_warnings = _check_dur_taboo(item.drug_name, other_drug_names or [])
    if dur_warnings:
        reason = "병용 중인 다른 약과 DUR 병용금기 경고가 있어 확인이 필요합니다."
        merged_reason = " ".join(part for part in (guide.review_reason, reason) if part)
        guide = guide.model_copy(
            update={
                "dur_warnings": dur_warnings,
                "review_required": True,
                "review_reason": merged_reason,
                "review_flags": [*guide.review_flags, "dur_taboo_warning"],
            }
        )

    dur_cautions = _check_dur_cautions(item.drug_name)
    if dur_cautions:
        reason = "DUR 노인주의/연령금기/임부금기 등 확인이 필요한 주의사항이 있습니다."
        merged_reason = " ".join(part for part in (guide.review_reason, reason) if part)
        guide = guide.model_copy(
            update={
                "dur_cautions": dur_cautions,
                "review_required": True,
                "review_reason": merged_reason,
                "review_flags": [*guide.review_flags, "dur_caution"],
            }
        )
    return guide


def generate_guides_from_medications(medications: list) -> tuple[list[GuideResponse], list[LifestyleGuideResult]]:
    """OCR `OCRResult.medications` 리스트를 순회해 항목별 의약품 가이드를 생성하고(실패 격리),
    진단명 기준 생활습관 안내를 별도로 생성한다.

    Returns:
        (guides, lifestyle_guides) — guides는 medications와 1:1(의약품별). lifestyle_guides는
        medications의 고유 진단명 집합 기준(1:1이 아님) — 여러 약이 같은 진단명을 공유해도
        그 진단명의 생활습관 안내는 한 번만 생성된다(2026-07-21 회의 반영: "의약품별이 아니라
        진단명 기준"). 진단명이 하나도 없으면(전부 미상) 안전한 폴백 안내 1건만 반환한다.

    비용 주의: generate_guide()/generate_lifestyle_guide_for_diagnosis()는 호출당
    SELF_CONSISTENCY_SAMPLES(기본 3)회 LLM 호출을 한다. 배치 비용은 대략
    3 * (약 개수 + 고유 진단명 개수)회 직렬 호출이다.

    항목 하나가 NoContextFoundError 등으로 실패해도 나머지 약 처리를 막지 않도록,
    실패한 항목은 review_required=True인 GuideResponse로 대체한다. 집계/통계가 필요한
    BatchGuideResponse류 스키마는 실제 ai_worker 이식 시점까지 보류한다 (YAGNI).

    각 항목 처리 시 나머지 약 이름들을 other_drug_names로 함께 넘겨 DUR 병용금기 대조에 쓴다.
    """
    drug_names = [
        (medication.get("drug_name") if isinstance(medication, dict) else getattr(medication, "drug_name", None))
        for medication in medications
    ]

    guides: list[GuideResponse] = []
    for idx, medication in enumerate(medications):
        try:
            other_names = [name for i, name in enumerate(drug_names) if i != idx and name]
            guides.append(generate_guide_from_medication(medication, other_drug_names=other_names))
        except Exception as exc:
            drug_name = (
                medication.get("drug_name") if isinstance(medication, dict) else getattr(medication, "drug_name", "")
            ) or "(미상)"
            logger.exception("가이드 생성 실패: drug_name=%s", drug_name)
            guides.append(
                GuideResponse(
                    drug_name=drug_name,
                    medication_guide="",
                    disclaimer=settings.DISCLAIMER,
                    review_required=True,
                    review_reason=f"가이드 생성 실패: {exc}",
                    review_flags=["generation_error"],
                )
            )

    # [2026-07-21 회의 반영] 진단명 기준 생활습관 안내 — 고유 진단명(첫 등장 순서 유지)마다
    # 정확히 한 번씩만 생성한다. 전부 미상이면 폴백 안내 1건(diagnosis="")만 반환한다.
    seen_diagnoses: list[str] = []
    for medication in medications:
        raw_diagnosis = (
            medication.get("diagnosis") if isinstance(medication, dict) else getattr(medication, "diagnosis", "")
        ) or ""
        diagnosis = raw_diagnosis.strip()
        if diagnosis and diagnosis not in seen_diagnoses:
            seen_diagnoses.append(diagnosis)

    if seen_diagnoses:
        lifestyle_guides = [generate_lifestyle_guide_for_diagnosis(d) for d in seen_diagnoses]
    else:
        lifestyle_guides = [generate_lifestyle_guide_for_diagnosis(None)]

    return guides, lifestyle_guides


def generate_guides_from_ocr_result(ocr_result) -> tuple[list[GuideResponse], list[LifestyleGuideResult]]:
    """OCR `OCRResult`(dataclass 또는 dict) 전체를 받는 검증된 배치 진입점.

    내부 medications만 꺼내 generate_guides_from_medications()에 위임한다.
    """
    medications = ocr_result["medications"] if isinstance(ocr_result, dict) else ocr_result.medications
    return generate_guides_from_medications(medications)
