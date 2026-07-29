#!/usr/bin/env bash

# AH_04_02 local environment sync checker.
# Run from the project root:
#   bash check_env_sync.sh

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR" || exit 1

section() {
  printf '\n========== %s ==========\n' "$1"
}

print_cmd() {
  printf '$ %s\n' "$*"
}

run_or_note() {
  print_cmd "$*"
  "$@" 2>&1 || printf '[WARN] command failed: %s\n' "$*"
}

sha_file() {
  local file="$1"
  if [ -f "$file" ]; then
    shasum -a 256 "$file"
  else
    printf '[MISSING] %s\n' "$file"
  fi
}

extract_env_keys() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return 1
  fi
  sed -nE 's/^[#[:space:]]*([A-Z0-9_]+)=.*/\1/p' "$file" | sort -u
}

section "Git"
run_or_note git rev-parse HEAD
run_or_note git status --short --branch

section "Runtime Versions"
run_or_note uv run python --version
if command -v node >/dev/null 2>&1; then
  run_or_note node --version
else
  printf '[MISSING] node command not found\n'
fi

section "backend/.env key comparison"
if [ ! -f backend/.env.example ]; then
  printf '[MISSING] backend/.env.example\n'
elif [ ! -f backend/.env ]; then
  printf '[MISSING] backend/.env\n'
  printf 'Create backend/.env from backend/.env.example and fill team-shared values.\n'
else
  tmp_example="$(mktemp)"
  tmp_actual="$(mktemp)"
  extract_env_keys backend/.env.example > "$tmp_example"
  extract_env_keys backend/.env > "$tmp_actual"

  printf '[Missing in backend/.env]\n'
  missing="$(comm -23 "$tmp_example" "$tmp_actual")"
  if [ -n "$missing" ]; then
    printf '%s\n' "$missing"
  else
    printf 'none\n'
  fi

  printf '\n[Extra in backend/.env]\n'
  extra="$(comm -13 "$tmp_example" "$tmp_actual")"
  if [ -n "$extra" ]; then
    printf '%s\n' "$extra"
  else
    printf 'none\n'
  fi

  rm -f "$tmp_example" "$tmp_actual"
fi

section "DB SSL values in backend/.env"
if [ -f backend/.env ]; then
  grep -E '^DATABASE_SSL_(REQUIRED|CA)=' backend/.env || printf '[WARN] DATABASE_SSL_REQUIRED or DATABASE_SSL_CA not found\n'
  printf '\n[Expected for Docker Compose + Aiven]\n'
  printf 'DATABASE_SSL_REQUIRED=true\n'
  printf 'DATABASE_SSL_CA=certs/aiven-ca.pem\n'
else
  printf '[SKIP] backend/.env not found\n'
fi

section "Shared file SHA256"
sha_file backend/certs/aiven-ca.pem

dur_found=0
for file in backend/data/dur_*.csv; do
  if [ -f "$file" ]; then
    dur_found=1
    shasum -a 256 "$file"
  fi
done
if [ "$dur_found" -eq 0 ]; then
  printf '[MISSING] backend/data/dur_*.csv\n'
fi

sha_file rag/data/kdca_healthinfo_cntntsSn.csv
sha_file rag/chroma_db/chroma.sqlite3

if [ -f SHA256SUMS.txt ]; then
  section "SHA256SUMS.txt comparison"
  run_or_note shasum -a 256 -c SHA256SUMS.txt
else
  printf '\n[INFO] SHA256SUMS.txt not found. Compare the hashes above in team chat.\n'
fi

section "Docker Compose"
if docker compose version >/dev/null 2>&1; then
  run_or_note docker compose ps
else
  printf '[MISSING] docker compose command not available\n'
fi

section "Done"
printf 'Copy everything above and share it in the team chat for comparison.\n'
