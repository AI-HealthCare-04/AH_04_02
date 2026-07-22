from pydantic import BaseModel, Field


class DrugInfo(BaseModel):
    """식약처 DrbEasyDrugInfoService getDrbEasyDrugList 응답 1개 품목."""

    item_seq: str = Field(alias="itemSeq")
    item_name: str = Field(alias="itemName")
    entp_name: str = Field(alias="entpName")
    efcy_qesitm: str | None = Field(default=None, alias="efcyQesitm")
    use_method_qesitm: str | None = Field(default=None, alias="useMethodQesitm")
    atpn_warn_qesitm: str | None = Field(default=None, alias="atpnWarnQesitm")
    atpn_qesitm: str | None = Field(default=None, alias="atpnQesitm")
    intrc_qesitm: str | None = Field(default=None, alias="intrcQesitm")
    se_qesitm: str | None = Field(default=None, alias="seQesitm")
    deposit_method_qesitm: str | None = Field(default=None, alias="depositMethodQesitm")
    update_de: str | None = Field(default=None, alias="updateDe")

    model_config = {"populate_by_name": True}


# DrugInfo 필드명 -> (사람이 읽는 라벨, 청크 필드 태그)
DRUG_FIELD_LABELS: dict[str, str] = {
    "efcy_qesitm": "효능·효과",
    "use_method_qesitm": "용법·용량",
    "atpn_warn_qesitm": "경고",
    "atpn_qesitm": "주의사항",
    "intrc_qesitm": "상호작용",
    "se_qesitm": "부작용",
    "deposit_method_qesitm": "보관법",
}


# [2026-07-14] 활용신청 승인되어 재활성화 — e약은요·약가마스터와 조율할 필요 없이 그대로
# 세 번째 인용 소스로 추가한다(HIRA와 마찬가지로 SourceRef 보강 필드로 병합).
class DrugPermitInfo(BaseModel):
    """식약처 DrugPrdtPrmsnInfoService07 getDrugPrdtPrmsnInq07 응답 1개 품목.

    e약은요(DrugInfo)와 원천이 다른 별도 API — 효능효과 등 설명문 텍스트는 없고,
    허가번호·허가일자·허가/신고 구분·취소여부 같은 규제 메타데이터만 담는다.
    "정식으로 허가·신고되어 현재 정상 상태인 의약품인지" 검증 용도.

    [2026-07-14] 실제 API 호출로 필드명 확인 완료(item_name 쿼리 파라미터, 응답 필드
    전부 이전 설계 그대로 일치).
    """

    item_seq: str = Field(alias="ITEM_SEQ")
    item_name: str = Field(alias="ITEM_NAME")
    item_eng_name: str | None = Field(default=None, alias="ITEM_ENG_NAME")
    entp_name: str = Field(alias="ENTP_NAME")
    entp_eng_name: str | None = Field(default=None, alias="ENTP_ENG_NAME")
    item_permit_date: str | None = Field(default=None, alias="ITEM_PERMIT_DATE")
    specialty_pblc: str | None = Field(default=None, alias="SPCLTY_PBLC")  # 전문/일반의약품
    product_type: str | None = Field(default=None, alias="PRDUCT_TYPE")  # 예: "[01140]해열.진통.소염제"
    permit_no: str | None = Field(default=None, alias="PRDUCT_PRMISN_NO")
    ingr_name: str | None = Field(default=None, alias="ITEM_INGR_NAME")
    permit_kind_code: str | None = Field(default=None, alias="PERMIT_KIND_CODE")  # "허가" | "신고"
    cancel_date: str | None = Field(default=None, alias="CANCEL_DATE")
    cancel_name: str | None = Field(default=None, alias="CANCEL_NAME")  # "정상" | 취소·취하 상태명

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @property
    def is_active(self) -> bool:
        """취소·취하되지 않고 현재 정상 허가 상태인지 (cancel_date가 없고 cancel_name이 '정상')."""
        return self.cancel_date is None and self.cancel_name == "정상"


