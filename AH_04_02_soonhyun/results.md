# OCR 실측 결과 보고서

> 측정일: 2026-07-03  
> 엔진: CLOVA OCR (primary) / Tesseract 5.5.2 (fallback)  
> `review_required` 기준: `overall_confidence < 0.80`

---

## 1. 실행 결과 요약

| # | 샘플 | 엔진 | 감지 포맷 | medications | confidence | review_required |
|---|------|------|-----------|:-----------:|:----------:|:---------------:|
| 1 | prescription_01.jpg | CLOVA | table | 7개 | 0.9147 | false |
| 2 | mock_prescription_table.png | CLOVA | table | 3개 | 0.9350 | false |
| 3 | mock_prescription_bag.png | CLOVA | list | 3개 | 0.8497 | false |
| 4 | mock_prescription_abbrev.png | CLOVA | abbrev | 3개 | 0.7811 | **true** |
| 5 | mock_prescription_official.png | CLOVA | official | 4개 | 0.9564 | false |
| 6 | mock_pharmacy_bag_format.png | CLOVA | table | 5개¹ | 0.9651 | false |
| 7 | mock_prescription_table.png | Tesseract | table | 3개² | 0.0³ | true |

> ¹ 5개 중 2개(메트포르민염산, 암로디핀베실)는 성분명 오인식 — 실제 브랜드 3개  
> ² 약품명만 추출, dosage·frequency 빈값  
> ³ pytesseract는 신뢰도를 제공하지 않아 0.0 고정

---

## 2. 샘플별 상세 결과

### 2-1. prescription_01.jpg (실제 처방전)
- **confidence**: 0.9147 / **포맷**: table
- **medications** (7개):

| 약품명 | dosage | frequency | days |
|--------|--------|-----------|------|
| 케이캡 | 50mg | _(빈값)_ | _(빈값)_ |
| 엑세그란 | _(빈값)_ | _(빈값)_ | _(빈값)_ |
| 가스모틴 | 5mg | _(빈값)_ | _(빈값)_ |
| 마도파 | _(빈값)_ | _(빈값)_ | _(빈값)_ |
| 뉴로메드 | 800mg | _(빈값)_ | _(빈값)_ |
| 프라닥사 | 110mg | _(빈값)_ | _(빈값)_ |
| 메바로친 | 20mg | _(빈값)_ | _(빈값)_ |

- **미해결**: `"7 회"` 처럼 숫자와 '회' 사이 공백이 있는 비표준 표기로 `KOR_FREQ_RE` 미검출, frequency 전량 빈값. Day2 이후 실샘플 기반 보강 필요 (TODO 주석 기록됨).

---

### 2-2. mock_prescription_table.png (테이블형 목업)
- **confidence**: 0.9350 / **포맷**: table / **diagnosis**: 고혈압, 제2형 당뇨병
- **medications** (3개):

| 약품명 | dosage | frequency | days | drug_class |
|--------|--------|-----------|------|------------|
| 암로디핀 | 5mg | 1일 1회 | 30일 | 칼슘채널차단제 |
| 로자탄칼륨 | 50mg | 1일 2회 | 30일 | ARB(안지오텐신수용체차단제) |
| 메트포르민 | 500mg | 1일 1회 | 30일 | 당뇨병용제(비구아니드) |

---

### 2-3. mock_prescription_bag.png (약봉투 리스트형 목업)
- **confidence**: 0.8497 / **포맷**: list / **diagnosis**: 관상동맥질환, 위염
- **medications** (3개):

| 약품명 | dosage | frequency | days | drug_class |
|--------|--------|-----------|------|------------|
| 아스피린프로텍트 | 100mg | 1일 1회 | 30일 | 항혈소판제 |
| 심바스타틴 | 20mg | 1일 1회 | 30일 | HMG-CoA환원효소억제제(스타틴) |
| 오메프라졸 | 20mg | 1일 1회 | 30일 | 양성자펌프억제제(PPI) |

