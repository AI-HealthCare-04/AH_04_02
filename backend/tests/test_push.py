"""core/push.py 테스트 (2026-07-24 신규, 담당: 박소정)

실제 브라우저 구독이 없으므로(HTTPS 배포 이후 프론트 작업) pywebpush.webpush()를
모킹해서 검증한다: VAPID 키 미설정 시 스킵, 구독별 발송, 410/404 응답 시 구독 삭제,
그 외 오류는 삭제하지 않고 넘어가는지.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from core import push
from models import PushSubscription
from pywebpush import WebPushException
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_subscription(session: Session, role: str = "patient", recipient_id: int = 1, endpoint: str = "https://push.example.com/1") -> PushSubscription:
    sub = PushSubscription(recipient_role=role, recipient_id=recipient_id, endpoint=endpoint, p256dh="p256dh-key", auth="auth-key")
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def _exception_with_status(status_code: int | None) -> WebPushException:
    if status_code is None:
        return WebPushException("boom", response=None)
    response = MagicMock()
    response.status_code = status_code
    return WebPushException("boom", response=response)


class TestVapidPublicKey:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", None)
        assert push.vapid_public_key() is None

    def test_returns_configured_value(self, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "test-public-key")
        assert push.vapid_public_key() == "test-public-key"


class TestSendPushToRecipient:
    def test_skips_silently_when_vapid_keys_missing(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", None)
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", None)
        _make_subscription(session)

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        mock_webpush.assert_not_called()

    def test_skips_when_no_subscriptions(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 999, "제목", "본문")

        mock_webpush.assert_not_called()

    def test_sends_to_each_subscription(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        monkeypatch.setattr(push, "_VAPID_CONTACT_EMAIL", "team@example.com")
        _make_subscription(session, endpoint="https://push.example.com/a")
        _make_subscription(session, endpoint="https://push.example.com/b")

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 1, "복약 시간이에요", "약 드실 시간이에요", url="/schedule")

        assert mock_webpush.call_count == 2
        first_call = mock_webpush.call_args_list[0].kwargs
        assert first_call["vapid_private_key"] == "priv"
        assert first_call["vapid_claims"] == {"sub": "mailto:team@example.com"}
        assert first_call["subscription_info"]["keys"] == {"p256dh": "p256dh-key", "auth": "auth-key"}

    def test_includes_schedule_id_in_payload_when_given(self, session: Session, monkeypatch):
        # [2026-07-30 추가] sw.ts가 복용 액션 버튼을 붙이려면 schedule_id가 payload에
        # 실려있어야 한다 — 안 넘기면(다른 알림 종류) payload에 빠져있는지도 같이 확인.
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session)

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 1, "복약 시간이에요", "약 드실 시간이에요", schedule_id=42)
        payload = json.loads(mock_webpush.call_args.kwargs["data"])
        assert payload["schedule_id"] == 42

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 1, "검토 완료", "확인해주세요")
        payload = json.loads(mock_webpush.call_args.kwargs["data"])
        assert "schedule_id" not in payload

    def test_does_not_send_to_other_recipients(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session, role="patient", recipient_id=1)
        _make_subscription(session, role="caregiver", recipient_id=1)  # 같은 id, 다른 role

        with patch("core.push.webpush") as mock_webpush:
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        assert mock_webpush.call_count == 1

    def test_prunes_subscription_on_410_gone(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session)

        with patch("core.push.webpush", side_effect=_exception_with_status(410)):
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        assert session.exec(select(PushSubscription)).all() == []

    def test_prunes_subscription_on_404(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session)

        with patch("core.push.webpush", side_effect=_exception_with_status(404)):
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        assert session.exec(select(PushSubscription)).all() == []

    def test_keeps_subscription_on_other_errors(self, session: Session, monkeypatch):
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session)

        with patch("core.push.webpush", side_effect=_exception_with_status(500)):
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        assert len(session.exec(select(PushSubscription)).all()) == 1

    def test_keeps_subscription_when_response_is_none(self, session: Session, monkeypatch):
        """response가 아예 없는(네트워크 오류 등) WebPushException도 구독을 지우면 안 된다."""
        monkeypatch.setattr(push, "_VAPID_PUBLIC_KEY", "pub")
        monkeypatch.setattr(push, "_VAPID_PRIVATE_KEY", "priv")
        _make_subscription(session)

        with patch("core.push.webpush", side_effect=_exception_with_status(None)):
            push.send_push_to_recipient(session, "patient", 1, "제목", "본문")

        assert len(session.exec(select(PushSubscription)).all()) == 1
