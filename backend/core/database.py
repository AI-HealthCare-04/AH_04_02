"""
database.py — DB 연결 설정 (관리: 박소정)

[2026-07-14 변경] 팀원마다 로컬 SQLite 파일(app.db)이 따로 생겨서 "내가 가입한 계정이
다른 팀원 서버에서 로그인 안 된다"는 문제가 있었음 — DATABASE_URL을 하드코딩된 SQLite
경로 대신 환경변수로 읽도록 바꿔서, 팀 공통 개발 DB(MySQL 등)를 .env 하나로 가리킬 수
있게 했다. APP_ENV=local이면 지금까지처럼 로컬 SQLite로 동작(기본값 유지, 하위호환).

APP_ENV 4단계:
- local: 개인 로컬 SQLite (기본값, DATABASE_URL 생략 가능)
- development: 팀 공통 개발 DB (DATABASE_URL 필수, 보통 MySQL)
- test: pytest가 그때그때 in-memory SQLite로 오버라이드(이 모듈의 값은 안 씀) — CONTRACT 유지 목적으로만 명시
- production: 운영 DB (DATABASE_URL 필수, 로그에 상세 정보 노출 안 함)

동기 SQLAlchemy(SQLModel)를 그대로 쓴다 — 비동기로 바꾸지 않음(기존 구조 유지).
"""
import os

from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine, select

APP_ENV = os.environ.get("APP_ENV", "local")

_DEFAULT_SQLITE_URL = "sqlite:///./app.db"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV in ("development", "production"):
        raise RuntimeError(
            f"APP_ENV={APP_ENV}인데 DATABASE_URL이 설정되지 않았습니다. "
            "팀 공통/운영 DB는 반드시 환경변수로 지정해야 합니다 (.env.example 참고)."
        )
    DATABASE_URL = _DEFAULT_SQLITE_URL  # local/test 기본값 — 기존 동작과 동일

_url = make_url(DATABASE_URL)

# [2026-07-15 추가] Aiven 등 관리형 MySQL은 SSL 연결을 강제한다(ssl-mode=REQUIRED) —
# pymysql은 URL 쿼리스트링이 아니라 connect_args로 ssl을 켜야 한다. 로컬에 SSL 없는
# MySQL(예: Docker)을 직접 붙일 수도 있으니 기본값은 꺼두고 필요할 때만 켠다.
DATABASE_SSL_REQUIRED = os.environ.get("DATABASE_SSL_REQUIRED", "false").lower() == "true"

# [2026-07-15 수정] 위 SSL_REQUIRED만 켜면 "암호화는 하되 서버 인증서는 검증하지 않는"
# 상태였다(ssl={} — CA 지정이 없으면 pymysql이 아무 인증서나 그대로 신뢰함, MITM에
# 취약). DATABASE_SSL_CA에 CA 인증서(Aiven이면 ca.pem) 경로를 주면 그 CA로 서버
# 인증서를 검증한다 — development는 아직 미검증으로 둬도 되지만 production은 반드시
# 이 값을 채워야 한다.
DATABASE_SSL_CA = os.environ.get("DATABASE_SSL_CA")

# [2026-07-15 수정] 이 가드가 원래 아래 `elif DATABASE_SSL_REQUIRED:` 블록 안에만 있어서,
# production인데 DATABASE_SSL_CA뿐 아니라 DATABASE_SSL_REQUIRED 자체를 깜빡 안 켜면
# else 분기(SSL 없는 평문 연결)로 빠져 이 검사 자체를 건너뛰는 구멍이 있었다(실제 재현
# 확인됨). production은 DATABASE_SSL_REQUIRED 값과 무관하게 항상 여기서 먼저 막는다.
if APP_ENV == "production" and not DATABASE_SSL_REQUIRED:
    raise RuntimeError(
        "APP_ENV=production인데 DATABASE_SSL_REQUIRED가 true가 아닙니다. 운영 DB는 "
        "반드시 SSL로 연결해야 합니다 — DATABASE_SSL_REQUIRED=true와 DATABASE_SSL_CA를 지정하세요."
    )

