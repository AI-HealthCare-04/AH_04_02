"""_issue_login_response() 회귀 테스트 — PR #22 리뷰에서 발견된 NameError 재발 방지"""
from fastapi import Response
from routers.auth_router import _issue_login_response
from sqlmodel import Session, SQLModel, create_engine


def test_issue_login_response_returns_name_and_id_for_given_subject():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        response = Response()
        result = _issue_login_response(response, subject_id=42, role="caregiver", name="테스트 보호자", session=session)
        assert result.caregiver_id == 42
        assert result.name == "테스트 보호자"
        assert result.access_token
