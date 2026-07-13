from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    DATA_GO_KR_SERVICE_KEY: str
    # 식약처_의약품개요정보(e약은요) — 효능효과/용법용량/주의사항 등 환자용 설명문 텍스트 (가이드 생성 인용용)
    MFDS_BASE_URL: str = "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

    # [보류] 식약처_의약품제품허가정보 — e약은요·약가마스터만으로 우선 조회하기로 하고 비활성화.
    # 정보량이 방대하고 순현님 쪽 연동(HIRA 약가마스터)과 조율이 더 필요해서, 나중에 정말
    # 경로를 바꿔야 하는 문제가 생기면 그때 주석을 풀어 쓴다. mfds_client.py의
    # search_permit_info()/is_officially_approved()도 같은 이유로 주석 처리해뒀다.
    # PERMIT_INFO_BASE_URL: str = "http://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"

    # [2026-07-10 → 7/13] 식약처_의약품안전사용서비스(DUR) 병용금기는 원래 API 연동(같은
    # DATA_GO_KR_SERVICE_KEY 재사용)을 시도했으나 403 Forbidden(활용신청 승인 대기중)이라,
    # 공공데이터포털에서 받은 로컬 CSV 조회로 대체했다 (rag_prototype/dur_master.py,
    # 경로는 hira_master.py와 동일하게 모듈 상수 DEFAULT_DUR_TABOO_CSV_PATH로 관리 —
    # 여기 Settings에는 별도 URL/경로 설정이 없다). CONTRACT.md §7 참고.

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
