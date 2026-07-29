# AH_04_02 로컬 공유 파일 체크리스트

GitHub에 올리지 않는 공통 로컬 파일(팀 공유 zip으로 전달)을 로컬에 배치할 때 확인하는
체크리스트입니다. 압축 해제 후 각 파일을 프로젝트의 동일 경로에 배치하세요.

## 포함 파일

1. `backend/certs/aiven-ca.pem`
2. `backend/data/dur_age_taboo_202606.csv`
3. `backend/data/dur_elderly_caution_202606.csv`
4. `backend/data/dur_elderly_caution_nsaid_202606.csv`
5. `backend/data/dur_pregnancy_taboo_202606.csv`
6. `backend/data/dur_usjnt_taboo_202606.csv`
7. `rag/data/kdca_healthinfo_cntntsSn.csv`
8. `rag/chroma_db/`

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
DATABASE_SSL_REQUIRED=true
DATABASE_SSL_CA=backend/certs/aiven-ca.pem
OCR_PROVIDER=clova
CLOVA_OCR_API_URL=각자 입력
CLOVA_OCR_SECRET_KEY=각자 입력
CHAT_PROVIDER=real
RAG_PROVIDER=real
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=각자 또는 팀 프로젝트 키
LANGFUSE_SECRET_KEY=각자 또는 팀 프로젝트 키
```

> **[2026-07-29 수정]** 예전엔 `DB_SSL_CA_PATH`로 적혀있었는데, 실제 코드
> (`backend/core/database.py`)가 읽는 변수명은 `DATABASE_SSL_CA`입니다 — 이름이
> 달라서 CA 인증서 경로가 조용히 무시되고 있었습니다. 또한 `DATABASE_SSL_CA`는
> `DATABASE_SSL_REQUIRED=true`일 때만 실제로 읽히므로(`database.py`), 두 줄을
> 함께 설정해야 합니다.

## rag/.env 확인 항목

```env
OPENAI_API_KEY=각자 입력
```

## 동일 파일 확인 방법

각자 압축 해제 후 아래 파일들이 같은 경로에 있는지 확인합니다.

```bash
ls backend/certs/aiven-ca.pem
ls backend/data/dur_*.csv
ls rag/data/kdca_healthinfo_cntntsSn.csv
ls rag/chroma_db/chroma.sqlite3
```

파일 내용까지 같은지 확인하려면 SHA256 해시를 비교합니다.

```bash
shasum -a 256 backend/certs/aiven-ca.pem
shasum -a 256 backend/data/dur_*.csv
shasum -a 256 rag/data/kdca_healthinfo_cntntsSn.csv
shasum -a 256 rag/chroma_db/chroma.sqlite3
```