# [2026-07-14 추가] 목록 조회(getDrugPrdtPrmsnInq07, DrugPermitInfo)와 별개 엔드포인트 —
# 사용자가 "제품허가정보로 사용상의 주의사항 조회 가능한지" 확인 요청해서 찾음.
class DrugPermitDetail(BaseModel):
    """식약처 DrugPrdtPrmsnInfoService07 getDrugPrdtPrmsnDtlInq06 응답 1개 품목.

    목록 조회(DrugPermitInfo)와 달리 효능효과/용법용량/사용상의주의사항/임부수유부주의사항
    원문(각 XX_DOC_DATA)을 담고 있다 — 이 4개 필드는 `<DOC><SECTION><ARTICLE
    title="...">문단들</ARTICLE></SECTION></DOC>` 형태의 구조화 XML 문자열이라
    `mfds_client.parse_doc_sections()`로 파싱해야 사람이 읽을 텍스트가 된다.
    """

    item_seq: str = Field(alias="ITEM_SEQ")
    item_name: str = Field(alias="ITEM_NAME")
    entp_name: str | None = Field(default=None, alias="ENTP_NAME")
    ee_doc_data: str | None = Field(default=None, alias="EE_DOC_DATA")  # 효능효과
    ud_doc_data: str | None = Field(default=None, alias="UD_DOC_DATA")  # 용법용량
    nb_doc_data: str | None = Field(default=None, alias="NB_DOC_DATA")  # 사용상의주의사항
    pn_doc_data: str | None = Field(default=None, alias="PN_DOC_DATA")  # 임부·수유부 주의사항(없는 품목 많음)

    model_config = {"populate_by_name": True, "extra": "ignore"}


class HiraDrugMasterEntry(BaseModel):
    """건강보험심사평가원 약가마스터·의약품표준코드 CSV(backend/data/hira_drug_master_20251031.csv) 1개 행.

    e약은요와 원천이 다른 별도 로컬 데이터 — 효능효과 등 설명문은 없지만, 표준코드·ATC코드·
    허가일자·취소일자 등 e약은요에 없는 코드성 정보를 담고 있어 품목 식별/검증 보조용으로 쓴다.
    """

    item_name: str = Field(alias="한글상품명")
    entp_name: str | None = Field(default=None, alias="업체명")
    spec: str | None = Field(default=None, alias="약품규격")
    dosage_form: str | None = Field(default=None, alias="제형구분")
    item_code: str | None = Field(default=None, alias="품목기준코드")  # 품목기준코드(=권순현 drug_code와 동일 개념)
    permit_date: str | None = Field(default=None, alias="품목허가일자")  # YYYY-MM-DD
    etc_otc: str | None = Field(default=None, alias="전문일반구분")  # 예: "전문의약품"/"일반의약품"/"한약재"
    standard_code: str | None = Field(default=None, alias="표준코드")
    atc_code: str | None = Field(default=None, alias="국제표준코드(ATC코드)")
    cancel_date: str | None = Field(default=None, alias="취소일자")

    model_config = {"populate_by_name": True}

    @property
    def is_active(self) -> bool:
        """취소일자가 없으면(빈 문자열/None) 현재 정상 등재 상태로 본다."""
        return not self.cancel_date


class DurTabooInfo(BaseModel):
    """건강보험심사평가원 DUR(의약품안전사용서비스) 병용금기 CSV 1개 관계.

    [2026-07-13] 원래 식약처 DURPrdlstInfoService03 getUsjntTabooInfoList03 API로
    연동하려 했으나 활용신청 승인 대기 상태(403 Forbidden)라, 공공데이터포털에서 받은
    로컬 CSV(dur_master.py)로 대체했다. "이 약(item_name)과 이 약(mixture_item_name)을
    같이 먹으면 안 된다"는 금기 쌍 하나를 나타낸다.
    """

    item_name: str
    mixture_item_name: str
    prohbt_content: str | None = None  # 금기 사유 설명 (CSV의 "상세정보" 컬럼)


