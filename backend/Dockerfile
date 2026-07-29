# 개발용 컨테이너 — 코드는 docker-compose의 바인드 마운트로 들어오고, 이미지에는
# 파이썬 런타임 + 의존성만 미리 깔아둔다 (재빌드 없이 코드 수정이 바로 반영되게).
# 로컬 개발(uv sync)과 동일하게 pyproject.toml/uv.lock 기준으로 의존성을 설치해서
# 로컬·컨테이너 두 환경의 패키지 버전이 어긋나지 않게 한다.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /workspace

COPY pyproject.toml uv.lock ./
# torch가 sentence-transformers 간접 의존성으로 들어오는데, pyproject.toml의
# tool.uv.sources가 CPU 전용 wheel로 고정해둬서 CUDA/nvidia 패키지(수GB)는
# uv.lock 단계에서부터 아예 빠져있다 — 여기서 추가 조치 불필요.
RUN uv sync --frozen --no-cache

WORKDIR /workspace/backend

EXPOSE 8000

CMD ["uv", "run", "--project", "/workspace", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
