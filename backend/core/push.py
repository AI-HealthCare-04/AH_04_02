"""
push.py — Web Push 실발송 (담당: 박소정, 2026-07-24 추가)

VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY가 없으면 조용히 스킵한다 — email.py(smtp)와
다르게 push는 아직 프론트에 구독 흐름이 없는 보조 채널이라(HTTPS 배포 이후 붙일
예정), 설정이 안 됐다고 이메일 발송까지 막으면 안 된다. 구독이 만료/취소되면
(404/410) 그 자리에서 DB에서 지운다 — 브라우저 데이터 삭제·앱 삭제 등으로
자연히 발생하는 정상 상황이다.
"""
from __future__ import annotations

import json
import logging
import os

from models import PushSubscription
from pywebpush import WebPushException, webpush
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

_VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY") or None
_VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY") or None
_VAPID_CONTACT_EMAIL = os.environ.get("VAPID_CONTACT_EMAIL", "admin@example.com")


def vapid_public_key() -> str | None:
    """프론트가 pushManager.subscribe()의 applicationServerKey로 쓸 공개키.
    None이면 아직 발송 설정이 안 된 것 — 구독 자체를 막아야 한다."""
    return _VAPID_PUBLIC_KEY


def send_push_to_recipient(
    session: Session,
    recipient_role: str,
    recipient_id: int,
    title: str,
    body: str,
    url: str = "/",
    schedule_id: int | None = None,
) -> bool:
    """recipient(환자 또는 보호자 본인 계정)가 등록한 모든 기기로 발송한다.
    한 기기 발송이 실패해도 나머지 기기는 계속 시도한다.

    반환값은 "구독이 있어서 실제로 발송을 시도했는지"다(개별 기기 발송 성공 여부까지는
    아님 — 이메일처럼 recipient 단위로만 추적). 호출부(scheduler.py)가 NotificationLog.
    channels에 push 항목을 남길지 판단하는 데 쓴다 — 구독이 없거나 VAPID 키가 없어
    아무 일도 안 했는데 "발송했다"고 로그를 남기면 안 되기 때문이다."""
    if not (_VAPID_PUBLIC_KEY and _VAPID_PRIVATE_KEY):
        return False

    subs = session.exec(
        select(PushSubscription)
        .where(PushSubscription.recipient_role == recipient_role)
        .where(PushSubscription.recipient_id == recipient_id)
    ).all()
    if not subs:
        return False

    payload_dict = {"title": title, "body": body, "url": url}
    # [2026-07-30 추가] 복약 알림에 schedule_id를 같이 보내면 sw.ts가 "복용했어요"/
    # "건너뛸게요" 액션 버튼을 붙인다 — 안드로이드/데스크톱 Chrome 계열만 지원(iOS Safari는
    # 웹 푸시 액션 버튼 자체를 지원 안 해서 이 값이 있어도 버튼 없이 기존처럼 탭-오픈만 됨).
    if schedule_id is not None:
        payload_dict["schedule_id"] = schedule_id
    payload = json.dumps(payload_dict, ensure_ascii=False)
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{_VAPID_CONTACT_EMAIL}"},
                # [2026-08-06] 기본값(Urgency 미지정="normal", ttl=0)이면 FCM(안드로이드/
                # 크롬)이 절전모드에서 발송을 몇 분~몇십 분씩 묶어서 배달한다 — 복약
                # 정시 알림처럼 지금 당장 봐야 하는 알림은 high로 즉시 배달을 요청해야
                # 한다. ttl도 0(=지금 못 전달하면 버림)이라 CATCH_UP_MINUTES(10분) 창과
                # 맞춰 늘려서, 기기가 잠깐 오프라인이어도 그 안에는 배달되게 한다.
                headers={"Urgency": "high"},
                ttl=600,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                session.delete(sub)
                session.commit()
            else:
                logger.warning(
                    "Web Push 발송 실패 (recipient=%s:%s): %s", recipient_role, recipient_id, exc
                )
    return True
