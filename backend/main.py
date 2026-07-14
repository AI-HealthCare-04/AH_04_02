"""
건강동행 백엔드 — main.py (관리: 박소정)

v6 확정 구조:
- DB: APP_ENV/DATABASE_URL 환경변수로 결정 (기본값은 지금까지처럼 로컬 SQLite,
  APP_ENV=development면 팀 공통 DB(MySQL 등)를 가리킴 — database.py 참고, 2026-07-14 변경)
- 동기 방식 (스트리밍/폴링 없음)
- Redis 미사용
- 로그인: /auth/login으로 Caregiver 이메일/비밀번호 인증, JWT 발급 (7/10 재개)
- 라우터: ocr_router(권순현) / rag_router(김영혜) / monitoring_router(박소정) / auth_router(박소정)

[7/6 보류 → 7/9 로그인 활성화] JWT 로그인(auth.py, dependencies.py, routers/auth_router.py)은
schedule_v6에서 시간·인력 상 이번 스프린트 스코프에서 뺐었는데(백엔드 경험 0명 대응), 2026-07-08
멘토링에서 개인정보 보호(암호화) 설계가 로그인 방식을 전제로 하게 되면서 auth_router를 다시
등록함 — 보호자/환자 둘 다 로그인 가능(POST /auth/login).

[7/10] 로그인 화면(Login.tsx)도 실제 이메일/비밀번호 폼으로 복원했지만, monitoring_router 등
나머지 라우터는 아직 caregiver_id/patient_id를 쿼리 파라미터로 그대로 신뢰합니다 — 발급된
토큰을 각 엔드포인트에서 검증하는 작업은 별도(issue #21)로 남아 있습니다.

실행 방법 (backend 폴더에서):
    pip install -r requirements.txt
    uvicorn main:app --reload
→ http://localhost:8000/docs 열리면 성공
"""
from __future__ import annotations
from pathlib import Path

from dotenv import load_dotenv

# [7/11] .env 로드가 ocr_router.py 안에만 있어서, auth_router(→models→security.py가
# 기동 시점에 PII_ENCRYPTION_KEY를 요구함)가 먼저 임포트되면 .env가 아직 안 읽힌
# 상태로 실패했다. 라우터 임포트보다 먼저, 여기 한 곳에서만 로드한다.
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, log_db_connection_info
from routers import (
    auth_router,
    care_router,
    chat_router,
    monitoring_router,
    ocr_router,
    patient_medications_router,
    rag_router,
    records_router,
)

app = FastAPI(
    title="건강동행 API",
    description="3인 체제 v6 — SQLite + 동기 방식",
    version="0.1.0",
)

# 프론트(Vite 개발서버)에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",  # [7/10] 별도 포트 미리보기 서버(backend-dev/frontend-dev)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 어느 DB에 붙었는지 로그로 남기고, local/test면 테이블 자동 생성
    (development/production은 Alembic migration으로 관리 — database.py 참고)"""
    log_db_connection_info()
    init_db()


@app.get("/", tags=["Health"])
def health_check():
    """서버 살아있는지 확인용 — 브라우저에서 http://localhost:8000 열면 이게 보임"""
    return {"status": "ok", "service": "건강동행 API"}


# ── 라우터 등록 (새 라우터 추가 시 여기에 한 줄씩) ──
app.include_router(auth_router.router)  # [7/9] 로그인 활성화 — 보호자/환자 둘 다 지원
app.include_router(records_router.router)
app.include_router(ocr_router.router)
app.include_router(rag_router.router)
app.include_router(monitoring_router.router)
app.include_router(care_router.router)
app.include_router(chat_router.router)
app.include_router(patient_medications_router.router)  # [2026-07-14 추가] 환자 의약품 등록/조회/일정/복약기록
