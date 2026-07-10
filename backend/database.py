"""
database.py — SQLite 연결 설정 (관리: 박소정)

app.db 파일 하나가 DB 전체예요. 삭제하면 데이터 초기화됩니다 (개발 중엔 그래도 됨).
"""
from sqlmodel import SQLModel, Session, create_engine, select

DATABASE_URL = "sqlite:///./app.db"

# check_same_thread=False: FastAPI가 여러 요청을 처리할 때 필요한 SQLite 옵션
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """models.py에 정의된 테이블을 전부 생성 (이미 있으면 건너뜀) + 데모 데이터 시드"""
    import models  # noqa: F401 — 테이블 정의를 메모리에 올리기 위한 import

    SQLModel.metadata.create_all(engine)
    _seed_demo_data()


def _seed_demo_data() -> None:
    """
    [7/6 추가] 로그인이 없어서 patient_id/caregiver_id를 아무도 안 만들면 테스트가 막힘.
    patients 테이블이 비어있으면 데모용 환자 1명 + 보호자 1명 + 연결 1건을 자동 생성.
    실제 여러 환자가 필요하면 POST /patients 로 더 만들면 됨 (이건 그냥 "빈 상태 방지"용).

    [7/6 추가 2] 로그인 도입 이후: 데모 보호자 계정으로 바로 로그인 테스트 가능하도록
    email=demo@example.com / password=password1234 로 시드함.
    """
    import models
    from auth import hash_password

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
