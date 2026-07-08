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


# [보류] 식약처 의약품제품허가정보(DrugPrdtPrmsnInfoService07) 스키마 — e약은요·약가마스터만으로
# 우선 조회하기로 하고 비활성화. 정보량이 방대하고 팀원 연동(HIRA 약가마스터) 조율이 더 필요해서
# 나중에 정말 경로를 바꿔야 하는 문제가 생기면 그때 주석을 풀어 쓴다.
# class DrugPermitInfo(BaseModel):
#     """식약처 DrugPrdtPrmsnInfoService07 getDrugPrdtPrmsnInq07 응답 1개 품목.
#
#     e약은요(DrugInfo)와 원천이 다른 별도 API — 효능효과 등 설명문 텍스트는 없고,
#     허가번호·허가일자·허가/신고 구분·취소여부 같은 규제 메타데이터만 담는다.
#     "정식으로 허가·신고되어 현재 정상 상태인 의약품인지" 검증 용도.
#     """
#
#     item_seq: str = Field(alias="ITEM_SEQ")
#     item_name: str = Field(alias="ITEM_NAME")
#     item_eng_name: str | None = Field(default=None, alias="ITEM_ENG_NAME")
#     entp_name: str = Field(alias="ENTP_NAME")
#     entp_eng_name: str | None = Field(default=None, alias="ENTP_ENG_NAME")
#     item_permit_date: str | None = Field(default=None, alias="ITEM_PERMIT_DATE")
#     specialty_pblc: str | None = Field(default=None, alias="SPCLTY_PBLC")  # 전문/일반의약품
#     product_type: str | None = Field(default=None, alias="PRDUCT_TYPE")  # 예: "[01140]해열.진통.소염제"
#     permit_no: str | None = Field(default=None, alias="PRDUCT_PRMISN_NO")
#     ingr_name: str | None = Field(default=None, alias="ITEM_INGR_NAME")
#     permit_kind_code: str | None = Field(default=None, alias="PERMIT_KIND_CODE")  # "허가" | "신고"
#     cancel_date: str | None = Field(default=None, alias="CANCEL_DATE")
#     cancel_name: str | None = Field(default=None, alias="CANCEL_NAME")  # "정상" | 취소·취하 상태명
#
#     model_config = {"populate_by_name": True}
#
#     @property
#     def is_active(self) -> bool:
#         """취소·취하되지 않고 현재 정상 허가 상태인지 (cancel_date가 없고 cancel_name이 '정상')."""
#         return self.cancel_date is None and self.cancel_name == "정상"


class HiraDrugMasterEntry(BaseModel):
    """건강보험심사평가원 약가마스터·의약품표준코드 CSV(data/hira_drug_master_20251031.csv) 1개 행.

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


class LifestyleSourceRef(BaseModel):
    guideline_id: str
    disease: str
    category: str
    source: str


class GuideResponse(BaseModel):
    drug_name: str
    medication_guide: str = Field(description="복약 안내: 효능, 복용법, 핵심 주의사항 요약")
    lifestyle_guide: str = Field(description="약물 연계 생활습관 개선 가이드")
    precautions: list[str] = Field(default_factory=list, description="반드시 확인해야 할 주의사항 목록")
    source_refs: list[SourceRef] = Field(default_factory=list)
    lifestyle_source_refs: list[LifestyleSourceRef] = Field(default_factory=list)
    disclaimer: str
    self_consistency_score: float | None = None
    review_required: bool = False
    review_reason: str | None = None
    review_flags: list[str] = Field(
        default_factory=list,
        description=(
            "검토 사유 코드: no_citation | low_self_consistency | "
            "ocr_low_confidence | ocr_confidence_unavailable | dry_run | generation_error"
        ),
    )
    ocr_confidence: float | None = Field(
        default=None, description="OCR 개별 인식 신뢰도 원본 (generate_guide_from_medication 경유 시에만 채워짐)"
    )
