"""
Langfuse tracing helpers.

Langfuse is optional: missing package/credentials must never break the chatbot.
Only non-sensitive metadata is sent. Do not add patient names, phone numbers,
raw medical record text, or full patient context to traces.
"""
from __future__ import annotations

import os
import re
import time
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator


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
    return bool(
        os.environ.get("LANGFUSE_SECRET_KEY")
        and os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_BASE_URL")
    )


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
        return None


@contextmanager
def optional_observation(*, as_type: str, name: str, **kwargs: Any) -> Iterator[Any]:
    """Start a Langfuse observation if configured, otherwise yield a no-op context."""
    client = get_langfuse_client()
    if client is None:
        with nullcontext(None) as observation:
            yield observation
        return

    try:
        with client.start_as_current_observation(as_type=as_type, name=name, **kwargs) as observation:
            yield observation
    except Exception:  # noqa: BLE001
        with nullcontext(None) as observation:
            yield observation


def update_observation(observation: Any, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception:  # noqa: BLE001
        return


def flush_langfuse() -> None:
    """Force pending traces to be sent after a request during local testing."""
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:  # noqa: BLE001
        return


def now_ms() -> float:
    return time.perf_counter() * 1000
