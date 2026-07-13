"""건강보험심사평가원 DUR(의약품안전사용서비스) 목록 로컬 CSV 조회.

[2026-07-13] DUR Open API(getUsjntTabooInfoList03)는 활용신청 승인 대기 상태라 실제로
쓸 수 없어서(403 Forbidden, CONTRACT.md §7 참고), API 대신 공공데이터포털에서 받은
CSV들을 로컬 조회로 대체한다. hira_master.py와 동일한 패턴 — 필요한 컬럼만 뽑아
품목명 인덱스로 최초 1회만 파싱해 프로세스 캐시에 둔다.

건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_202606에는 카테고리 5개가 있고,
**전부** backend/data/에 대응 파일이 있어야 한다 (처음엔 병용금기만 연동했다가, 나머지
카테고리도 함께 있다는 걸 뒤늦게 인지해서 이번에 추가함):

| 카테고리 | 파일 | 관계 종류 |
|---|---|---|
| 병용금기 | dur_usjnt_taboo_202606.csv (약 87만 행) | **약 두 개 사이의 관계** — 처방전에 상대 약이 실제로 있어야 경고 (search_usjnt_taboo) |
| 노인주의 | dur_elderly_caution_202606.csv (약 558행) | 약 하나의 속성 (search_elderly_caution) |
| 노인주의(해열진통소염제) | dur_elderly_caution_nsaid_202606.csv (약 1035행) | 약 하나의 속성 (search_elderly_caution) |
| 연령금기 | dur_age_taboo_202606.csv (약 2867행) | 약 하나의 속성 (search_age_taboo) |
| 임부금기 | dur_pregnancy_taboo_202606.csv (약 19521행) | 약 하나의 속성 (search_pregnancy_taboo) |

노인주의/연령금기/임부금기는 "이 환자에게 실제로 해당하는지"(나이·임신 여부)를 이 시스템이
모르므로 조건 판단 없이 정보성으로만 노출한다 (schemas.DurCaution 참고).
"""

import csv
from functools import lru_cache
from pathlib import Path

from rag_prototype.schemas import DurCaution, DurTabooInfo

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "data"

DEFAULT_DUR_TABOO_CSV_PATH = _DATA_DIR / "dur_usjnt_taboo_202606.csv"
DEFAULT_ELDERLY_CAUTION_CSV_PATH = _DATA_DIR / "dur_elderly_caution_202606.csv"
DEFAULT_ELDERLY_CAUTION_NSAID_CSV_PATH = _DATA_DIR / "dur_elderly_caution_nsaid_202606.csv"
DEFAULT_AGE_TABOO_CSV_PATH = _DATA_DIR / "dur_age_taboo_202606.csv"
DEFAULT_PREGNANCY_TABOO_CSV_PATH = _DATA_DIR / "dur_pregnancy_taboo_202606.csv"


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


@lru_cache(maxsize=8)
def _load_single_drug_rows(path_str: str) -> dict[str, tuple[dict, ...]]:
    """노인주의/연령금기/임부금기 CSV 공통 로더 — 전부 "제품명" 컬럼 기준으로 인덱싱한다.

    병용금기(제품명A/B 쌍)와 달리 이 CSV들은 행 하나가 "약 하나"의 속성이라
    양방향 인덱스가 필요 없다.
    """
    csv_path = Path(path_str)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"DUR CSV가 없습니다.\n"
            f"  필요 경로: {csv_path}\n"
            f"  건강보험심사평가원 의약품안전사용서비스(DUR) 의약품 목록의 해당 카테고리 CSV를\n"
            f"  backend/data/ 폴더에 위 파일명으로 넣고 다시 실행해주세요. (CP949 인코딩)"
        )
    index: dict[str, list[dict]] = {}
    with csv_path.open(encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("제품명") or "").strip()
            if not name:
                continue
            index.setdefault(name, []).append(row)
    return {name: tuple(rows) for name, rows in index.items()}


