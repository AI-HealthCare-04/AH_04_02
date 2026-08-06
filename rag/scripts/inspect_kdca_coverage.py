"""data/kdca_healthinfo_content.jsonl에 있는 항목이 실제로 벡터DB에 인제스트돼 있는지
제목(title) 단위로 대조한다.

[2026-08-05, 천식 생활습관 가이드 미노출 조사 관련] `rag ingest-kdca-health-info`는 CI/배포
어디에도 자동 연결돼 있지 않은 수동 1회 명령이라(rag/README.md), jsonl에 새 데이터가
추가돼도 각자 환경의 벡터DB가 조용히 그 시점에 멈춰있을 수 있다. 지금까지는 이걸 코드로
확인할 방법이 전혀 없어서 "재인제스트를 안 돌린 것 같다"는 추정 이상으로 검증할 수 없었다
— 이 스크립트가 그 검증 수단이다.

주의: `get_vectorstore()`가 임베딩 모델(HuggingFaceEmbeddings)을 로드하므로, ingest와
마찬가지로 torch가 정상 동작하는 환경에서 실행해야 한다.

사용법:
    cd rag && uv run python scripts/inspect_kdca_coverage.py
    cd rag && uv run python scripts/inspect_kdca_coverage.py --title 천식   # 특정 제목만
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Windows 콘솔 기본 인코딩(cp949)에선 한글/이모지 출력 시 UnicodeEncodeError가 날 수 있다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from rag.chunking import kdca_health_info_section_to_document  # noqa: E402
from rag.kdca_health_info_data import load_kdca_health_info_sections  # noqa: E402
from rag.vectorstore import get_vectorstore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default=None, help="이 제목만 대조 (기본값: 전체)")
    args = parser.parse_args()

    sections = load_kdca_health_info_sections()
    expected: Counter[str] = Counter()
    for section in sections:
        if args.title and section.title != args.title:
            continue
        # 순수 이미지 등 텍스트 없는 섹션은 애초에 인제스트 대상이 아니므로
        # (chunking.kdca_health_info_section_to_document가 None 반환) 기대치에서 제외한다.
        if kdca_health_info_section_to_document(section) is not None:
            expected[section.title] += 1

    if not expected:
        print(f"jsonl에서 대조 대상 섹션을 찾지 못했습니다 (title={args.title!r}).")
        return

    # "title" 메타데이터는 kdca_health_info 문서에만 쓰이므로(chunking.py) doc_type과
    # 조합하지 않아도 다른 문서 타입이 섞여 들어올 위험이 없다 — 기존
    # search_kdca_health_info_by_title()과 동일한 필터 방식.
    store = get_vectorstore()
    where = {"title": args.title} if args.title else {"doc_type": "kdca_health_info"}
    result = store.get(where=where)
    actual: Counter[str] = Counter(m.get("title", "") for m in result.get("metadatas", []))

    titles = sorted(set(expected) | set(actual))
    missing_entirely = [t for t in titles if expected[t] > 0 and actual[t] == 0]
    partial_mismatch = [t for t in titles if expected[t] > 0 and 0 < actual[t] != expected[t]]

    print(f"jsonl 기대 섹션 수: {sum(expected.values())}건 ({len(expected)}개 제목)")
    print(f"벡터DB 실제 섹션 수: {sum(actual.values())}건 ({len([t for t in actual if actual[t] > 0])}개 제목)")
    print()

    if missing_entirely:
        print(f"❌ 벡터DB에 전혀 없는 제목 {len(missing_entirely)}건 (재인제스트 필요 가능성):")
        for t in missing_entirely:
            print(f"   - {t}: jsonl {expected[t]}건 / DB 0건")
    if partial_mismatch:
        print(f"⚠️  건수가 어긋나는 제목 {len(partial_mismatch)}건:")
        for t in partial_mismatch:
            print(f"   - {t}: jsonl {expected[t]}건 / DB {actual[t]}건")
    if not missing_entirely and not partial_mismatch:
        print("✅ 대조 대상 전부 jsonl과 벡터DB 건수가 일치합니다.")

    if missing_entirely or partial_mismatch:
        sys.exit(1)


if __name__ == "__main__":
    main()
