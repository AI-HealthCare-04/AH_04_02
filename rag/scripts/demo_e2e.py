"""2주차 목요일 완료 기준 데모: 의약품 10건 확보 -> top-3 검색 -> 가이드 1건 생성."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.chunking import drugs_to_documents  # noqa: E402
from rag.mfds_client import search_by_name  # noqa: E402
from rag.rag_chain import generate_guide  # noqa: E402
from rag.vectorstore import add_documents  # noqa: E402

SAMPLE_DRUG_NAMES = [
    "타이레놀정500밀리그람(아세트아미노펜)",
    "아스피린프로텍트정100밀리그람",
    "노바스크정5밀리그람(암로디핀베실산염)",
    "글루코파지정500밀리그램(메트포르민염산염)",
    "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)",
    "플라빅스정75밀리그램(클로피도그렐황산염)",
    "낙센정(나프록센)",
    "아모잘탄정5/50밀리그램",
    "크레스토정10밀리그램(로수바스타틴칼슘)",
    "자누비아정100밀리그램(시타글립틴인산염수화물)",
]


def main() -> None:
    print("=== 1. 의약품 샘플 데이터 확보 ===")
    all_drugs = []
    for name in SAMPLE_DRUG_NAMES:
        found = search_by_name(name, num_of_rows=1)
        if found:
            print(f"  - {name}: {found[0].item_name} (itemSeq={found[0].item_seq})")
            all_drugs.append(found[0])
        else:
            print(f"  - {name}: 검색 결과 없음")

    print(f"\n총 {len(all_drugs)}건 확보")

    print("\n=== 2. 벡터DB(ChromaDB) 저장 ===")
    documents = drugs_to_documents(all_drugs)
    count = add_documents(documents)
    print(f"청크 {count}건 저장 완료")

    if not all_drugs:
        print("확보된 데이터가 없어 가이드 생성을 건너뜁니다.")
        return

    target = all_drugs[0].item_name
    print(f"\n=== 3. 가이드 생성 테스트: '{target}' ===")
    guide = generate_guide(target, situation="고령, 다약물 복용 중")
    print(f"\n(참고) top-{len(documents)} 청크 중 '{target}' 관련 검색 결과를 사용했습니다.")
    print(json.dumps(guide.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
