"""
건강동행 백엔드 — main.py (관리: 박소정)

v6 확정 구조:
- DB: SQLite (app.db 파일 하나, 설치 불필요)
- 동기 방식 (스트리밍/폴링 없음)
- Redis 미사용
- 라우터: ocr_router(권순현) / rag_router(김영혜) / monitoring_router(박소정)

[7/6 보류 → 7/9 로그인 활성화] JWT 로그인(auth.py, dependencies.py, routers/auth_router.py)은
schedule_v6에서 시간·인력 상 이번 스프린트 스코프에서 뺐었는데(백엔드 경험 0명 대응), 2026-07-08
멘토링에서 개인정보 보호(암호화) 설계가 로그인 방식을 전제로 하게 되면서 auth_router를 다시
등록함 — 보호자/환자 둘 다 로그인 가능(POST /auth/login). ⚠️ monitoring_router.py 등 기존
엔드포인트들은 여전히 caregiver_id/patient_id를 쿼리 파라미터로 받는 기존 방식 그대로임 — 그
엔드포인트들을 실제 토큰 기반(`Depends(get_current_caregiver)`)으로 바꾸는 건 이번 변경 범위
밖(별도 작업)이고, 로그인 자체와 개인정보 암호화만 이번에 반영함.

실행 방법 (backend 폴더에서):
    pip install -r requirements.txt
    uvicorn main:app --reload
→ http://localhost:8000/docs 열리면 성공
"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth_router, ocr_router, rag_router, monitoring_router, records_router, care_router, chat_router

app = FastAPI(
    title="건강동행 API",
    description="3인 체제 v6 — SQLite + 동기 방식",
    version="0.1.0",
)

# 프론트(Vite 개발서버)에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """서버 시작 시 SQLite 테이블 자동 생성 (없으면 만들고, 있으면 그대로 둠)"""
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