# check_same_thread=False: SQLite에서 FastAPI가 여러 요청을 처리할 때 필요한 옵션.
# MySQL 등 서버형 DB는 이 옵션이 없고, 대신 pool_pre_ping으로 끊긴 연결을 자동 복구한다.
if _url.get_backend_name() == "sqlite":
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif DATABASE_SSL_REQUIRED:
    ssl_args = {"ca": DATABASE_SSL_CA} if DATABASE_SSL_CA else {}
    if APP_ENV == "production" and not DATABASE_SSL_CA:
        raise RuntimeError(
            "APP_ENV=production인데 DATABASE_SSL_CA가 없습니다. 운영 DB는 서버 인증서를 "
            "반드시 검증해야 합니다 — CA 인증서 경로를 DATABASE_SSL_CA에 지정하세요."
        )
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"ssl": ssl_args})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def log_db_connection_info() -> None:
    """서버 시작 시 호출 — 비밀번호 등 민감정보 없이 어느 DB에 붙었는지만 로그로 남긴다.
    운영 환경에서는 상세 정보(host/port/db명)까지도 노출하지 않고 연결 여부만 알린다.
    """
    if APP_ENV == "production":
        print(f"[db] APP_ENV={APP_ENV} — DB 연결됨 (상세 연결 정보는 운영 환경에서 로그에 남기지 않음)")
        return
    print(
        f"[db] APP_ENV={APP_ENV} host={_url.host or '(파일 기반)'} "
        f"port={_url.port or '-'} database={_url.database}"
    )


def init_db() -> None:
    """models.py에 정의된 테이블을 전부 생성 (이미 있으면 건너뜀) + 데모 데이터 시드.

    [2026-07-14 변경] development/production은 Alembic migration으로 스키마를 관리해야
    하므로(alembic/README 참고) 여기서 create_all()을 실행하지 않는다 — 팀 공통 DB가
    아직 마이그레이션 안 된 상태로 반쪽짜리 스키마가 생기는 걸 방지. 데모 데이터 시드도
    local(내 컴퓨터에만 있는 SQLite)에서만 의미가 있어 local일 때만 실행한다.
    """
    import models  # noqa: F401 — 테이블 정의를 메모리에 올리기 위한 import

    if APP_ENV in ("local", "test"):
        SQLModel.metadata.create_all(engine)
        if APP_ENV == "local":
            _seed_demo_data()


def _seed_demo_data() -> None:
    """
    [7/6 추가] 로그인이 없어서 patient_id/caregiver_id를 아무도 안 만들면 테스트가 막힘.
    patients 테이블이 비어있으면 데모용 환자 1명 + 보호자 1명 + 연결 1건을 자동 생성.
    실제 여러 환자가 필요하면 POST /patients 로 더 만들면 됨 (이건 그냥 "빈 상태 방지"용).

    [7/6 추가 2] 로그인 도입 이후: 데모 보호자 계정으로 바로 로그인 테스트 가능하도록
    email=demo@example.com / password=password1234 로 시드함.

    [2026-07-14] local 전용 — 팀 공통 DB(development)에서 서버를 띄운 팀원마다
    이 데모 데이터가 중복 시도되는 걸 막기 위해 init_db()에서 APP_ENV==local일 때만 호출한다.
    """
    import models

    from core.auth import hash_password

    with Session(engine) as session:
        existing = session.exec(select(models.Patient)).first()
        if existing:
            return

        # [7/9] name은 프로퍼티(암호화 setter)라 생성자 kwarg로 못 받음 — 생성 후 대입.
        patient = models.Patient()
        patient.name = "테스트 환자"
        caregiver = models.Caregiver(
            email="demo@example.com",
            hashed_password=hash_password("password1234"),
            relation_type="guardian",
        )
        caregiver.name = "테스트 보호자"
        session.add(patient)
        session.add(caregiver)
        session.commit()
        session.refresh(patient)
        session.refresh(caregiver)

        session.add(models.CaregiverPatient(caregiver_id=caregiver.id, patient_id=patient.id))
        session.commit()


def get_session():
    """엔드포인트에서 DB 쓸 때: session: Session = Depends(get_session)"""
    with Session(engine) as session:
        yield session