def _lookup_single_drug_rows(item_name: str, path: Path) -> list[dict]:
    """정확 일치 우선, 없으면 부분일치 폴백 (search_usjnt_taboo와 동일 정책)."""
    index = _load_single_drug_rows(str(path))

    exact = index.get(item_name)
    if exact:
        return list(exact)

    matched: list[dict] = []
    for name, rows in index.items():
        if item_name in name:
            matched.extend(rows)
    return matched


def _dedupe_cautions(cautions: list[DurCaution]) -> list[DurCaution]:
    """부분일치 조회 시 같은 성분의 제조사별 제품이 CSV에 각각 행으로 등재돼 있어,
    (카테고리, 사유, 부가정보)가 완전히 같은 경고가 수십 건씩 중복될 수 있다
    (_check_dur_taboo의 브랜드 중복 제거와 같은 문제 — 실측: "아스피린" 하나로 노인주의
    47건, 임부금기 59건 발생). item_name은 어차피 검색어로 고정돼 있으므로
    (category, detail, extra) 조합 기준으로 한 번만 남긴다.
    """
    seen: set[tuple[str, str | None, str | None]] = set()
    deduped: list[DurCaution] = []
    for c in cautions:
        key = (c.category, c.detail, c.extra)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def search_elderly_caution(
    item_name: str,
    elderly_path: Path | None = None,
    nsaid_path: Path | None = None,
) -> list[DurCaution]:
    """품목명(부분일치)으로 노인주의 정보를 조회합니다 (일반 노인주의 + 해열진통소염제 전용 목록 둘 다).

    이 서비스의 주 사용자층(고령 만성질환자)과 직접 관련된 카테고리라 다른 카테고리보다
    우선순위가 높다.
    """
    results = []
    for row in _lookup_single_drug_rows(item_name, elderly_path or DEFAULT_ELDERLY_CAUTION_CSV_PATH):
        results.append(
            DurCaution(item_name=item_name, category="노인주의", detail=(row.get("약품상세정보") or "").strip() or None)
        )
    for row in _lookup_single_drug_rows(item_name, nsaid_path or DEFAULT_ELDERLY_CAUTION_NSAID_CSV_PATH):
        results.append(
            DurCaution(
                item_name=item_name,
                category="노인주의(해열진통소염제)",
                detail=(row.get("약품상세정보") or "").strip() or None,
            )
        )
    return _dedupe_cautions(results)


def search_age_taboo(item_name: str, path: Path | None = None) -> list[DurCaution]:
    """품목명(부분일치)으로 연령금기(특정 연령대 사용 금지) 정보를 조회합니다."""
    results = []
    for row in _lookup_single_drug_rows(item_name, path or DEFAULT_AGE_TABOO_CSV_PATH):
        age = f"{(row.get('특정연령') or '').strip()}{(row.get('특정연령단위') or '').strip()}".strip()
        condition = (row.get("연령처리조건") or "").strip()
        extra = f"{age} {condition}".strip() if (age or condition) else None
        results.append(
            DurCaution(
                item_name=item_name,
                category="연령금기",
                detail=(row.get("상세정보") or "").strip() or None,
                extra=extra,
            )
        )
    return _dedupe_cautions(results)


def search_pregnancy_taboo(item_name: str, path: Path | None = None) -> list[DurCaution]:
    """품목명(부분일치)으로 임부금기 정보를 조회합니다."""
    results = []
    for row in _lookup_single_drug_rows(item_name, path or DEFAULT_PREGNANCY_TABOO_CSV_PATH):
        grade = (row.get("금기등급") or "").strip()
        results.append(
            DurCaution(
                item_name=item_name,
                category="임부금기",
                detail=(row.get("상세정보") or "").strip() or None,
                extra=f"금기등급 {grade}" if grade else None,
            )
        )
    return _dedupe_cautions(results)
