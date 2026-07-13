"""건강보험심사평가원 DUR(의약품안전사용서비스) 병용금기 목록 로컬 CSV 조회.

[2026-07-13] DUR Open API(getUsjntTabooInfoList03)는 활용신청 승인 대기 상태라 실제로
쓸 수 없어서(403 Forbidden, CONTRACT.md §7 참고), API 대신 공공데이터포털에서 받은
병용금기 CSV를 로컬 조회로 대체한다. hira_master.py와 동일한 패턴 — 87만 행 규모라
필요한 컬럼(제품명A/B, 상세정보)만 뽑아 품목명 -> [(상대 품목명, 사유)] 양방향 인덱스로
최초 1회만 파싱해 프로세스 캐시에 둔다.

backend/data/dur_usjnt_taboo_202606.csv
(건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_202606의 "병용금기" 파일,
약 87만 행, CP949 인코딩) 기준. 같은 폴더의 노인주의/연령금기/임부금기 파일은
이번에 다루는 병용금기(getUsjntTabooInfoList)와는 다른 DUR 카테고리라 아직 연동하지 않았다.
"""

import csv
from functools import lru_cache
from pathlib import Path

from rag_prototype.schemas import DurTabooInfo

DEFAULT_DUR_TABOO_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "dur_usjnt_taboo_202606.csv"
)


@lru_cache(maxsize=2)
def _load_taboo_index(path_str: str) -> dict[str, tuple[tuple[str, str], ...]]:
    """CSV를 품목명 기준 양방향 인덱스로 읽어들입니다 (최초 1회만 파싱, 프로세스 캐시).

    각 행의 제품명A/제품명B는 "이 둘을 같이 먹으면 안 된다"는 순서 없는 관계이므로,
    조회 방향에 상관없이 찾을 수 있도록 양쪽 이름 모두에 상대방을 등록해둔다.
    """
    csv_path = Path(path_str)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"DUR 병용금기 CSV가 없습니다.\n"
            f"  필요 경로: {csv_path}\n"
            f"  건강보험심사평가원 의약품안전사용서비스(DUR) 병용금기 목록 CSV를\n"
            f"  backend/data/ 폴더에 dur_usjnt_taboo_202606.csv 이름으로 넣고 다시 실행해주세요.\n"
            f"  (파일 크기 약 250 MB, CP949 인코딩)"
        )

    index: dict[str, list[tuple[str, str]]] = {}
    with csv_path.open(encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_a = (row.get("제품명A") or "").strip()
            item_b = (row.get("제품명B") or "").strip()
            detail = (row.get("상세정보") or "").strip()
            if not item_a or not item_b:
                continue
            index.setdefault(item_a, []).append((item_b, detail))
            index.setdefault(item_b, []).append((item_a, detail))

    # tuple로 고정해 이후 조회에서 실수로 원본 인덱스를 수정하는 걸 방지한다.
    return {name: tuple(pairs) for name, pairs in index.items()}


def _index(path: Path | None = None) -> dict[str, tuple[tuple[str, str], ...]]:
    resolved = path or DEFAULT_DUR_TABOO_CSV_PATH
    return _load_taboo_index(str(resolved))


def search_usjnt_taboo(item_name: str, path: Path | None = None) -> list[DurTabooInfo]:
    """품목명(부분일치)으로 병용금기 상대 목록을 조회합니다.

    정확히 일치하는 품목명이 있으면 그것만, 없으면 부분일치로 폴백합니다
    (hira_master.search_by_product_name과 동일한 정책). 못 찾으면 빈 리스트 —
    "이 약은 병용금기가 없다"는 의미가 아니라 "이 CSV에 해당 품목명이 등재돼 있지
    않다"는 뜻이므로 호출부에서 그렇게 해석하지 않도록 주의할 것.
    """
    index = _index(path)

    exact = index.get(item_name)
    if exact:
        pairs: tuple[tuple[str, str], ...] = exact
    else:
        matched: list[tuple[str, str]] = []
        for name, pairs_for_name in index.items():
            if item_name in name:
                matched.extend(pairs_for_name)
        pairs = tuple(matched)

    return [
        DurTabooInfo(item_name=item_name, mixture_item_name=partner, prohbt_content=detail or None)
        for partner, detail in pairs
    ]
