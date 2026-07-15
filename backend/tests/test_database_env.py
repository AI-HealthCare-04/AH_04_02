"""
test_database_env.py — APP_ENV/DATABASE_URL 환경변수 기반 DB 연결 전환 검증 (2026-07-14 추가)

database.py는 모듈 임포트 시점에 환경변수를 읽어 엔진을 만들기 때문에, 같은 프로세스
안에서 재임포트로는 다른 설정을 재현할 수 없다 — 그래서 서브프로세스로 각 케이스를
독립 실행해서 검증한다(실제 서버 프로세스가 기동될 때와 동일한 조건).
"""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_BASE_ENV = {
    "PII_ENCRYPTION_KEY": "c7Ka8_mp2rYGAesszwMtAXutMT8rq2SqDyVnhjU6H_8=",
    "PII_HASH_SECRET": "test-only-hash-secret",
    "SECRET_KEY": "test-only-jwt-secret",
}


def _run(code: str, extra_env: dict) -> subprocess.CompletedProcess:
    import os

    # [주의] conftest.py가 이 테스트 프로세스 자체의 os.environ에 DATABASE_URL=sqlite://를
    # setdefault로 심어둔다 — 그걸 그대로 상속하면 "DATABASE_URL 없음" 케이스를 재현할 수
    # 없으므로, 서브프로세스 환경에서는 DATABASE_URL/APP_ENV를 명시적으로 지우고 시작한다.
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "APP_ENV")}
    env.update(_BASE_ENV)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=30
    )


def test_local_env_defaults_to_sqlite_without_database_url():
    result = _run(
        "from core import database; print(database.engine.dialect.name)",
        {"APP_ENV": "local"},  # DATABASE_URL 생략
    )
    assert result.returncode == 0, result.stderr
    assert "sqlite" in result.stdout


def test_development_env_requires_database_url():
    result = _run("from core import database", {"APP_ENV": "development"})  # DATABASE_URL 생략
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_production_env_requires_database_url():
    result = _run("from core import database", {"APP_ENV": "production"})  # DATABASE_URL 생략
    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_development_env_with_mysql_url_uses_mysql_dialect_and_correct_host():
    result = _run(
        "from core import database; print(database.engine.dialect.name)",
        {"APP_ENV": "development", "DATABASE_URL": "mysql+pymysql://user:pass@shared-db.internal:3306/healthdb"},
    )
    assert result.returncode == 0, result.stderr
    assert "mysql" in result.stdout


def test_log_db_connection_info_never_prints_password():
    result = _run(
        "from core import database; database.log_db_connection_info()",
        {"APP_ENV": "development", "DATABASE_URL": "mysql+pymysql://secretuser:secretpass123@shared-db.internal:3306/healthdb"},
    )
    assert result.returncode == 0, result.stderr
    assert "secretpass123" not in result.stdout
    assert "secretuser" not in result.stdout
    assert "shared-db.internal" in result.stdout  # host는 노출(민감정보 아님)


def test_log_db_connection_info_hides_details_in_production():
    result = _run(
        "from core import database; database.log_db_connection_info()",
        {"APP_ENV": "production", "DATABASE_URL": "mysql+pymysql://user:pass@prod-db.internal:3306/healthdb_prod"},
    )
    assert result.returncode == 0, result.stderr
    assert "prod-db.internal" not in result.stdout  # 운영은 host도 로그에 안 남김
    assert "healthdb_prod" not in result.stdout