---

### 2-4. mock_prescription_abbrev.png (약어 처방전 목업)
- **confidence**: 0.7811 → **review_required: true** / **포맷**: abbrev / **diagnosis**: 골관절염, 불면증
- **medications** (3개):

| 약품명 | dosage | frequency | days | drug_class |
|--------|--------|-----------|------|------------|
| 세레브렉스 | 200mg | 1일 2회 | 14일 | COX-2선택적억제제(NSAIDs) |
| 졸피뎀 | 10mg | 1일 1회 | 7일 | 수면유도제(비벤조디아제핀계) |
| 파모티딘 | 20mg | 1일 2회 | 14일 | H2수용체차단제 |

- **확인**: `bid` → "1일 2회", `qd` → "1일 1회" 변환 정상 동작

---

### 2-5. mock_prescription_official.png (공식 처방전 포맷 목업)
- **confidence**: 0.9564 / **포맷**: official / **diagnosis**: 무릎관절증
- **medications** (4개):

| 약품명 | dosage | frequency | days |
|--------|--------|-----------|------|
| 세레콕시브 | 200mg | 1일 2회 | 7일 |
| 에페리손염산염 | 50mg | 1일 3회 | 7일 |
| 라베프라졸나트륨장용 | _(빈값)_ | 1일 1회 | 7일 |
| 조인트콘드로이친 | _(빈값)_ | 1일 1회 | 1일 |

- **확인**: `[급여][코드]` 접두어 건너뜀, `질병분류기호:M17 (무릎관절증)` → diagnosis 정상 추출
- **확인**: 자유서술형 용법("1일 1회 취침전 복용하세요") → frequency 정상 파싱
- **확인**: 복합 용량 `110/500` → col_nums 룩어헤드로 자동 제외

---

### 2-6. mock_pharmacy_bag_format.png (약봉투 테이블형 목업)
- **confidence**: 0.9651 / **포맷**: table (오감지¹)
- **medications** (파서 출력 5개, 실제 브랜드 3개):

| 약품명 | 실제 여부 | dosage | frequency | 비고 |
|--------|-----------|--------|-----------|------|
| 글루코파지 | ✅ 정상 | 500mg | 1일 2회 | 복약안내 문장에 "1일 2회" 포함 |
| 메트포르민염 | ❌ 오인식 | _(빈값)_ | _(빈값)_ | 성분명(-산) 제형 패턴 오매칭 |
| 노바스크 | ✅ 정상 | 5mg | _(빈값)_ | 복약안내 "아침 식후" → KOR_FREQ_RE 미검출 |
| 암로디핀베실 | ❌ 오인식 | _(빈값)_ | _(빈값)_ | 성분명(-산) 제형 패턴 오매칭 |
| 리피토 | ✅ 정상 | 10mg | _(빈값)_ | 복약안내 "저녁 식후" → KOR_FREQ_RE 미검출 |

> ¹ `[급여][코드]` 없고 `bid/qd` 없어 table로 감지되나, 순수 숫자 컬럼 포맷

- **진단 (정규식 한계)**: 순수 숫자 컬럼(1 2 30 / 1 1 30 / 1 1 30) 포맷은 CLOVA flat string에서 행 소속 정보가 소실되어 **정규식으로 해결 불가**. `fields[].boundingPoly.vertices` y좌표 기반 행 그룹핑 필요.

---

### 2-7. mock_prescription_table.png — Tesseract fallback
- **confidence**: 0.0 (pytesseract 신뢰도 미제공 → 고정값) / **review_required**: true
- **medications** (3개, 약품명만):

| 약품명 | dosage | frequency | 비고 |
|--------|--------|-----------|------|
| 암로디핀 | _(빈값)_ | _(빈값)_ | "5mg" → "5078" 오인식 |
| 로자탄칼륨 | _(빈값)_ | _(빈값)_ | "50mg" → "50078" 오인식 |
| 메트포르민 | _(빈값)_ | _(빈값)_ | "500mg" → "500008" 오인식 |

