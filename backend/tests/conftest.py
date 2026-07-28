"""
conftest.py — 테스트 환경 세팅 (담당: 김영혜)

security.py는 PII_ENCRYPTION_KEY/PII_HASH_SECRET가 없으면 import 시점에 바로
에러를 내므로, 어떤 backend 모듈이든 import되기 전에 여기서 테스트 전용 값을
환경변수로 넣어둔다. 실제 배포용 키가 아니라 테스트에서만 쓰는 더미 값이다.

또 backend/ 자체는 패키지(__init__.py)가 아니라 `core/`, `services/`, `routers/` 같은
서브패키지들을 담는 루트라 `from core.security import ...`처럼 절대 임포트를 쓰므로,
backend/ 자체를 sys.path에 넣어줘야 테스트에서도 같은 방식으로 임포트할 수 있다.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

os.environ.setdefault("PII_ENCRYPTION_KEY", "c7Ka8_mp2rYGAesszwMtAXutMT8rq2SqDyVnhjU6H_8=")  # 테스트 전용 더미 키
os.environ.setdefault("PII_HASH_SECRET", "test-only-hash-secret-do-not-use-in-prod")
os.environ.setdefault("SECRET_KEY", "test-only-jwt-secret-do-not-use-in-prod")
os.environ.setdefault("DATA_GO_KR_SERVICE_KEY", "test-only-data-go-kr-service-key")
# [2026-07-14 추가] TestClient(app)가 FastAPI startup 이벤트(init_db())를 실제로 실행시키는데,
# APP_ENV/DATABASE_URL을 안 정해주면 개발자의 진짜 로컬 app.db를 건드릴 수 있다 —
# 완전히 분리된 in-memory SQLite를 가리키도록 고정한다 (각 테스트 파일의 실제 assertion은
# 자체 in-memory 엔진+dependency_overrides를 쓰므로 이건 순전히 startup 부작용 방지용).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")
# [2026-07-15 추가] main.py가 나중에(테스트가 main을 import할 때) load_dotenv()를 호출하는데,
# 개발자 로컬 backend/.env에 실제로 DATABASE_SSL_REQUIRED=true 등이 켜져 있으면 그 값을
# 이 프로세스의 os.environ에 심어버린다(load_dotenv는 이미 있는 키는 안 건드리므로 여기서
# 빈 문자열로 먼저 채워서 "막아둔다" — pop()으로 지우기만 하면 나중에 load_dotenv가 다시
# 채워버림). test_database_env.py가 서브프로세스에 os.environ을 그대로 물려주는 방식이라,
# 이 값이 남아있으면 "SSL 관련 값이 아예 없는 조합"을 재현하는 테스트가 개발자 로컬 .env
# 내용에 따라 깨진다.
os.environ.setdefault("DATABASE_SSL_REQUIRED", "")
os.environ.setdefault("DATABASE_SSL_CA", "")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# [2026-07-28 추가] SQLite는 기본적으로 외래키 제약을 강제하지 않는다(PRAGMA로 켜야 함) —
# 반면 실서버(MySQL/InnoDB)는 항상 강제한다. 그래서 "삭제 순서를 안 지켜 FK 위반이 나는"
# 버그가 SQLite로 도는 테스트는 통과하고 실서버에서만 500이 나는 일이 반복됐다(실제 사례:
# 9dc7e8e — delete_schedule()이 레거시 MedicationLog를 안 지우고 스케줄을 지워도 SQLite
# 테스트는 통과했음). 각 테스트 파일이 개별적으로 `create_engine("sqlite://", ...)`를
# 부르므로, 엔진 인스턴스가 아니라 Engine 클래스 자체에 이벤트를 걸어 전부 한 번에 적용한다.
@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(autouse=True)
def _reset_chat_llm_available(monkeypatch: pytest.MonkeyPatch):
    """[2026-07-20 추가] routers/chat_router.py의 _CHAT_LLM_AVAILABLE은 모듈 import
    시점에 한 번만 CHAT_PROVIDER/rag.config.settings.OPENAI_API_KEY로 계산되는 전역
    변수다 — 개발자 로컬 backend/.env에 CHAT_PROVIDER=real과 실 OPENAI_API_KEY가 있으면
    그 값 그대로 고정돼, 프리셋/동적 질문 테스트가 실제 GPT를 호출해버렸다(answer_source가
    "preset"/"unsupported"가 아니라 "llm (gpt-4o-mini)"로 나와 실패).

    함수 스코프 autouse로 매 테스트 시작 시 False로 되돌린다 — monkeypatch가 테스트당
    공유되는 함수 스코프 fixture라, 실 LLM 경로를 직접 검증하려는 개별 테스트가 같은
    monkeypatch로 `monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", True)`를
    호출하면 이 fixture보다 나중에 실행되어 그 테스트 안에서만 이긴다(세션 스코프였다면
    override가 다음 테스트로 새어나갈 위험이 있어 함수 스코프를 택함). raising=False는
    이 속성이 아직 없는 극단적 상황에서도 conftest 자체가 깨지지 않게 하는 방어."""
    import routers.chat_router as chat_router

    monkeypatch.setattr(chat_router, "_CHAT_LLM_AVAILABLE", False, raising=False)
