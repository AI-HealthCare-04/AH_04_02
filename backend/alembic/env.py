import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# backend/ 자체가 패키지가 아니라 평평한 구조라(다른 backend 모듈들과 동일한 방식으로)
# sys.path에 넣어야 `import database`/`import models`가 된다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# alembic 명령은 uvicorn(main.py)을 거치지 않고 단독 실행되므로 .env를 직접 로드해야
# APP_ENV/DATABASE_URL/PII_* 등이 채워진다 (main.py의 load_dotenv와 동일한 이유).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import database  # noqa: E402 — sys.path/load_dotenv 이후에 import 해야 함
import models  # noqa: E402,F401 — SQLModel.metadata에 테이블 정의를 올리기 위한 import
from sqlmodel import SQLModel

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# alembic.ini에 실제 DB 접속정보를 적어두지 않는다 — database.py가 이미 읽은
# DATABASE_URL(환경변수 기반)을 그대로 재사용한다 (한 곳에서만 관리, 비밀번호 이중 관리 방지).
config.set_main_option("sqlalchemy.url", database.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # render_as_batch: SQLite는 대부분의 ALTER TABLE을 직접 지원하지 않아서
        # (컬럼 추가 정도만 가능, 타입 변경/제약조건 변경 불가) Alembic이 "배치 모드"로
        # 테이블을 통째로 재생성하는 방식으로 우회해야 한다. MySQL/Postgres는 필요 없다.
        connection_url = str(connectable.url)
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection_url.startswith("sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