- **diagnosis**: 고혈압, 제2형 당뇨병 (정상 추출)
- **결론**: 약품명·진단명 추출까지만 기대 가능. CLOVA 장애 시 폴백 용도.

---

## 3. 파싱 정확도 요약

| 항목 | 결과 |
|------|------|
| 지원 포맷 | 4종 (official / abbrev / list / table) |
| 약품명 추출 성공률 | 목업 5종 기준 100% (오인식 제외 시) |
| frequency 정상 파싱 | table·list·official·abbrev 목업 전체 ✅ |
| bid/qd 약어 변환 | ✅ 확인 |
| diagnosis 추출 | 진단명: / Dx: / 질병분류기호: 3종 모두 ✅ |
| 약봉투 테이블형 frequency | ❌ bounding box 필요 (미구현) |
| Tesseract dosage 추출 | ❌ mg 오인식 |

---

## 3-1. drug_class 정확도 — 단계별 개선 이력

> 테스트셋: 기존 9개 + 신규 14개 = 23개 약품 (2026-07-04 기준)

| 단계 | 구현 | 정확도 | 비고 |
|------|------|:------:|------|
| 초기 | `parsing_rules.py` 하드코딩 사전 | 9/23 (39%) | 브랜드명·전문의약품 전량 빈값 |
| Day1-v1 | ATC 패턴 정규식(1) + e약은요 DB(2) + 폴백(3) | 23/23 (100%) | 성분명 패턴 기반, 브랜드명 한계 |
| **Day1-v2** | **HIRA 약가마스터(1) + e약은요(2) + ATC 패턴(3) + 폴백(4)** | **23/23 (100%)** | **브랜드명 직접 매칭, ATC 코드 실거래 데이터** |

### Day1-v2 HIRA 연동 결과 (2026-07-04)

> 데이터: 건강보험심사평가원 약가마스터 20251031 (30.5만 건, ATC 코드 23.4만 건)  
> 매칭 방식: 한글상품명 startswith + 제형접두(정/캡/주/산) 단일제 우선 → ATC 코드 → drug_class

| 약품명 | 소스 | ATC 코드 | drug_class | 이전 상태 |
|--------|------|----------|------------|-----------|
| 케이캡 | hira_name | A02BC09 | 양성자펌프억제제(PPI) | ❌ 빈값 |
| 엑세그란 | hira_name | N03AX15 | 항경련제 | ❌ 빈값 |
| 가스모틴 | hira_name | A03FA09 | 위장운동촉진제 | ✅ (ATC 패턴) |
| 마도파 | hira_name | N04BA02 | 파킨슨치료제(레보도파계) | ❌ 빈값 |
| 뉴로메드 | hira_name | N06BX07 | 인지기능개선제 | ❌ 빈값 |
| 프라닥사 | hira_name | B01AE07 | 항응고제(직접트롬빈억제제) | ✅ (ATC 패턴) |
| 메바로친 | hira_name | C10AA03 | HMG-CoA환원효소억제제(스타틴) | ❌ 빈값 |
| 자낙스 | hira_name | N05BA12 | 항불안제(벤조디아제핀계) | ❌ 빈값 |
| 렉사프로 | hira_name | N06AB10 | SSRI(항우울제) | ❌ 빈값 |
| 스틸녹스 | hira_name | N05CF02 | 수면유도제(비벤조디아제핀계) | ❌ 빈값 |
| 리피토 | hira_name | C10AA05 | HMG-CoA환원효소억제제(스타틴) | ✅ (ATC 패턴) |
| 엘리퀴스 | hira_name | B01AF02 | 항응고제(직접Xa인자억제제) | ✅ (ATC 패턴) |

