# 약품명 매칭 모듈 (drug_reference.py와 짝을 맞춘 버전)

## 먼저 정리: `drug_reference.py`랑 뭐가 다른가

권순현님 PR의 `drug_reference.py`를 보고 확인했어요 — **중복이 아니라 역할이 다릅니다.**

| | `drug_reference.py` (권순현, 기존) | `drug_matcher.py` (이번 파일) |
|---|---|---|
| 질문 | "이 약이 무슨 효능군인가?" | "OCR이 읽은 이름이 실제 등록 의약품과 일치하는가?" |
| 출력 | `drug_class` (예: "항혈소판제") | `matched_name`, `score`, `needs_review` |
| 용도 | RAG 가이드 생성, 화면 표시용 분류 | 검증 게이트 — 애매하면 review_required로 걸러냄 |
| 매칭 방식 | 코드/이름 부분일치 → ATC패턴 → 하드코딩 폴백 (5단계) | e약은요→HIRA 순 정규화 정확일치 → 퍼지매칭(rapidfuzz) |

**둘 다 필요하고, 같은 데이터 파일을 그대로 재사용하도록 맞췄습니다.** 처음에 드렸던 버전은 제가
데이터를 따로 가공해서 파일명도 다르고 중복 저장되는 문제가 있었는데, 이번 버전은 그 문제를 없앴어요.

## 필요한 파일 (이제 2개만)

```
backend/
├── drug_reference.py       ← 이미 있음 (권순현님 PR로 반영됨, 손댈 필요 없음)
├── drug_matcher.py         ← 이번에 추가
└── data/
    ├── hira_drug_master_20251031.csv   ← 원본 그대로 (30.5만행, CP949)
    └── 2_e약은요_정리.xlsx              ← 원본 그대로 (4,809건)
```

`data/` 폴더에 이 두 파일만 넣으면 `drug_reference.py`의 1~3순위(HIRA/e약은요 기반 분류)와
`drug_matcher.py`가 **동시에** 활성화됩니다. 이전처럼 가공된 CSV를 별도로 만들 필요 없어요.

두 파일 다 원본 그대로라 총 53MB 정도예요. git에 커밋하기 부담스러우면 `.gitignore` 처리하고
팀 드라이브에 올려서 각자 받는 방법도 괜찮습니다 (`drug_reference.py`의 데이터도 어차피 같은 파일이라
한 번만 받으면 됨).

## 사용법

```python
from drug_matcher import match_drug_name

result = match_drug_name("타이레놀정500mg")
# {
#   "matched": True,
#   "matched_name": "타이레놀정500밀리그람(아세트아미노펜)",
#   "score": 80.0,
#   "source": "easy_drug",
#   "needs_review": True,   # mg ↔ 밀리그람 표기 차이라 90점 미만 → 검토 필요
#   "efficacy": "이 약은 두통, 치통...",
#   "ingredient_code": None,
#   "atc_code": None,
# }
```

`drug_reference.py`의 `get_drug_class()`와 함수 스타일(모듈 레벨 함수 + 지연 로드 + 조용한 폴백)을
그대로 맞췄어요. 같은 파일 안에서 pandas/openpyxl/rapidfuzz 중 뭐가 없어도, 데이터 파일이 없어도
예외 없이 "매칭 실패"로 조용히 넘어가도록 만들었습니다 (기존 파일 설계 원칙 그대로 따름).

## `run_ocr()` / `records_router.py`에 같이 붙이는 예시

```python
from drug_reference import get_drug_class
from drug_matcher import match_drug_name

def enrich_extracted_medication(item: dict) -> dict:
    match = match_drug_name(item["drug_name"])
    item["matched_drug_name"] = match["matched_name"]
    item["match_score"] = match["score"]
    item["needs_review"] = match["needs_review"] or not match["matched"]

    # drug_class는 매칭된 정식명이 있으면 그걸로, 없으면 원본 이름으로 시도
    lookup_name = match["matched_name"] or item["drug_name"]
    item["drug_class"] = get_drug_class(lookup_name, drug_code=item.get("drug_code", ""))
    return item
```

## DB 스키마

`ocr_results`(또는 `extracted_medications`)에 추가 권장 컬럼:
- `matched_drug_name` (str, nullable)
- `match_score` (float, nullable)
- `needs_review` (bool, default False)

⚠️ `models.py` 수정 후 `rm -f backend/app.db` 하고 서버 재시작 필요 (SQLite 컬럼 자동추가 안 됨).

## 임계값 튜닝

```python
SCORE_AUTO_ACCEPT = 90   # 이상이면 자동 신뢰
SCORE_NEEDS_REVIEW = 70  # 이상~90 미만이면 매칭은 되지만 검토 필요 표시
```

실제 처방전 OCR 데이터로 몇 건 테스트해보면서 조정하시면 됩니다.
