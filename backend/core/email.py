"""
email.py — 이메일 발송 (담당: 김영혜)

EMAIL_PROVIDER=mock(기본값) | smtp — OCR_PROVIDER/RAG_PROVIDER와 동일한 패턴.
mock은 실제로 보내지 않고 로그로만 남긴다(로컬/테스트에서 실수로 실제 메일이
나가지 않도록 안전한 기본값). smtp로 켜면 SMTP_* 환경변수로 실제 발송한다.

[2026-07-15] REQ-039(비밀번호 재설정) 코드 발송용으로 도입 — 가입이 이미
이메일 기반이라 SMS 등 별도 채널 계약 없이 바로 구축 가능하다는 판단(사용자 확인).
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "mock")

_SMTP_HOST = os.environ.get("SMTP_HOST")
_SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
_SMTP_USER = os.environ.get("SMTP_USER")
_SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
_SMTP_FROM = os.environ.get("SMTP_FROM", _SMTP_USER or "no-reply@example.com")


def send_email(to: str, subject: str, body: str) -> None:
    """EMAIL_PROVIDER에 따라 실제 발송하거나(smtp) 로그만 남긴다(mock).

    smtp 모드에서 SMTP_HOST/SMTP_USER/SMTP_PASSWORD가 없으면, 잘못된 설정으로
    조용히 메일이 안 나가는 상황을 막기 위해 즉시 에러를 던진다(다른 PROVIDER들의
    "의존성 없으면 조용히 폴백" 방식과 다르게, 이메일은 폴백하면 사용자가 코드를
    영영 못 받으므로 실패를 숨기지 않는다).
    """
    if _EMAIL_PROVIDER != "smtp":
        logger.info("[EMAIL mock] to=%s subject=%s body=%s", to, subject, body)
        return

    if not (_SMTP_HOST and _SMTP_USER and _SMTP_PASSWORD):
        raise RuntimeError(
            "EMAIL_PROVIDER=smtp인데 SMTP_HOST/SMTP_USER/SMTP_PASSWORD 중 일부가 없습니다. "
            "backend/.env에 SMTP 설정을 채우거나, EMAIL_PROVIDER=mock으로 되돌리세요."
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _SMTP_FROM
    message["To"] = to
    message.set_content(body)

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.starttls()
        server.login(_SMTP_USER, _SMTP_PASSWORD)
        server.send_message(message)


def send_password_reset_email(to: str, code: str) -> None:
    """REQ-039 비밀번호 재설정 인증코드 발송."""
    send_email(
        to=to,
        subject="[건강동행] 비밀번호 재설정 인증코드",
        body=(
            f"비밀번호 재설정 인증코드: {code}\n\n"
            "이 코드는 10분간 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시하세요."
        ),
    )