> **수정 이슈 2건**: 케이캡→엘도스케이캡슐 오매칭(startswith 우선순위 도입으로 해결),  
> 리피토→리피토플러스 오매칭(제형접두 단일제 필터로 해결)

---

## 4. 현재 파이프라인 (Day1-v2)

```
이미지 파일
   ↓
CLOVA OCR API (base64 전송, fields[].inferText 병합)
   ↓
parsing_rules.parse_prescription()
  ├─ 포맷 감지: [급여/비급여] → official
  │              bid/qd      → abbrev
  │              번호+약품명  → list
  │              기본         → table
  ├─ 약품명·용량·횟수·일수·진단명 정규식 추출
  └─ drug_reference.get_drug_class(drug_name, drug_code) 약효 분류
       ├─ 1. HIRA 약가마스터 — 품목기준코드 exact 매칭 → ATC코드 (30.5만 건)
       ├─ 2. HIRA 약가마스터 — 한글상품명 startswith + 제형접두 단일제 매칭 → ATC코드
       ├─ 3. e약은요 DB — 일반의약품(OTC) 부분/유사도 매칭 + efcyQesitm 분류 (4,809건)
       ├─ 4. ATC 패턴 정규식 (성분명 기반 하드코딩, 30종)
       └─ 5. 하드코딩 폴백 사전 (17종)
   ↓
OCRResult { raw_text, medications[], overall_confidence,
            review_required, source }
```

**Tesseract fallback**: CLOVA 키 미설정 또는 장애 시 사용. 약품명·진단명만 신뢰.

---

---

## 2-8. mock_dental_bag.png (치과 약봉투)
- **confidence**: 0.9119 / **포맷**: list / **review_required**: false
- **medications** (2개):

| 약품명 | dosage | frequency | diagnosis | drug_class | 비고 |
|--------|--------|-----------|-----------|------------|------|
| 아모클란 | 375mg | 1일 3회 | _(빈값)_ | _(빈값)_ | 정상 추출 |
| 프로 | _(빈값)_ | 1일 3회 | _(빈값)_ | **항혈소판제** | ❌ OCR이 "이지엔6프로연질캡슐"을 분리 인식, ATC 패턴 오매칭 |

- **잔존 이슈**: "프로" 2자 이하 단편명 — `_lookup_emedinfo` 2자 미만 가드로 e약은요 오매칭은 방지됐으나, ATC 패턴의 부분 일치(`프로스타글란딘|프로부코` 등)로 항혈소판제 오분류 지속. Day2 대응: ATC 패턴에 단어 경계(`\b`) 추가.

---

## 2-9. mock_oriental_medicine.png (한방 첩약)
- **confidence**: 0.9238 / **포맷**: _(감지 불가)_ / **review_required**: false
- **medications**: **0개** (예상 동작)
- 십전대보탕 등 한방 첩약은 형태소(정/캡슐/주/산/시럽/액) 없음 → 기존 4-포맷 파서 전부 미매칭. **별도 한방처방전 파서 필요** (미구현, Day3 이후).

---

## 2-10. mock_pediatric.png (소아청소년과)
- **confidence**: 0.9342 / **포맷**: list / **review_required**: false
- **medications** (2개):

| 약품명 | dosage | frequency | diagnosis | drug_class | 비고 |
|--------|--------|-----------|-----------|------------|------|
| 오구멘틴 | 5mL | 1일 2회 | 급성 중이염 | _(빈값)_ | ✅ 시럽 포맷 정상 |
| 지르텍 | 2.5mL | 1일 1회 | 급성 중이염 | 항히스타민제 | ✅ drug_class 정상 |

- **수정 내역**: list 감지 정규식에 `시럽|액|주|산` 추가 → table 오감지 수정 후 5mL/2.5mL 정상 추출
- **잔존 이슈**: `오구멘틴` 브랜드명 미등록 → drug_class 빈값 (ATC J01 항생제 패턴 미포함)

---

