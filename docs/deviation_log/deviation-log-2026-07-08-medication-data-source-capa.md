# 편차(Deviation) & CAPA 로그 — 의약품 데이터 소스 오인 및 HIRA 연동

- **날짜**: 2026-07-08
- **작성자**: 김영혜 (RAG 담당)
- **관련 문서**: `rag/contract.md` 6번 항목([보류] 의약품 제품허가정보 API), `rag/README.md` "출처 1 / 출처 1-부가"

## 목적 — 무엇을 위해서

의약품 정보 조회에 쓰는 공공데이터 소스가 원래 의도("의약품 허가를 기반으로 데이터 구축")와
실제 구현이 맞는지 재확인하고, 팀원(순현님)이 이미 쓰고 있는 데이터와 불필요하게 겹치는
부분이 있으면 정리하기 위함.

## 무엇을 하다가

기존 답변("순현님 drug_reference.py와 안 겹친다")을 다시 검토하다가, 사용자가 "왜 아직도
e약은요랑 연동돼 있는지 모르겠다"고 지적. `rag_prototype/schemas.py`의 `DrugInfo`/`mfds_client.py`가
실제로 어떤 공공데이터포털 서비스에 대응하는지 필드명(`efcyQesitm`/`useMethodQesitm` 등
"~Qesitm" FAQ 형식) 기준으로 재검증하고, 웹 검색으로 정확한 서비스명을 대조.

## 발견된 편차 2건

### D5. "의약품 허가정보"인 줄 알았던 API가 실제로는 e약은요였음

- **무엇**: `config.MFDS_BASE_URL`(`DrbEasyDrugInfoService/getDrbEasyDrugList`)은 공공데이터포털의
  "식품의약품안전처_의약품개요정보(e약은요)" 서비스였다. 순현님 `drug_reference.py`가 drug_class
  분류에 쓰는 "e약은요 DB"(정적 xlsx, 4,809건)와 **원천 데이터가 완전히 동일**했다.
- **원인**: `git log`로 확인 결과 이 API 설정은 rag-prototype 최초 커밋(`67ab17d`, 2026-07-03,
  오늘 이전)부터 이미 이렇게 돼 있었다. 요구사항정의서(`요구사항_정의서_v7.xlsx` 등)와
  API명세서를 전부 검색했지만 "의약품 허가" 데이터를 명시적으로 요구하는 문구를 찾지 못했다 —
  즉 최초 설계 시점에 API 선택 근거가 문서화되지 않은 채 굳어진 것으로 보인다.
- **해결**:
  1. 웹 검색으로 실제 "의약품 제품허가정보" API(`DrugPrdtPrmsnInfoService07`/`getDrugPrdtPrmsnInq07`)를
     확인하고, 기존 서비스 키로 실제 호출까지 검증(별도 활용신청 불필요, 바로 접근 가능했음).
     응답 필드가 허가번호·허가일자·허가/취소 상태 등 규제 메타데이터뿐이고 효능효과 같은 설명문이
     없다는 것도 실측으로 확인.
  2. 사용자 결정: e약은요는 그대로 유지(가이드 생성에 필수인 설명문 텍스트가 여기에만 있음),
     허가정보 API는 **정보량이 방대하고 팀원 연동(HIRA) 조율이 더 필요해 당장 쓰지 않기로 하고
     코드를 삭제하지 않고 `[보류]` 주석 처리**(`config.py`/`schemas.py`/`mfds_client.py` + 테스트 6건).
  3. 대신 순현님이 이미 쓰고 있는 **HIRA 약가마스터 CSV**(`건강보험심사평가원_약가마스터_
     의약품표준코드_20251031.csv`, 순현님과 동일 파일)를 `data/`로 옮기고 `hira_master.py`로
     조회 경로를 연결 — 표준코드/ATC코드/허가일자/취소여부를 이걸로 대신 확보.
- **재발 방지**:
  - `rag/contract.md`에 e약은요 vs 허가정보 vs HIRA 약가마스터 세 데이터 소스의 원천·용도·중복 관계를
    명시(`rag/README.md` "출처 1/출처 1-부가", `rag/contract.md` 6번).
  - 허가정보 API 코드는 삭제 대신 `[보류]` 마커로 남겨, 실제 서비스명·엔드포인트·요청 파라미터·
    응답 필드(실측 검증됨)까지 `rag/contract.md`에 기록해서 나중에 재검토·복원 시 처음부터 다시
    조사하지 않아도 되게 함.
  - 앞으로 새 공공데이터 API를 추가할 때는 "정확한 서비스명을 문서에 남긴다"를 관례로 삼는다 —
    이번 편차의 근본 원인이 "API를 고른 근거가 기록 안 됨"이었기 때문.

### D6. 백엔드 `rag_router.py`의 `source_refs` 매핑이 새 HIRA 필드를 누락 (이번 검증 중 발견, 배포 전 수정)

- **무엇**: `SourceRef`에 `hira_standard_code`/`hira_atc_code`/`hira_permit_date`/`hira_active`를
  추가(D5 해결책의 일부)했지만, `backend/routers/rag_router.py`의
  `_generate_via_rag_prototype()`이 `source_refs`를 만들 때 `item_name`/`field`만 꺼내고 새
  HIRA 필드는 꺼내지 않고 있었다.
- **원인**: `rag-prototype`(스키마 변경)과 `backend`(그 결과를 소비하는 코드)가 물리적으로 다른
  디렉터리·별도 커밋이라, 스키마에 필드를 추가해놓고 소비하는 쪽 매핑을 갱신하는 걸 깜빡하기
  쉬운 구조다. Pydantic이 아니라 수동으로 dict를 조립하는 지점이라 타입 체크로도 못 잡는다.
- **해결**: `rag_router.py`의 `source_refs` 리스트 컴프리헨션에 4개 필드를 추가해 즉시 수정
  (아래 "항목 2" 실행 결과에서 실제로 값이 채워지는지 재검증).
- **재발 방지**: `rag-prototype`의 `SourceRef`/`GuideResponse`에 필드를 추가할 때마다
  `backend/routers/rag_router.py`의 `_generate_via_rag_prototype()` 매핑도 함께 확인하는 것을
  체크리스트화할 필요가 있다 — 두 코드베이스 사이에 타입 체크가 없는 지점이므로(계약 테스트
  없음), OCR↔RAG 계약처럼 RAG↔backend 계약도 필요하면 향후 `rag/contract.md`에 추가 검토.

## 검증(Validation) 실행 결과

- `pytest -v`: **29/29 통과** (신규 HIRA 관련 9건 포함: `test_hira_master.py` 6건,
  `test_rag_chain.py`의 HIRA enrichment 3건)
- `ruff check .`: **클린**
- 실제 데이터: 현재 벡터DB에 있는 e약은요 품목명 7개 전부 HIRA 약가마스터와 정확히 매칭 확인,
  실제 파이프라인으로 "어린이타이레놀산160밀리그램" 조회 시 `SourceRef`에 표준코드
  `8806723001704`/ATC `N02BE01`/정상 등재 상태까지 정상 반영되는 것을 실측 확인