class DurWarning(BaseModel):
    """같은 처방전 안의 다른 약과 DUR 병용금기 관계가 확인됐을 때만 채워지는 경고.

    SourceRef(단일 약 인용)와 달리 두 약 사이의 관계를 나타내므로 별도 모델로 둔다.
    """

    mixture_item_name: str = Field(description="병용금기 상대 약물명 (처방전에 실제로 함께 있는 약)")
    prohbt_content: str | None = Field(default=None, description="금기 사유")
    source: str = "식약처 DUR(의약품안전사용서비스)"


class DurCaution(BaseModel):
    """DUR 병용금기를 제외한 나머지 카테고리 — "약 하나"에 대한 주의/금기 정보.

    [2026-07-13] 병용금기(DurWarning, 두 약 사이의 관계)와 달리 이 4개 카테고리는
    다른 약과 무관하게 그 약 자체의 속성이라 처방전에 이 약 하나만 있어도 표시된다:
    - 노인주의 / 노인주의(해열진통소염제): 고령 환자에게 특히 주의가 필요한 약 (이 서비스의
      주 사용자층인 고령 만성질환자와 직접 관련)
    - 연령금기: 특정 연령대(주로 소아·청소년) 사용 금기
    - 임부금기: 임부 사용 금기(금기등급 포함)
    환자의 실제 나이·임신 여부를 이 시스템이 알지 못하므로, "이 환자에게 해당되는지"는
    판단하지 않고 "이 약에 이런 조건부 주의사항이 있다"는 사실만 정보성으로 전달한다.
    """

    item_name: str
    category: str = Field(description='"노인주의" | "노인주의(해열진통소염제)" | "연령금기" | "임부금기"')
    detail: str | None = Field(default=None, description="금기/주의 사유 설명")
    extra: str | None = Field(default=None, description="카테고리별 부가 정보 (연령금기의 연령 조건, 임부금기의 금기등급 등)")


class LifestyleGuideline(BaseModel):
    """만성질환 생활지침 항목 (질병관리청·학회 진료지침 기반, 도메인 지식 참고자료).

    2차 가공(AI 요약) 출처를 사람이 정리한 데이터이므로, 실제 서비스 반영 전
    각 학회 진료지침 원문 대조 검증이 필요하다.
    """

    id: str
    disease: str
    disease_code: str
    category: str
    rule: str
    source: str


class KdcaHealthInfoSection(BaseModel):
    """질병관리청 국가건강정보포털 Open API(healthInfoNew)에서 수집한 건강정보 1개 항목의
    섹션 하나. 원본 응답의 cntntsClList 배열을 펼친 것 — 같은 cntnts_sn(질환/주제)에
    section_sn(개요정의/증상/치료 등)이 여러 개 있고, 같은 section_sn 안에서도 텍스트/이미지
    블록이 나뉘어 여러 행으로 반복될 수 있어 등장 순서(index)까지 있어야 완전히 유일하다.
    """

    cntnts_sn: str
    title: str
    section_name: str
    section_sn: str
    index: int
    html: str
    updated_at: str
    source: str
    source_url: str


class MedicationInput(BaseModel):
    """OCR 파트(AH_04_02_soonhyun/ocr_interface.py)의 MedicationItem과 필드명을 맞춘 입력 스키마.

    drug_name은 처방전 기재 관행상 상품명(제품명)
    (의료법 시행규칙 제12조 — 일반명칭·제품명·대한민국약전 명칭 중 선택 기재 가능).
    """

    drug_name: str
    dosage: str = ""
    frequency: str = ""
    diagnosis: str = ""
    drug_class: str = ""
    confidence: float = 0.0


class SourceRef(BaseModel):
    item_seq: str
    item_name: str
    field: str
    update_de: str | None = None
    # HIRA 약가마스터(hira_master.py) 보강 필드 — e약은요 item_name으로 조회해 채움.
    # 매칭 안 되면(HIRA 미등재 품목명 등) 전부 None으로 남는다 (인용 자체는 그대로 유효).
    hira_standard_code: str | None = None
    hira_atc_code: str | None = None
    hira_permit_date: str | None = None
    hira_active: bool | None = None  # None=HIRA에서 못 찾음, True=정상 등재, False=취소·취하됨
    # [2026-07-14 추가] 식약처 의약품제품허가정보(DrugPermitInfo) 보강 필드 — e약은요 item_name으로
    # 조회해 채움. HIRA(약가 등재 상태)와는 다른 개념 — 이건 제조·판매 허가 자체의 취소여부다.
    permit_kind_code: str | None = None  # "허가" | "신고"
    permit_active: bool | None = None  # None=허가정보에서 못 찾음, True=정상, False=취소·취하됨