## 2-11. mock_psychiatry.png (정신건강의학과)
- **confidence**: 0.9505 / **포맷**: list / **review_required**: false
- **medications** (3개):

| 약품명 | dosage | frequency | diagnosis | drug_class | 소스 |
|--------|--------|-----------|-----------|------------|------|
| 자낙스 | 0.25mg | 1일 2회 | F41.1 범불안장애 | 항불안제(벤조디아제핀계) | hira_name (N05BA12) |
| 렉사프로 | 10mg | 1일 1회 | F41.1 범불안장애 | SSRI(항우울제) | hira_name (N06AB10) |
| 스틸녹스 | 10mg | 1일 1회 | F41.1 범불안장애 | 수면유도제(비벤조디아제핀계) | hira_name (N05CF02) |

- **수정 내역**: `_split_by_number` — `(?<![A-Za-z가-힣])\d+\s*[).](?!\d)` 로 F41.1 오분할 방지 → 자낙스 dosage·frequency 정상 복원
- **HIRA 연동 후**: 브랜드명 3종 모두 HIRA 한글상품명 매칭으로 drug_class 자동 분류 ✅ (이전 전량 빈값)

---

## 2-12. mock_university_hospital.png (대학병원 다과 협진)
- **confidence**: 0.9194 / **포맷**: official / **review_required**: false
- **medications** (4개):

| 약품명 | dosage | frequency | diagnosis | drug_class | 비고 |
|--------|--------|-----------|-----------|------------|------|
| 자누메트 | 1000mg | 1일 2회 | 제2형 당뇨병, 이상지질혈증, 본태성 고혈압, 심방세동 | _(빈값)_ | 복합제 브랜드명 미등록 |
| 아토젯 | 40mg | 1일 1회 | 〃 | HMG-CoA환원효소억제제(스타틴) | ✅ ATC C10 패턴 매칭 |
| 엘리퀴스 | 5mg | 1일 2회 | 〃 | 항응고제 | ✅ |
| 오메가3 | _(빈값)_ | 1일 1회 | 〃 | _(빈값)_ | dosage 없음 (성분명 패턴) |

- **수정 내역 3가지**:
  1. `DRUG_NAME_RE`에 `(?:\d+)?(?:연질)?` 추가 → 오메가3연질캡슐 인식
  2. col_nums 룩어헤드에서 `|회|번` 제거 → "1정 2회 30일" frequency 정상 추출
  3. `DIAGNOSIS_KOR_RE` `진단(?:명)?` → 2개 과 복수 진단명 모두 수집
- **잔존 이슈**: 자누메트(메트포르민+자누비아 복합제) 브랜드명 미등록, 오메가3 dosage 빈값(복용량 미기재)

---

## 5. MFDS 공공데이터포털 API 연동 현황

> MFDS 공공데이터포털 API는 2026-07-03 저녁 기준 게이트웨이 자체 장애(500 에러 13회 연속)로 연동 보류.
> 키/코드는 정상 발급 확인됨. 서버 복구 후 재시도 필요.
> 당장은 drug_reference.py(e약은요 로컬 데이터)로 충분히 커버됨.
>
> e약은요 DB는 OTC(일반의약품) 중심이라 전문의약품 매칭에는 사용하지 않음.
> 전문의약품 drug_class 분류는 ATC 코드 기반 정규식 패턴으로 처리.
> (2026-07-04, 팀원 확인 후 명시)

---

## 7. Day3-4 완료 (2026-07-06)

- `ocr_router.py`에 실제 CLOVA OCR 연동 완료 (가짜 데이터 제거)
- `monitoring_router.py` prefix 버그 수정 (`/monitoring` 누락 발견 및 수정)
- `review_required` 로직 실제 검증 완료: confidence 0.80 미만 시 `review_required=true`, `status="review_required"`로 정상 전환 확인 (`mock_prescription_table_tilt_blur.jpg`로 테스트, confidence 0.6388)
- PR #8 생성 및 dev 머지 완료
- **알려진 한계**: CLOVA가 다중 행 표에서 텍스트 순서를 가끔 뒤섞어 줘서 frequency가 잘못 매칭될 수 있음 (bounding box 재구성 필요, Day2+ 이슈)

