# RAG 실제 파이프라인 응답 샘플 & Result.tsx/MedGuide.tsx 호환 패치

- 작성일: 2026-07-08 (2026-07-09 재작성)
- 작성자: 김영혜
- 관련 PR: `fix/result-medguide-schema-compat_yunghye` → `feature/frontend-setup_sojung`
  (이전 버전은 PR #13 `feature/result-prescdetail-schema-compat_yunghye`였는데,
  그 사이 소정님이 Figma 디자인 기준으로 화면을 재구성하면서 `PrescriptionDetail.tsx`가
  대상 로직을 통째로 신규 `MedGuide.tsx`로 옮겨 PR #13이 CONFLICTING 상태가 됨 —
  PR #13은 닫고 이 문서/패치를 `MedGuide.tsx` 기준으로 다시 작성함)

## 배경

PR #11(RAG·챗봇 실연동) 머지 후 순현님이 "`RAG_PROVIDER`가 stub→real로 바뀌는 순간
`Result.tsx`가 깨질 수 있다"고 지적. 실제로 재현해보니 `guide.lifestyle_guide.diet`/
`exercise`가 실제 모양에는 아예 없어서 **`Cannot read properties of undefined`로
결과 화면이 크래시**나는 걸 확인했다. 실제 응답 모양을 이미 파악한 내가 직접 패치를
작성하고 소정님은 리뷰만 하는 것으로 역할을 조정했다(PR #13).

이후 소정님이 Figma 디자인 기준으로 화면을 재구성하면서 `PrescriptionDetail.tsx`가
diagnosis만 보여주는 화면으로 바뀌고, 가이드(복약 지도/생활습관) 렌더링은 신규
`MedGuide.tsx`(탭형 화면)로 옮겨졌다. PR #13이 고치려던 취약 지점(`.diet.avoid`,
`.exercise.type` 등 옵셔널 체크 없는 직접 접근)이 그대로 `MedGuide.tsx`에 있어서,
이 패치를 `Result.tsx` + `MedGuide.tsx` + `records.ts` 3개 파일 기준으로 다시
작성했다. `PrescriptionDetail.tsx`는 이제 이 데이터를 렌더링하지 않아 패치 대상에서
빠졌고, `PrescriptionReview.tsx`(처방전확인/수정 화면)는 여전히 OCR 필드만 다뤄서
무관함을 확인했다.

## 브랜치 상태 참고

`feature/frontend-setup_sojung`은 이미 `dev`(PR #11 포함)를 자체적으로 병합해둔
상태(`a1dc4b9`)라, 이전 버전 문서에 있던 `run_rag_stub`/HIRA `source_refs` 관련
우려는 해소됐다. 남은 별도 이슈는 `backend/drug_matcher.py` 중복(소정님 쪽에서
dev 버전 채택 + `drug_reference.py`에 `efficacy` 필드 추가로 정리 중, 이 PR과는
무관).
이번 패치(타입 optional화)는 어느 쪽 `rag_router.py`를 쓰든 안전하게 동작합니다.

## 실행 조건 (샘플 채취)

- 최신 `dev`(`57f73fb`, PR #11 머지 이후) 기준
- `.env`: `OCR_PROVIDER=mock`, `RAG_PROVIDER=real`, `CHAT_PROVIDER=real`
- 처방전: 아스피린(100mg, confidence 0.92), 로자탄(50mg, confidence 0.78), 진단 고혈압
- 처리 시간: 약 2건 처리에 57초 소요

## `POST /records` 실제 응답 (`guide` 부분, 실측)

```json
{
  "medication_guide": {
    "drugs": [
      {
        "drug_name": "아스피린",
        "medication_guide": "아스피린은 항혈소판제로, 혈액을 맑게 해줍니다. 성인은 1일 1회, 1정(100mg)을 식전에 충분한 물과 함께 복용하세요.",
        "precautions": ["장용정이므로 충분한 물과 함께 복용해야 합니다.", "소금 섭취를 줄여야 합니다.", "정기적으로 혈압을 체크해야 합니다."],
        "review_required": false,
        "review_flags": []
      },
      {
        "drug_name": "로자탄",
        "medication_guide": "로자탄은 고혈압 치료에 사용됩니다. 하루에 한 번 50mg을 복용하세요.",
        "precautions": ["의사와 상담 없이 약 복용을 중단하지 마세요.", "약 복용 중 부작용이 나타나면 즉시 의사에게 알리세요."],
        "review_required": true,
        "review_flags": ["ocr_low_confidence"]
      }
    ]
  },
  "lifestyle_guide": {
    "diagnosis": "고혈압",
    "guides": [
      "고혈압 관리 위해 소금 섭취를 하루 6g 이하로 줄이고, 적정 체중을 유지하세요. ...",
      "고혈압을 관리하기 위해 소금 섭취를 하루 6g 이하로 줄이고, 적정 체중을 유지하세요. ..."
    ]
  },
  "source_refs": [
    {
      "drug_name": "아스피린",
      "item_name": "초당아스피린장용정100mg(아스피린)",
      "field": "용법·용량",
      "hira_standard_code": "8806707006503",
      "hira_atc_code": "B01AC06",
      "hira_permit_date": "1997-01-17",
      "hira_active": true
    },
    {
      "drug_name": "아스피린",
      "disease": "고혈압",
      "category": "식이요법",
      "source": "대한고혈압학회 고혈압 진료지침; 질병관리청 심뇌혈관질환 예방관리수칙"
    }
  ]
}
```

## 스텁 vs 실제 — 뭐가 다르고 왜 크래시가 나는지

| 필드 | 스텁 | 실제 | 크래시 여부 |
|---|---|---|---|
| `medication_guide.drugs[i].dosage_text`/`caution` | 있음 | 없음(`medication_guide`/`precautions`로 대체) | 크래시 안 남 — `undefined`가 빈 값으로 렌더링될 뿐 |
| `lifestyle_guide.diet`/`exercise` | 있음 | **아예 없음**(`guides` 배열로 대체) | **크래시 남** — `undefined.avoid`/`undefined.type` 접근 시 TypeError |
| `source_refs[i].title`/`url` | 있음 | 없음(`item_name`/`disease` 등 구조화 필드로 대체) | 크래시 안 남 — 빈 문자열로만 표시 |

## 적용한 패치

- `frontend/src/api/records.ts`: `GuideDrug`/`LifestyleGuide`/`SourceRef` 타입의 필드를
  전부 optional로 바꾸고 스텁/실제 양쪽 필드를 함께 선언. `formatSourceRef()` 헬퍼 추가.
- `frontend/src/pages/Result.tsx` / `frontend/src/pages/MedGuide.tsx`: 어느
  필드가 있는지 보고 스텁/실제 어느 모양인지 판단해서 렌더링(`guide.lifestyle_guide.guides?.length`로
  분기 등). `MedGuide.tsx`는 "복약 지도"/"주의사항"/"생활습관" 탭 3곳 모두에 적용
  — **두 모드 다 크래시 없이 동작**, `RAG_PROVIDER`를 stub↔real 아무 때나 전환해도
  안전함.
- `PrescriptionDetail.tsx` / `PrescriptionReview.tsx`는 guide 데이터를 안 그려서(각각
  약물 목록만/OCR 필드만 다루는 화면) 이번 패치 대상이 아님 — 확인만 하고 안 건드림.
- 검증: `npx tsc -b` 통과, `npm run build` 통과, 위 실제 샘플 JSON과 기존 스텁 JSON
  양쪽으로 렌더링 로직을 직접 트레이스해 크래시 지점 없음을 확인.

## 소정님 리뷰 포인트

- 지금은 실제 파이프라인 안내 문구를 있는 그대로(`💊 안내 1`, `🌿 안내 1`처럼) 보여주는
  최소 대응입니다. UI/UX상 더 예쁘게 다듬고 싶으시면(예: 실제 diet/exercise 구조로
  다시 나누고 싶다든가) 편하게 고쳐주세요 — 지금 패치는 "크래시 안 나게"가 목적입니다.
- `review_required`/`review_flags`가 있으면 "AI 검토 필요" 문구를 추가했는데, 디자인에
  안 맞으면 빼셔도 됩니다.
