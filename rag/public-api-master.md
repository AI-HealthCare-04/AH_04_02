# 공공 API 소형 마스터

운영 요청에서는 식약처 e약은요·허가정보·DUR API를 매번 호출하지 않는다. 서비스에서
실제로 사용하는 의약품만 `data/public_api_master.jsonl`에 JSONL로 보관하고, 조회 함수는
마스터를 먼저 읽는다. 마스터에 없는 의약품은 안전정보 누락을 막기 위해 기존 공공 API로
폴백한다. 따라서 마스터에 포함된 의약품은 즉시 응답하고, 미포함 의약품도 DUR 경고가
조용히 사라지지 않는다.

마스터 갱신은 요청 처리와 분리된 배치로 실행한다.

```bash
PYTHONPATH=rag python rag/scripts/build_public_api_master.py \
  --from-emed-xlsx --item-names "노바스크정5밀리그람,타이레놀8시간이알서방정"
PYTHONPATH=rag python rag/scripts/ingest_public_api_master.py
```

두 번째 명령은 같은 내용을 기존 Chroma 컬렉션에 `doc_type=public_api_master`로 적재한다.
애플리케이션에서는 `search_public_api_master()`로 검색할 수 있다.
`PUBLIC_API_LIVE_FALLBACK=true`가 안전한 기본값이며, 전체 데이터가 검증된 마스터를
배포한 폐쇄 환경에서만 명시적으로 끌 수 있다.

배치 중 API 오류는 빈 결과로 기록하지 않는다. 과거 버전에서 API 오류와 정상 빈 결과가
모두 `items=[]`로 저장됐기 때문에, 아래 명령으로 불명확한 빈 레코드를 제거할 수 있다.

```bash
PYTHONPATH=rag python rag/scripts/build_public_api_master.py --prune-unverified-empty
```
