"""건강보험심사평가원 약가마스터·의약품표준코드 CSV 로컬 조회.

e약은요(mfds_client.py)와 원천이 다른 로컬 데이터 — 효능효과 같은 설명문은 없지만,
표준코드·ATC코드·허가일자·취소일자 등 e약은요에 없는 코드성 정보를 담고 있다.
backend/data/hira_drug_master_20251031.csv (약 30.5만 행, CP949 인코딩) 기준.

이 CSV는 backend/drug_matcher.py(OCR 약품 매칭)도 함께 참조하는 파일이라, 54MB 파일을
두 곳에 중복 보관하지 않도록 backend/data/ 한 곳만 두고 여기서는 그 경로를 가리킨다.
"""

import csv
from functools import lru_cache
from pathlib import Path

from rag_prototype.schemas import HiraDrugMasterEntry

DEFAULT_HIRA_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "data" / "hira_drug_master_20251031.csv"
)


@lru_cache(maxsize=4)
def _load_raw_index(path_str: str) -> dict[str, list[dict]]:
    """CSV를 한글상품명 기준으로 그룹핑한 원시 dict 인덱스로 읽어들입니다 (최초 1회만 파싱, 프로세스 캐시).

    30만 행 규모라, 조회할 때마다 pydantic 모델로 변환하지 않고 raw dict으로만 인덱싱해둔다
    (실제 모델 검증은 검색으로 걸러진 소수 결과에 대해서만 수행 — search_by_product_name 참고).
    """
    csv_path = Path(path_str)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"HIRA 약가마스터 CSV가 없습니다.\n"
            f"  필요 경로: {csv_path}\n"
            f"  건강보험심사평가원 약가마스터(hira_drug_master_20251031.csv)를\n"
            f"  rag-prototype/data/ 폴더에 넣고 다시 실행해주세요.\n"
            f"  (파일 크기 약 52 MB, CP949 인코딩)"
        )
    index: dict[str, list[dict]] = {}
    with csv_path.open(encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            name = cleaned.get("한글상품명")
            if not name:
                continue
            index.setdefault(name, []).append(cleaned)
    return index


def _index(path: Path | None = None) -> dict[str, list[dict]]:
    resolved = path or DEFAULT_HIRA_CSV_PATH
    return _load_raw_index(str(resolved))


def search_by_product_name(name: str, limit: int = 10, path: Path | None = None) -> list[HiraDrugMasterEntry]:
    """한글상품명으로 조회합니다 — 정확히 일치하는 품목이 있으면 그것만, 없으면 부분일치로 폴백합니다."""
    index = _index(path)

    exact_rows = index.get(name)
    if exact_rows:
        return [HiraDrugMasterEntry.model_validate(row) for row in exact_rows[:limit]]

    matched_rows: list[dict] = []
    for item_name, rows in index.items():
        if name in item_name:
            matched_rows.extend(rows)
            if len(matched_rows) >= limit:
                break
    return [HiraDrugMasterEntry.model_validate(row) for row in matched_rows[:limit]]


def is_registered_and_active(name: str, path: Path | None = None) -> bool | None:
    """상품명으로 약가마스터에 등재돼 있는지, 등재돼 있다면 취소되지 않은 정상 상태인지 확인합니다.

    조회 결과가 아예 없으면(등재 안 된 상품명 등) 판단 불가로 None을 반환합니다.
    """
    results = search_by_product_name(name, path=path)
    if not results:
        return None
    return any(item.is_active for item in results)
