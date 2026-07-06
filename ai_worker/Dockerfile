# ---- Builder stage ----
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

COPY pyproject.toml uv.lock ./

# ai 그룹 의존성만 설치
RUN uv sync --group ai --no-dev --frozen

# ---- Runtime stage ----
FROM python:3.13-slim AS runtime

# 일부 AI 라이브러리(torch 등)가 필요로 하는 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY --from=builder /build/.venv /code/.venv
ENV PATH="/code/.venv/bin:$PATH"

COPY ai_worker ./ai_worker

CMD ["python", "-m", "ai_worker.main"]