## 8. 진행중 / 대기

- **Day5 BackgroundTask**: 김영혜님 `rag_router.py` 실제 연동 대기 중
- 박소정님 `records_router.py` 아직 미공유 상태, `main.py` 미등록 확인됨 (2026-07-07 기준)

---

## 9. Day5 완료 (2026-07-07)

### 수정 내역

1. **`BARE_FREQ_RE` 추가** (`parsing_rules.py`)
   - `1일` 접두사 없이 단독으로 오는 `N회` 패턴 파싱 지원
   - `extract_frequency` KOR_FREQ_RE → ABBREV_FREQ_RE → BARE_FREQ_RE 순 폴백
   - 오탐 방지: 뒤에 한글(`투약량`·`복용` 등) 또는 `)` 오면 매칭 제외 → `용량(1회)`, `1회 투약량` 헤더 안전

2. **`_parse_official_format` 횟수 검색 범위 확장** (`parsing_rules.py`)
   - 기존: `post` (약품명 이후 텍스트만 검색)
   - 변경: `seg_clean` (세그먼트 전체, ■ 이전)
   - 효과: CLOVA가 `[코드] 0.5mg 1회 3일 ... 덱사메타손정` 처럼 횟수를 약품명 앞에 출력하는 경우도 포착

3. **OcrResult `drug_code` 하드코딩 제거** (`ocr_interface.py`, `routers/ocr_router.py`)
   - `drug_code=""` 고정값 → `med.drug_code` (파싱된 실제 코드)로 변경

### mock_seoul_clinic_prescription.png 재테스트 결과

- confidence: 0.9684 / status: completed / review_required: false

| 약품명 | dosage | frequency | 이전 결과 | 비고 |
|--------|--------|-----------|-----------|------|
| 아목시실린 | 500mg | **1일 3회** ✅ | 1일 3회 | 유지 |
| 이부프로펜 | 400mg | **""** | "" | CLOVA가 해당 행 횟수 미출력 — 파싱 차원 해결 불가 |
| 오메프라졸 | 20mg | **1일 2회** ✅ | "" (버그) | BARE_FREQ_RE로 수정 |
| 덱사메타손 | 0.5mg | **1일 1회** ✅ | "" (버그) | seg_clean 확장으로 수정 |

---

## 6. 미해결 이슈 (Day2 이후)

| 우선순위 | 이슈 | 근거 샘플 |
|----------|------|-----------|
| 높음 | 약봉투 테이블형 — bounding box 기반 행 그룹핑 구현 | mock_pharmacy_bag_format.png |
| 높음 | 한방 첩약 파서 구현 (형태소 없는 자연어 처방) | mock_oriental_medicine.png |
| 중간 | 영문 약품명 지원 — `DRUG_NAME_RE`에 `[A-Za-z]{3,}` 추가 | mock_english_mixed.png |
| 중간 | 피부과 제형 추가 — `크림\|로션\|연고\|겔\|패취` | mock_dermatology.png |
| 중간 | 점안액 용량 패턴 — `\d+(?:\.\d+)?%` 추가 | mock_ophthalmology.png |
| 중간 | ATC 패턴 단어 경계(`\b`) — 2자 단편명 오분류 방지 | mock_dental_bag.png |
| 중간 | 비표준 frequency 표기("7 회") KOR_FREQ_RE 보강 | prescription_01.jpg |
| 낮음 | ~~정신건강의학과 브랜드명 미등록~~ → HIRA 연동으로 해결 | — |
| 낮음 | ~~DRUG_CLASS_DICTIONARY 확장~~ → drug_reference.py로 대체 완료 | — |
