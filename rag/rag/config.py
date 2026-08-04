from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    DATA_GO_KR_SERVICE_KEY: str
    # 식약처_의약품개요정보(e약은요) — 효능효과/용법용량/주의사항 등 환자용 설명문 텍스트 (가이드 생성 인용용)
    MFDS_BASE_URL: str = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

    # [2026-07-14] 식약처_의약품제품허가정보 활용신청 승인되어 재활성화. 같은
    # DATA_GO_KR_SERVICE_KEY를 재사용한다. mfds_client.py의 search_permit_info()/
    # is_officially_approved()도 함께 복원.
    PERMIT_INFO_BASE_URL: str = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
    # [2026-07-14 추가] 목록 조회와 별개 엔드포인트 — 사용상의주의사항(NB_DOC_DATA) 등 원문 텍스트 제공.
    PERMIT_DETAIL_BASE_URL: str = (
        "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06"
    )

    # [2026-07-14] 식약처_의약품안전사용서비스(DUR) 활용신청이 승인되어(신청유형: 개발계정,
    # 처리상태: 승인) 로컬 CSV 조회를 폐기하고 다시 API 연동으로 전환했다. 같은
    # DATA_GO_KR_SERVICE_KEY를 재사용한다. CONTRACT.md §7 참고.
    DUR_USJNT_TABOO_BASE_URL: str = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03"
    DUR_ODSN_ATENT_BASE_URL: str = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getOdsnAtentInfoList03"
    DUR_AGE_TABOO_BASE_URL: str = (
        "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getSpcifyAgrdeTabooInfoList03"
    )
    DUR_PREGNANCY_TABOO_BASE_URL: str = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getPwnmTabooInfoList03"

    # 식약처 API 응답 디스크 캐시 경로 — 서버 재시작 후에도 캐시가 유지된다.
    # Docker 환경에서는 .:/workspace 바인드 마운트 덕분에 컨테이너 재시작·재빌드 후에도
    # 호스트 파일시스템에 그대로 남는다. 로컬 실행 시에는 프로젝트 루트/mfds_cache에 생성된다.
    MFDS_CACHE_DIR: str = str(BASE_DIR.parent / "mfds_cache")
    MFDS_CACHE_TTL_SECONDS: int = 60 * 60 * 48  # 48시간 — 식약처/DUR 고시 수시 개정 대응

    # Compact offline snapshot. Runtime network fallback is opt-in so normal
    # requests remain fast and deterministic.
    PUBLIC_API_MASTER_PATH: str = str(BASE_DIR / "data" / "public_api_master.jsonl")
    PUBLIC_API_MASTER_ENABLED: bool = True
    # The compact master is intentionally partial. A miss must fall back to
    # the official API so an unknown medicine never becomes a silent
    # "no DUR warning" result.
    PUBLIC_API_LIVE_FALLBACK: bool = True

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    EMBEDDING_MODEL_NAME: str = "jhgan/ko-sroberta-multitask"

    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "chroma_db")
    CHROMA_COLLECTION_NAME: str = "mfds_drug_info"

    TOP_K: int = 3
    SELF_CONSISTENCY_SAMPLES: int = 3
    SELF_CONSISTENCY_SIMILARITY_THRESHOLD: float = 0.75

    # OCR 개별 인식 신뢰도 검토 임계값 (OCR팀 REQ-011과 동일 값).
    # OCR의 review_required는 overall_confidence만 보고 개별 약의 저신뢰를 놓치므로,
    # 이 임계값은 그에 대한 보완 통제(compensating control)로 쓰인다 (rag_chain._merge_ocr_confidence).
    # SELF_CONSISTENCY_SIMILARITY_THRESHOLD(0.75)와는 의미가 다른 별개 상수다.
    OCR_CONFIDENCE_REVIEW_THRESHOLD: float = 0.80

    DISCLAIMER: str = "본 정보는 의료진의 진단·처방을 대체하지 않습니다. 복용 중인 다른 약물이나 건강 상태에 대해서는 반드시 의사·약사와 상의하세요."


settings = Settings()
