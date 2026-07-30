"""
Langfuse tracing helpers.

Langfuse is optional: missing package/credentials must never break the chatbot.
Only non-sensitive metadata is sent. Do not add patient names, phone numbers,
raw medical record text, or full patient context to traces.
"""
from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

# [2026-07-28 버그수정] Langfuse 연동은 "절대 챗봇을 깨면 안 된다"는 설계 때문에 모든
# 예외를 조용히 삼키기만 하고 어디에도 로그를 남기지 않았다 — 그래서 duckdns 도메인
# 전환(EC2 인스턴스 재설정) 이후 추적이 안 되는 문제가 생겨도, 서버 로그 어디에도
# 단서가 없어 "키가 안 옮겨졌는지/네트워크가 막혔는지/SDK 문제인지" 구분할 방법이
# 전혀 없었다. 챗봇 동작 자체는 여전히 막지 않되(예외를 여전히 삼킴), 최소한 로그는
# 남긴다 — LANGFUSE_* 환경변수 자체가 없는 경우(로컬 개발 등 흔한 정상 상황)는 요청마다
# 반복해서 남기면 로그만 시끄러워지므로 프로세스당 한 번만 남긴다.
logger = logging.getLogger(__name__)
_warned_disabled = False

_PHONE_RE = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")
_RRN_RE = re.compile(r"\d{6}[-\s]?[1-8]\d{6}")


def mask_for_langfuse(value: str | None) -> str:
    """Mask common Korean PII patterns before sending text to Langfuse."""
    if not value:
        return ""
    masked = _PHONE_RE.sub("[PHONE_MASKED]", value)
    masked = _RRN_RE.sub("[RRN_MASKED]", masked)
    return masked[:1000]


def _enabled() -> bool:
    result = bool(
        os.environ.get("LANGFUSE_SECRET_KEY")
        and os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_BASE_URL")
    )
    if not result:
        global _warned_disabled
        if not _warned_disabled:
            _warned_disabled = True
            # 로컬 개발처럼 원래 키를 안 넣는 환경도 흔해서 경고(warning)까진 아니고,
            # "지금 이 프로세스는 추적이 꺼진 상태다"만 한 번 알려준다(info) — 배포
            # 환경에서 "추적이 안 된다"는 제보를 받으면 이 로그 한 줄로 원인(키 누락)을
            # 바로 좁힐 수 있다.
            logger.info(
                "Langfuse tracing disabled — LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY/"
                "LANGFUSE_BASE_URL 중 하나 이상이 설정되지 않았습니다."
            )
    return result


def _prepare_langfuse_env() -> None:
    """Keep our .env naming compatible with the Langfuse SDK.

    The project uses LANGFUSE_BASE_URL in .env.example, while recent Langfuse
    SDKs also understand LANGFUSE_HOST. Set the SDK name from our existing
    value so Cloud region configuration is not silently ignored.
    """
    base_url = os.environ.get("LANGFUSE_BASE_URL")
    if base_url and not os.environ.get("LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = base_url


def langfuse_available() -> bool:
    if not _enabled():
        return False
    try:
        import langfuse  # noqa: F401
    except Exception:  # noqa: BLE001
        # 여기 도달했다는 건 키는 다 설정돼 있는데(_enabled()==True) SDK 자체를 못 불러온
        # 것 — 흔한 "키 누락" 케이스와 달리 실제 문제(패키지 미설치 등)일 가능성이 높다.
        logger.warning("Langfuse SDK import에 실패했습니다 — 추적이 비활성화됩니다.", exc_info=True)
        return False
    return True


def get_langfuse_client():
    if not _enabled():
        return None
    try:
        _prepare_langfuse_env()
        from langfuse import get_client

        return get_client()
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse 클라이언트 초기화에 실패했습니다 — 추적이 비활성화됩니다.", exc_info=True)
        return None


def get_langchain_callback_handler():
    """Return a LangChain callback handler for Langfuse if configured.

    Langfuse v4 exposes this as `langfuse.langchain.CallbackHandler`. The
    handler uses the process-level Langfuse client configuration for secret key
    and host, while the public key is passed explicitly.
    """
    if not _enabled():
        return None
    try:
        _prepare_langfuse_env()
        from langfuse.langchain import CallbackHandler

        return CallbackHandler(public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"))
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse LangChain 콜백 핸들러 생성에 실패했습니다 — 추적이 비활성화됩니다.", exc_info=True)
        return None


@contextmanager
def optional_observation(*, as_type: str, name: str, **kwargs: Any) -> Iterator[Any]:
    """Start a Langfuse observation if configured, otherwise yield a no-op context."""
    client = get_langfuse_client()
    if client is None:
        with nullcontext(None) as observation:
            yield observation
        return

    manager = None
    try:
        manager = client.start_as_current_observation(as_type=as_type, name=name, **kwargs)
        observation = manager.__enter__()
    except Exception:  # noqa: BLE001
        # 키는 설정돼 있고 클라이언트도 만들어졌는데 여기서 실패한다면(예: EC2 아웃바운드
        # 방화벽/보안그룹이 langfuse 서버로 나가는 443을 막는 경우) 실제 네트워크/연결
        # 문제일 가능성이 높다 — "키 누락"과 구분되는 신호라 반드시 남긴다.
        logger.warning("Langfuse observation(%s) 시작에 실패했습니다.", name, exc_info=True)
        with nullcontext(None) as observation:
            yield observation
        return

    try:
        yield observation
    except BaseException as exc:
        if manager is not None:
            suppress = manager.__exit__(type(exc), exc, exc.__traceback__)
            if suppress:
                return
        raise
    else:
        if manager is not None:
            manager.__exit__(None, None, None)


def update_observation(observation: Any, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse observation 업데이트에 실패했습니다.", exc_info=True)
        return


def flush_langfuse() -> None:
    """Force pending traces to be sent after a request during local testing."""
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse flush()에 실패했습니다 — 트레이스가 전송되지 않았을 수 있습니다.", exc_info=True)
        return


def now_ms() -> float:
    return time.perf_counter() * 1000
