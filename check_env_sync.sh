#!/usr/bin/env bash
# check_env_sync.sh — AH_04_02 로컬 환경 동기화 체크
# 실행: bash check_env_sync.sh (프로젝트 루트에서)
# 결과를 그대로 복사해서 팀 채팅에 공유하면 서로 비교할 수 있습니다.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

SEP="──────────────────────────────────────────"

echo "=============================================="
echo "  AH_04_02 환경 동기화 체크"
echo "  실행 시각: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  호스트:    $(hostname)"
echo "=============================================="
echo ""

# ── 1. Git 커밋 확인 ────────────────────────────
echo "[ 1 ] Git HEAD 커밋"
echo "$SEP"
echo "브랜치: $(git branch --show-current)"
echo "HEAD:   $(git rev-parse HEAD)"
git status --short --branch
echo ""

# ── 2. Python 버전 ──────────────────────────────
echo "[ 2 ] Python 버전 (uv)"
echo "$SEP"
uv run python --version 2>&1 || echo "ERROR: uv run python 실패"
echo ""

# ── 3. Node 버전 ────────────────────────────────
echo "[ 3 ] Node 버전"
echo "$SEP"
if command -v node >/dev/null 2>&1; then
  node --version
else
  echo "ERROR: node 명령어를 찾을 수 없음"
fi
echo ""

# ── 4. .env.example vs .env 누락/추가 키 확인 ───
echo "[ 4 ] backend/.env 키 비교"
echo "$SEP"
ENV_EXAMPLE="backend/.env.example"
ENV_LOCAL="backend/.env"

extract_keys() {
  sed -nE 's/^[[:space:]]*([A-Z0-9_]+)=.*/\1/p' "$1" | sort -u
}

if [[ ! -f "$ENV_EXAMPLE" ]]; then
  echo "ERROR: $ENV_EXAMPLE 없음"
elif [[ ! -f "$ENV_LOCAL" ]]; then
  echo "ERROR: $ENV_LOCAL 없음 — .env.example을 복사해서 값을 채우세요"
else
  tmp_example="$(mktemp)"
  tmp_actual="$(mktemp)"
  extract_keys "$ENV_EXAMPLE" > "$tmp_example"
  extract_keys "$ENV_LOCAL"   > "$tmp_actual"

  MISSING="$(comm -23 "$tmp_example" "$tmp_actual")"
  EXTRA="$(comm -13 "$tmp_example" "$tmp_actual")"

  if [[ -z "$MISSING" ]]; then
    echo "OK — .env.example의 모든 키가 .env에 있습니다"
  else
    echo "MISSING (.env에 없는 키):"
    echo "$MISSING" | sed 's/^/  /'
  fi

  if [[ -n "$EXTRA" ]]; then
    echo "EXTRA (.env.example에는 없는 .env 전용 키 — 정상인 경우도 있음):"
    echo "$EXTRA" | sed 's/^/  /'
  fi

  rm -f "$tmp_example" "$tmp_actual"
fi
echo ""

# ── 5. DATABASE_SSL 설정 값 확인 ────────────────
echo "[ 5 ] backend/.env SSL 설정"
echo "$SEP"
if [[ -f "$ENV_LOCAL" ]]; then
  grep -E '^DATABASE_SSL_(REQUIRED|CA)=' "$ENV_LOCAL" \
    || echo "[WARN] DATABASE_SSL_REQUIRED 또는 DATABASE_SSL_CA 없음"
  echo ""
  echo "  [기댓값 — Docker Compose + Aiven]"
  echo "  DATABASE_SSL_REQUIRED=true"
  echo "  DATABASE_SSL_CA=certs/aiven-ca.pem"
  # CA 파일 실제 존재 여부
  SSL_CA="$(grep '^DATABASE_SSL_CA=' "$ENV_LOCAL" 2>/dev/null | cut -d= -f2 || true)"
  if [[ -n "${SSL_CA:-}" ]]; then
    CA_PATH="backend/${SSL_CA}"
    if [[ -f "$CA_PATH" ]]; then
      echo "  → $CA_PATH 존재 ✓"
    else
      echo "  → $CA_PATH 없음 ✗ (aiven-ca.pem 복사 필요 — docs/etc/local-files-checklist.md 참고)"
    fi
  fi
else
  echo "ERROR: backend/.env 없음"
fi
echo ""

# ── 6. 공유 데이터 파일 SHA256 해시 ─────────────
echo "[ 6 ] 공유 데이터 파일 해시 (SHA256)"
echo "$SEP"

sha_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    shasum -a 256 "$path"
  else
    printf '[MISSING] %s\n' "$path"
  fi
}

sha_file backend/certs/aiven-ca.pem

dur_found=0
for f in backend/data/dur_*.csv; do
  [[ -f "$f" ]] && { shasum -a 256 "$f"; dur_found=1; }
done
[[ "$dur_found" -eq 0 ]] && echo "[MISSING] backend/data/dur_*.csv"

sha_file rag/data/kdca_healthinfo_cntntsSn.csv
sha_file rag/chroma_db/chroma.sqlite3

# SHA256SUMS.txt가 있으면 자동 비교
if [[ -f SHA256SUMS.txt ]]; then
  echo ""
  echo "  [SHA256SUMS.txt 자동 대조]"
  shasum -a 256 -c SHA256SUMS.txt 2>&1 | sed 's/^/  /' || true
fi
echo ""

# ── 7. Docker 컨테이너 상태 ─────────────────────
echo "[ 7 ] Docker 컨테이너 상태"
echo "$SEP"
if docker compose version >/dev/null 2>&1; then
  docker compose ps 2>&1 || echo "ERROR: docker compose ps 실패"
else
  echo "ERROR: Docker 데몬이 실행 중이지 않습니다 (Docker Desktop을 시작하세요)"
fi
echo ""

# ── 8. rag/.env 키 확인 ─────────────────────────
echo "[ 8 ] rag/.env 키 확인"
echo "$SEP"
RAG_ENV="rag/.env"
RAG_REQUIRED_KEYS=("OPENAI_API_KEY" "DATA_GO_KR_SERVICE_KEY")

if [[ ! -f "$RAG_ENV" ]]; then
  echo "ERROR: $RAG_ENV 없음 — RAG/챗봇(RAG_PROVIDER=real, CHAT_PROVIDER=real) 사용 시 필수"
else
  echo "OK — $RAG_ENV 존재"
  for key in "${RAG_REQUIRED_KEYS[@]}"; do
    if grep -qE "^${key}=.+" "$RAG_ENV" 2>/dev/null; then
      echo "  $key: 설정됨 ✓"
    elif grep -qE "^${key}=" "$RAG_ENV" 2>/dev/null; then
      echo "  $key: 키는 있으나 값이 비어있음 ✗ (RAG/챗봇이 동작하지 않음)"
    else
      echo "  $key: 없음 ✗"
    fi
  done
fi
echo ""

echo "=============================================="
echo "  체크 완료 — 이 결과를 팀 채팅에 공유하세요"
echo "=============================================="