class LifestyleSourceRef(BaseModel):
    guideline_id: str
    disease: str
    category: str
    source: str


class GuideResponse(BaseModel):
    """의약품(drug) 기준 가이드 — 생활습관 안내는 여기 없다.

    [2026-07-21 회의 반영] 생활습관 안내는 의약품별이 아니라 진단명별로 1회만 생성해야
    하므로, 의약품 하나당 생성되는 이 응답에서 lifestyle_guide/lifestyle_source_refs를
    분리해 별도의 LifestyleGuideResult(진단명 기준, generate_lifestyle_guide_for_diagnosis)로
    옮겼다. 이 모델은 순수하게 "이 약"에 대한 정보(효능·복용법·주의사항·DUR)만 담는다.
    """

    drug_name: str
    medication_guide: str = Field(description="복약 안내: 효능, 복용법, 핵심 주의사항 요약")
    precautions: list[str] = Field(default_factory=list, description="반드시 확인해야 할 주의사항 목록")
    source_refs: list[SourceRef] = Field(default_factory=list)
    dur_warnings: list[DurWarning] = Field(
        default_factory=list, description="같은 처방전의 다른 약과 DUR 병용금기 관계가 확인된 경우만 채워짐"
    )
    dur_cautions: list[DurCaution] = Field(
        default_factory=list, description="이 약 자체의 DUR 주의/금기 정보(노인주의/연령금기/임부금기 등, 다른 약과 무관)"
    )
    disclaimer: str
    self_consistency_score: float | None = None
    review_required: bool = False
    review_reason: str | None = None
    review_flags: list[str] = Field(
        default_factory=list,
        description=(
            "검토 사유 코드: no_citation | low_self_consistency | "
            "ocr_low_confidence | ocr_confidence_unavailable | dry_run | generation_error | "
            "dur_taboo_warning | dur_caution"
        ),
    )
    ocr_confidence: float | None = Field(
        default=None, description="OCR 개별 인식 신뢰도 원본 (generate_guide_from_medication 경유 시에만 채워짐)"
    )
    cached: bool = Field(default=False, description="True이면 DB 캐시에서 반환된 결과 (REQ-020)")
    cache_expires_at: str | None = Field(
        default=None, description="캐시 만료 시각 ISO-8601 문자열 (cached=True 일 때만 채워짐)"
    )


class LifestyleGuideResult(BaseModel):
    """진단명(diagnosis) 기준 생활습관 안내 — 의약품과 무관하게 진단명 하나당 1회만 생성된다.

    [2026-07-21 회의 반영] 여러 의약품이 같은 진단명을 공유해도 이 결과는 한 번만
    만들어진다(generate_guides_from_medications가 진단명 집합 기준으로 중복 제거).
    diagnosis가 비어 있으면 안전한 일반 안내 문구로 폴백한다(hallucination 방지).
    """

    diagnosis: str = Field(description="이 안내가 대상으로 하는 진단명 — 진단명이 없으면 빈 문자열")
    guide: str = Field(description="진단명 기준 생활습관 개선 가이드(식이/운동/주의사항 등). 약물 이름은 언급하지 않는다")
    source_refs: list[LifestyleSourceRef] = Field(default_factory=list)
    review_required: bool = False
    review_reason: str | None = None
    review_flags: list[str] = Field(
        default_factory=list,
        description=(
            "검토 사유 코드: no_diagnosis | no_lifestyle_context | no_citation | "
            "low_self_consistency | dry_run | empty_lifestyle_fallback | empty_lifestyle_guide"
        ),
    )
