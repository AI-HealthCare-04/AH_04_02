import numpy as np

from rag.vectorstore import get_embedding_function


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)


def pick_consistent_answer(candidates: list[str]) -> tuple[int, float]:
    """여러 후보 답변 중 서로 가장 유사한(대표) 답변의 인덱스와 평균 유사도를 반환합니다.

    self-consistency: 동일 질의를 N회 생성해 답변들이 서로 얼마나 일치하는지로
    hallucination 가능성을 가늠합니다. 평균 유사도가 낮으면 review_required로 표시합니다.
    """
    if len(candidates) == 1:
        return 0, 1.0

    embedder = get_embedding_function()
    vectors = embedder.embed_documents(candidates)

    avg_similarities = []
    for i, vec_i in enumerate(vectors):
        sims = [_cosine_similarity(vec_i, vec_j) for j, vec_j in enumerate(vectors) if i != j]
        avg_similarities.append(sum(sims) / len(sims))

    best_idx = max(range(len(candidates)), key=lambda i: avg_similarities[i])
    overall_avg = sum(avg_similarities) / len(avg_similarities)
    return best_idx, overall_avg
