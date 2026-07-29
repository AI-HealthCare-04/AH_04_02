# AH_04_02 로컬 공유 파일 체크리스트

이 ZIP은 GitHub에 올리지 않는 공통 로컬 파일만 선별해서 묶은 것입니다.
압축 해제 후 각 파일을 프로젝트의 동일 경로에 배치하세요.

## 포함 파일

1. `backend/certs/aiven-ca.pem`
2. `backend/data/dur_age_taboo_202606.csv` ⚠️ 레거시
3. `backend/data/dur_elderly_caution_202606.csv` ⚠️ 레거시
4. `backend/data/dur_elderly_caution_nsaid_202606.csv` ⚠️ 레거시
5. `backend/data/dur_pregnancy_taboo_202606.csv` ⚠️ 레거시
6. `backend/data/dur_usjnt_taboo_202606.csv` ⚠️ 레거시
7. `rag/data/kdca_healthinfo_cntntsSn.csv`
8. `rag/chroma_db/`

> **⚠️ 레거시 — DUR CSV (2~6번):** `rag/rag/dur_master.py`가 2026-07-14에 식약처 Open API
> 직접 연동으로 전환되어 이 CSV 파일들은 더 이상 코드에서 읽히지 않습니다. 기존 팀원 환경과의
> SHA256 대조 목적으로만 포함됩니다.
>
> **7번 `kdca_healthinfo_cntntsSn.csv`:** 질병관리청 KDCA 데이터 크롤링 파이프라인의 원본 입력
> 파일입니다(`rag/scripts/kdca_crawl_list.py` 출력 → `kdca_crawl_content.py` 입력).
> `rag/chroma_db/`(8번)가 이미 빌드되어 있으면 **런타임에는 불필요**합니다. KDCA 데이터를
> 재크롤링하거나 ChromaDB를 처음부터 재빌드할 때만 필요합니다.

## 포함하지 않은 파일

- `.env`
- `backend/.env`
- `rag/.env`
- `backend/app.db`
- `backend/uploads/`
- `.venv/`
- `frontend/node_modules/`
- `.idea/`
- `.claude/`
- `.omc/`

## backend/.env 확인 항목

아래 변수 이름이 있는지 확인하고, 값은 팀 내 공유 기준에 맞춰 각자 입력합니다.

```env
APP_ENV=development
DATABASE_URL=원격 Aiven DB 주소
# SSL 필수 여부 — Aiven MySQL은 true로 설정
DATABASE_SSL_REQUIRED=true
# CA 인증서 상대 경로 — backend/Dockerfile의 WORKDIR이 /workspace/backend이므로
# certs/aiven-ca.pem이 /workspace/backend/certs/aiven-ca.pem으로 해석됨.
# backend/certs/aiven-ca.pem으로 쓰면 /workspace/backend/backend/...가 되어 파일을 못 찾음.
DATABASE_SSL_CA=certs/aiven-ca.pem
OCR_PROVIDER=clova
CLOVA_OCR_API_URL=각자 입력
CLOVA_OCR_SECRET_KEY=각자 입력
CHAT_PROVIDER=real
RAG_PROVIDER=real
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=각자 또는 팀 프로젝트 키
LANGFUSE_SECRET_KEY=각자 또는 팀 프로젝트 키
```

## rag/.env 확인 항목

```env
OPENAI_API_KEY=각자 입력
```

## 동일 파일 확인 방법

각자 압축 해제 후 아래 파일들이 같은 경로에 있는지 확인합니다.

```bash
ls backend/certs/aiven-ca.pem
ls backend/data/dur_*.csv          # 레거시 — 런타임 무관, 해시 대조용
ls rag/data/kdca_healthinfo_cntntsSn.csv  # 재크롤링 시에만 필요
ls rag/chroma_db/chroma.sqlite3
```

파일 내용까지 같은지 확인하려면 SHA256 해시를 비교합니다.

```bash
shasum -a 256 backend/certs/aiven-ca.pem
shasum -a 256 backend/data/dur_*.csv          # 레거시 — 런타임 무관, 해시 대조용
shasum -a 256 rag/data/kdca_healthinfo_cntntsSn.csv  # 재크롤링 시에만 필요
shasum -a 256 rag/chroma_db/chroma.sqlite3
```

> **⚠️ `chroma.sqlite3` 해시 비교 주의:** ChromaDB는 내부 HNSW 벡터 인덱스를 빌드 순서에
> 따라 구성하므로, 같은 문서로 각자 재빌드하면 내용이 동일해도 파일 바이트가 달라집니다
> (팀원 두 명이 동일 데이터로 빌드했는데 해시가 다르게 나온 사례 확인).
>
> - **한 사람 파일을 그대로 복사해서 배포하는 경우** → 해시 비교 유효
> - **각자 `rag cli ingest-*`로 재빌드하는 경우** → 해시 대신 문서 수로 비교:
>   ```bash
>   uv run python -c "
>   from rag.rag.vectorstore import get_collection
>   c = get_collection()
>   print('총 문서 수:', c.count())
>   "
>   ```

## 한 번에 점검하는 방법

프로젝트 루트에서 아래 스크립트를 실행하면 현재 커밋, Python/Node 버전, `.env` 누락 키,
DB SSL 설정, 공유 파일 SHA256, Docker Compose 상태를 한 번에 출력합니다.

```bash
bash check_env_sync.sh
```

출력 결과 전체를 팀 채팅에 공유하면 서로 같은 환경을 바라보고 있는지 비교할 수 있습니다.
