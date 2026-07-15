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


def hash_phone(phone: str) -> str:
    """정규화한 전화번호를 HMAC-SHA256으로 해시 — 로그인/검색 조회용(복호화 대상 아님)."""
    normalized = normalize_phone(phone)
    return hmac.new(_HASH_SECRET_BYTES, normalized.encode(), hashlib.sha256).hexdigest()
