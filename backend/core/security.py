"""
security.py — 개인정보(PII) 필드 암호화/해시 유틸 (담당: 김영혜)

2026-07-08 멘토링 확정 방침: 이름·전화번호는 대칭키 암호화(Fernet)로 저장하고,
전화번호는 로그인/검색을 위해 정규화한 값의 HMAC-SHA256 해시(phone_hash)를
별도로 둔다. 비밀번호는 이 모듈이 다루지 않음 — auth.py의 기존 단방향 해시
(bcrypt)를 그대로 씀. 사용 위치: models.py의 Patient/Caregiver .name/.phone
프로퍼티에서만 호출 — 라우터가 이 모듈을 직접 호출할 필요는 없다.

PII_ENCRYPTION_KEY 생성 방법:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

PII_HASH_SECRET 생성 방법 (32바이트 랜덤 hex):
    python -c "import secrets; print(secrets.token_hex(32))"

둘 다 .env에 넣고 코드/DB에는 절대 하드코딩하지 않는다. 키가 없거나 형식이
잘못되면 이 모듈을 import하는 시점(서버 기동 시점)에 바로 실패한다 — 평문
저장으로 조용히 넘어가는 사고를 막기 위함.
"""
import hashlib
import hmac
import os
import secrets

from cryptography.fernet import Fernet

_PII_ENCRYPTION_KEY = os.environ.get("PII_ENCRYPTION_KEY")
_PII_HASH_SECRET = os.environ.get("PII_HASH_SECRET")

if not _PII_ENCRYPTION_KEY:
    raise RuntimeError(
        "PII_ENCRYPTION_KEY 환경변수가 없습니다. "
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '
        "로 생성해서 backend/.env에 추가하세요."
    )
if not _PII_HASH_SECRET:
    raise RuntimeError(
        "PII_HASH_SECRET 환경변수가 없습니다. "
        'python -c "import secrets; print(secrets.token_hex(32))" 로 생성해서 backend/.env에 추가하세요.'
    )

try:
    _fernet = Fernet(_PII_ENCRYPTION_KEY.encode())
except Exception as exc:  # noqa: BLE001 — 키 형식이 잘못됐을 때 원인을 명확히 알려주기 위해 감쌈
    raise RuntimeError(f"PII_ENCRYPTION_KEY가 올바른 Fernet 키 형식이 아닙니다: {exc}") from exc

_HASH_SECRET_BYTES = _PII_HASH_SECRET.encode()


def encrypt_pii(value: str) -> str:
    """평문을 Fernet으로 암호화해 복호화 가능한 문자열로 반환."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt_pii(value: str) -> str:
    """encrypt_pii()로 암호화된 문자열을 평문으로 복호화."""
    return _fernet.decrypt(value.encode()).decode()


def normalize_phone(phone: str) -> str:
    """전화번호에서 하이픈·공백을 제거. 예: 010-1234-5678 -> 01012345678"""
    return phone.replace("-", "").replace(" ", "")


def normalize_email(email: str) -> str:
    """[2026-07-14 추가] 이메일 앞뒤 공백 제거 + 소문자 정규화.

    가입/로그인 양쪽에서 항상 이 함수를 거치지 않으면 " Test@Example.COM "과
    "test@example.com"이 서로 다른 계정으로 취급돼 로그인이 안 되는 문제가 있었다.
    """
    return email.strip().lower()


def hash_phone(phone: str) -> str:
    """정규화한 전화번호를 HMAC-SHA256으로 해시 — 로그인/검색 조회용(복호화 대상 아님)."""
    normalized = normalize_phone(phone)
    return hmac.new(_HASH_SECRET_BYTES, normalized.encode(), hashlib.sha256).hexdigest()


def generate_reset_code() -> str:
    """[2026-07-15 추가, REQ-039] 비밀번호 재설정용 6자리 숫자 임시번호. 앞자리 0도 유지됨."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_code(code: str) -> str:
    """[2026-07-15 추가, REQ-039] 임시번호를 HMAC-SHA256으로 해시 — DB에는 평문 저장 안 함."""
    return hmac.new(_HASH_SECRET_BYTES, code.encode(), hashlib.sha256).hexdigest()


def hash_token(token: str) -> str:
    """[2026-07-15 추가] 무작위 토큰(초대 링크 등)을 HMAC-SHA256으로 해시 — 원문은 저장하지
    않고, 조회 시 넘어온 토큰을 같은 방식으로 해시해 DB의 해시값과 대조한다."""
    return hmac.new(_HASH_SECRET_BYTES, token.encode(), hashlib.sha256).hexdigest()


def verify_pii_key_against_db(engine) -> None:
    """[2026-07-28 추가] 기동 시 현재 PII_ENCRYPTION_KEY가 DB의 실제 암호화 데이터와
    일치하는지 검증한다.

    위의 Fernet 형식 검사는 "형식은 유효하지만 기존 DB와 맞지 않는 다른 키"를 통과시켜
    버린다 — 실제 사고 원인이 이것이었고, 그 경우 기동 후 로그인 실패로만 드러났다.
    이 함수를 lifespan에서 호출해 그 케이스도 기동 시점(fail-fast)에 잡는다.

    patients와 caregivers 양쪽을 모두 확인한다 — 한쪽만 확인하면 그쪽이 비어있을 때
    오탐(통과)이 생길 수 있다(예: patients가 비어있고 caregivers에만 데이터가 있는 경우).
    두 테이블 모두 암호화된 레코드가 없으면(최초 배포·빈 DB) 검증 대상이 없으므로 스킵한다.
    """
    from cryptography.fernet import InvalidToken
    from sqlalchemy import text

    _queries = [
        text("SELECT name_encrypted FROM patients WHERE name_encrypted != '' LIMIT 1"),
        text("SELECT name_encrypted FROM caregivers WHERE name_encrypted != '' LIMIT 1"),
    ]
    with engine.connect() as conn:
        for query in _queries:
            row = conn.execute(query).fetchone()
            if row is not None:
                try:
                    _fernet.decrypt(row[0].encode())
                except InvalidToken as exc:
                    raise RuntimeError(
                        "PII_ENCRYPTION_KEY가 기존 데이터와 일치하지 않는 것 같습니다 — "
                        "docs/env-var-checklist.md 참고"
                    ) from exc
                return  # 한 테이블에서 복호화 성공 = 키 일치, 추가 검증 불필요
    # patients/caregivers 모두 암호화된 레코드 없음 — 최초 배포/빈 DB이므로 스킵
