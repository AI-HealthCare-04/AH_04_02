from services.langfuse_tracing import mask_for_langfuse


def test_mask_for_langfuse_masks_dot_separated_phone_number():
    masked = mask_for_langfuse("연락처는 010.1234.5678 입니다.")

    assert "010.1234.5678" not in masked
    assert "[PHONE_MASKED]" in masked


def test_mask_for_langfuse_masks_foreigner_rrn_gender_digits():
    masked = mask_for_langfuse("주민번호 900101-5123456")

    assert "900101-5123456" not in masked
    assert "[RRN_MASKED]" in masked
