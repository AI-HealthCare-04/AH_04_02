from unittest.mock import patch

from rag.self_consistency import pick_consistent_answer


class _FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # 텍스트 길이를 단순 벡터로 사용 (테스트 전용 결정론적 임베딩)
        return [[float(len(t)), float(t.count("가"))] for t in texts]


def test_pick_consistent_answer_single_candidate():
    idx, score = pick_consistent_answer(["동일한 답변"])
    assert idx == 0
    assert score == 1.0


def test_pick_consistent_answer_prefers_majority_agreement():
    candidates = ["가가가가가", "가가가가나", "완전히 다른 이야기"]
    with patch("rag.self_consistency.get_embedding_function", return_value=_FakeEmbedder()):
        idx, score = pick_consistent_answer(candidates)

    assert idx in (0, 1)
    assert 0.0 <= score <= 1.0
