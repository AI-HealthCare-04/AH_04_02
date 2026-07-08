import argparse
import json

from rag_prototype.chunking import drugs_to_documents, lifestyle_guidelines_to_documents
from rag_prototype.lifestyle_data import load_lifestyle_guidelines
from rag_prototype.mfds_client import fetch_page, search_by_name
from rag_prototype.rag_chain import generate_guide
from rag_prototype.vectorstore import add_documents, add_lifestyle_documents


def cmd_ingest(args: argparse.Namespace) -> None:
    drugs = []
    if args.item_names:
        for name in args.item_names.split(","):
            name = name.strip()
            if not name:
                continue
            found = search_by_name(name, num_of_rows=args.per_name)
            print(f"[ingest] '{name}' -> {len(found)}건")
            drugs.extend(found)
    if args.pages:
        for page in range(1, args.pages + 1):
            page_items, total = fetch_page(num_of_rows=args.num_of_rows, page_no=page)
            print(f"[ingest] page {page}/{args.pages} -> {len(page_items)}건 (전체 {total}건)")
            drugs.extend(page_items)

    if not drugs:
        print("수집된 의약품이 없습니다. --item-names 또는 --pages를 지정하세요.")
        return

    documents = drugs_to_documents(drugs)
    count = add_documents(documents)
    print(f"[ingest] 완료: 의약품 {len(drugs)}건 -> 청크 {count}건 저장")


def cmd_ingest_lifestyle(args: argparse.Namespace) -> None:
    guidelines = load_lifestyle_guidelines()
    documents = lifestyle_guidelines_to_documents(guidelines)
    count = add_lifestyle_documents(documents)
    print(f"[ingest-lifestyle] 완료: 생활지침 {len(guidelines)}건 -> 청크 {count}건 저장")


def cmd_query(args: argparse.Namespace) -> None:
    guide = generate_guide(args.drug, situation=args.situation, diagnosis=args.diagnosis)
    print(json.dumps(guide.model_dump(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag_prototype", description="식약처 의약품 데이터 기반 RAG 프로토타입")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="식약처 API에서 의약품 데이터를 수집해 벡터DB에 저장")
    ingest_parser.add_argument("--item-names", help="쉼표로 구분한 품목명 목록 (부분 일치 검색)")
    ingest_parser.add_argument("--per-name", type=int, default=3, help="품목명 1건당 가져올 최대 결과 수")
    ingest_parser.add_argument("--pages", type=int, default=0, help="전체 목록에서 가져올 페이지 수 (샘플 대량 수집용)")
    ingest_parser.add_argument("--num-of-rows", type=int, default=100, help="페이지당 항목 수")
    ingest_parser.set_defaults(func=cmd_ingest)

    ingest_lifestyle_parser = sub.add_parser(
        "ingest-lifestyle", help="data/lifestyle_guidelines.json의 만성질환 생활지침을 벡터DB에 저장"
    )
    ingest_lifestyle_parser.set_defaults(func=cmd_ingest_lifestyle)

    query_parser = sub.add_parser("query", help="약품명으로 복약/생활습관 가이드를 생성")
    query_parser.add_argument("--drug", required=True, help="약품명 (정확한 품목명 권장)")
    query_parser.add_argument("--situation", default=None, help="환자 상황 (예: 고령, 신장질환 있음)")
    query_parser.add_argument("--diagnosis", default=None, help="진단명 (예: 고혈압) — 만성질환 생활지침 인용에 사용")
    query_parser.set_defaults(func=cmd_query)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
