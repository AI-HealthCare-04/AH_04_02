# ---- Builder stage ----
FROM python:3.13-slim AS builder

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

# 의존성 정의 파일만 먼저 복사 (레이어 캐싱)
COPY pyproject.toml uv.lock ./

# app 그룹 의존성만 설치 (개발 의존성 제외)
RUN uv sync --group app --no-dev --frozen

# ---- Runtime stage ----
FROM python:3.13-slim AS runtime

WORKDIR /code

# builder에서 생성된 가상환경만 복사 (빌드 도구 등은 제외 → 이미지 경량화)
COPY --from=builder /build/.venv /code/.venv
ENV PATH="/code/.venv/bin:$PATH"

# 애플리케이션 코드 복사
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
