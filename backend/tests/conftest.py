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

os.environ.setdefault("PII_ENCRYPTION_KEY", "c7Ka8_mp2rYGAesszwMtAXutMT8rq2SqDyVnhjU6H_8=")  # 테스트 전용 더미 키
os.environ.setdefault("PII_HASH_SECRET", "test-only-hash-secret-do-not-use-in-prod")
os.environ.setdefault("SECRET_KEY", "test-only-jwt-secret-do-not-use-in-prod")
# [2026-07-14 추가] TestClient(app)가 FastAPI startup 이벤트(init_db())를 실제로 실행시키는데,
# APP_ENV/DATABASE_URL을 안 정해주면 개발자의 진짜 로컬 app.db를 건드릴 수 있다 —
# 완전히 분리된 in-memory SQLite를 가리키도록 고정한다 (각 테스트 파일의 실제 assertion은
# 자체 in-memory 엔진+dependency_overrides를 쓰므로 이건 순전히 startup 부작용 방지용).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite://")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
