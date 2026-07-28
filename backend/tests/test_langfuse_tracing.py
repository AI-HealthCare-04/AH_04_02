import logging

import services.langfuse_tracing as langfuse_tracing
from services.langfuse_tracing import _enabled, get_langfuse_client, mask_for_langfuse


def test_mask_for_langfuse_masks_dot_separated_phone_number():
    masked = mask_for_langfuse("연락처는 010.1234.5678 입니다.")

    assert "010.1234.5678" not in masked
    assert "[PHONE_MASKED]" in masked


def test_mask_for_langfuse_masks_foreigner_rrn_gender_digits():
    masked = mask_for_langfuse("주민번호 900101-5123456")

    assert "900101-5123456" not in masked
    assert "[RRN_MASKED]" in masked


# ── [2026-07-28 추가] Langfuse 비활성화/실패가 로그 없이 조용히 삼켜지던 문제 ──────
# duckdns 배포 전환 후 Langfuse 추적이 안 되는 제보가 있었는데, 원인이 "키 누락"인지
# "네트워크 문제"인지 서버 로그 어디서도 구분할 수 없었다 — 최소한 "지금 이 프로세스는
# 추적이 꺼져 있다"는 사실은 로그로 남도록 고쳤다.

def test_enabled_logs_once_when_env_vars_missing(monkeypatch, caplog):
    """키가 하나라도 없으면 disabled 상태를 알리되, 요청마다 반복해서 남기지 않고
    프로세스당 한 번만 남긴다(로그가 시끄러워지는 것 방지)."""
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.setattr(langfuse_tracing, "_warned_disabled", False)

    with caplog.at_level(logging.INFO, logger="services.langfuse_tracing"):
        assert _enabled() is False
        assert _enabled() is False
        assert _enabled() is False

    disabled_logs = [r for r in caplog.records if "disabled" in r.message]
    assert len(disabled_logs) == 1


def test_enabled_true_when_all_three_env_vars_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    assert _enabled() is True


def test_get_langfuse_client_returns_none_without_credentials(monkeypatch):
    """자격증명이 없으면 예외 없이 조용히 None을 반환해 챗봇 자체는 막지 않아야 한다."""
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)

    assert get_langfuse_client() is None
