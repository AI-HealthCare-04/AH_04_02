"""security.py 단위 테스트 — encrypt_pii/decrypt_pii, normalize_phone, hash_phone (담당: 김영혜)"""
import pytest

from security import decrypt_pii, encrypt_pii, hash_phone, normalize_phone


def test_encrypt_decrypt_round_trip():
    plaintext = "김건강"
    ciphertext = encrypt_pii(plaintext)
    assert ciphertext != plaintext
    assert decrypt_pii(ciphertext) == plaintext


def test_encrypt_is_not_deterministic():
    """Fernet은 매 호출마다 랜덤 IV를 쓰므로 같은 평문도 암호문이 매번 달라야 한다."""
    a = encrypt_pii("같은 값")
    b = encrypt_pii("같은 값")
    assert a != b
    assert decrypt_pii(a) == decrypt_pii(b) == "같은 값"


def test_decrypt_tampered_value_fails():
    ciphertext = encrypt_pii("김건강")
    tampered = ciphertext[:-4] + "abcd"
    with pytest.raises(Exception):  # cryptography.fernet.InvalidToken
        decrypt_pii(tampered)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("010-1234-5678", "01012345678"),
        ("010 1234 5678", "01012345678"),
        ("01012345678", "01012345678"),
        ("010 - 1234 - 5678", "01012345678"),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_hash_phone_same_number_different_formats_match():
    """하이픈/공백 유무와 무관하게 같은 번호는 같은 해시가 나와야 로그인 조회가 된다."""
    assert hash_phone("010-1234-5678") == hash_phone("01012345678") == hash_phone("010 1234 5678")


def test_hash_phone_different_numbers_differ():
    assert hash_phone("010-1234-5678") != hash_phone("010-1234-5679")


def test_hash_phone_is_not_reversible_looking():
    """해시값 자체가 원본 숫자를 그대로 노출하지 않는지 — 단순 sanity check."""
    h = hash_phone("010-1234-5678")
    assert "01012345678" not in h
    assert len(h) == 64  # HMAC-SHA256 hexdigest 길이
