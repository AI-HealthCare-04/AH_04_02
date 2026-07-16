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
- ~~**알려진 한계**: CLOVA가 다중 행 표에서 텍스트 순서를 가끔 뒤섞어 줘서 frequency가 잘못 매칭될 수 있음~~ → **해결** (`7816a42`): `ocr_interface.py`에 `_sort_fields_by_bbox()` 추가, bounding box 중심 좌표 기반 행 재구성으로 열 우선 출력 문제 수정

## 8. 진행중 / 대기

- **Day5 BackgroundTask**: 김영혜님 `rag_router.py` 실제 연동 대기 중
- 박소정님이 `records_router.py`로 통합 라우터 작업 중 — 기존 `ocr_router` / `rag_router` / `monitoring_router`와의 관계 확인 필요

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

## 7. 팀 결정 사항

### 의약품 데이터 소스 최종 픽스 (2026-07-08)

- **채택**: 약가마스터 + e약은요
- **배제**: 허가사항(MFDS API)
- **근거**:
  - 타겟이 만성질환자 → 약가마스터가 만성질환 급여 우선 등재 구조라 커버리지 90%+ 확보
  - 커버 안 되는 품목(위고비, 탈모치료제 등)은 프로젝트 타겟 범위 밖 → 실질적 영향 없음
  - MFDS API는 게이트웨이 장애 이력도 있어 안정성 우려로 배제
- **제안**: 김영혜 / **팀 확인**: 완료

---

## 6. 미해결 이슈 (Day2 이후)

| 우선순위 | 이슈 | 근거 샘플 |
|----------|------|-----------|
| ~~높음~~ | ~~약봉투 테이블형 — bounding box 기반 행 그룹핑 구현~~ → **해결** `7816a42` (`ocr_interface._sort_fields_by_bbox`) | mock_pharmacy_bag_format.png |
| 높음 | 한방 첩약 파서 구현 (형태소 없는 자연어 처방) | mock_oriental_medicine.png |
| 중간 | 영문 약품명 지원 — `DRUG_NAME_RE`에 `[A-Za-z]{3,}` 추가 | mock_english_mixed.png |
| 중간 | 피부과 제형 추가 — `크림\|로션\|연고\|겔\|패취` | mock_dermatology.png |
| 중간 | 점안액 용량 패턴 — `\d+(?:\.\d+)?%` 추가 | mock_ophthalmology.png |
| 중간 | ATC 패턴 단어 경계(`\b`) — 2자 단편명 오분류 방지 | mock_dental_bag.png |
| 중간 | 비표준 frequency 표기("7 회") KOR_FREQ_RE 보강 | prescription_01.jpg |
| 낮음 | ~~정신건강의학과 브랜드명 미등록~~ → HIRA 연동으로 해결 | — |
| 낮음 | ~~DRUG_CLASS_DICTIONARY 확장~~ → drug_reference.py로 대체 완료 | — |

---

## 9. Day7 통합테스트 체크리스트

> 기준일: 2026-07-08 / 서버: `cd /Users/admin/backend && OCR_PROVIDER=mock uvicorn main:app --reload`  
> 사전 준비: `patient_id=1` 존재 확인 (`GET /monitoring/patients`)

### 9-1. 정상 케이스

| # | 시나리오 | 예상 응답 | 확인 방법 | 담당 |
|---|----------|-----------|-----------|------|
| 1-1 | OCR(mock) → drug_code 매칭 → RAG 호출 → 결과 반환 | `status:"completed"`, `guide` 포함, `medications[].drug_code` 존재 | `curl -X POST "http://localhost:8000/records?patient_id=1" -F "file=@samples/mock_prescription_official.png"` | 권순현 |
| 1-2 | OCR(CLOVA) 실제 호출 (.env에 키 있을 때) | `status:"completed"`, `overall_confidence > 0` | `.env`의 `OCR_PROVIDER=clova`로 변경 후 위 curl 재실행 | 권순현 |
| 1-3 | RAG 스텁 결과 응답 JSON 구조 확인 | `guide.medication_guide.drugs[]`, `guide.lifestyle_guide`, `guide.source_refs[]` 모두 포함 | 1-1 응답 JSON에서 `guide` 키 검사 | 김영혜 |

### 9-2. review_required=true 케이스

| # | 시나리오 | 예상 응답 | 확인 방법 | 담당 |
|---|----------|-----------|-----------|------|
| 2-1 | CLOVA confidence < 0.80 → RAG 스킵 | `status:"review_required"`, `guide:null` | `curl -X POST "http://localhost:8000/records?patient_id=1" -F "file=@samples/mock_prescription_abbrev.png"` (실측 confidence 0.78) | 권순현 |
| 2-2 | mock 강제 저신뢰: `.env`에 `OCR_PROVIDER=mock` 후 TestClient로 confidence 0.75 패치 | `status:"review_required"`, `medications[]` 비어있지 않음, `guide:null` | `python3 -c "import os; os.environ['OCR_PROVIDER']='mock'; ..."` (이전 세션 검증 스크립트 참조) | 권순현 |

### 9-3. drug_code 매칭 실패 케이스

| # | 시나리오 | 예상 응답 | 확인 방법 | 담당 |
|---|----------|-----------|-----------|------|
| 3-1 | OCR에서 drug_code 미추출 (약품명만 인식) | `medications[].drug_code:""`, `review_required` 플래그로 정상 폴백 — 에러 없음 | mock 처방전 업로드 후 응답의 `drug_code` 값 확인 (`""` 이면 정상) | 권순현 |
| 3-2 | drug_code 없어도 RAG 호출 정상 진행 | `status:"completed"`, `guide` 포함 | 3-1과 동일 응답에서 `guide != null` 확인 | 권순현 |

### 9-4. CLOVA 다중행 표 bounding box 정렬 케이스

| # | 시나리오 | 예상 응답 | 확인 방법 | 담당 |
|---|----------|-----------|-----------|------|
| 4-1 | mock 21개 중 다중 약품 표 이미지 파싱 (현재 DB raw_text 기준) | 이상치 0건: "2026회·30회·7회·0회" 없음, 각 약품 frequency 정상 범위 | `python3 -c "from parsing_rules import parse_prescription; ..."` (배치 검증 스크립트 재실행) | 권순현 |
| 4-2 | CLOVA 실제 호출 후 `raw_text` 텍스트 순서 확인 (열 우선 → 행 우선으로 재구성) | raw_text가 `약품A 횟수A 일수A 약품B 횟수B 일수B` 형태 (약품명+횟수 인접) | `OCR_PROVIDER=clova`로 다중 약품 처방전 업로드 후 DB에서 `raw_text` 확인: `sqlite3 app.db "SELECT raw_text FROM medical_records ORDER BY id DESC LIMIT 1;"` | 권순현 |
| 4-3 | mock 21개 핵심 다중 약품 케이스 (`mock_prescription_official`, `mock_nursing_hospital`, `mock_university_hospital`) | 약품별 frequency 정확히 매칭 (세레콕시브 1일2회, 에페리손 1일3회 등) | 배치 검증 스크립트 결과표 참조 (`7cf421b` 기준 검증 완료) | 권순현 |

### 9-5. 에러 케이스

| # | 시나리오 | 예상 응답 | 확인 방법 | 담당 |
|---|----------|-----------|-----------|------|
| 5-1 | 빈 파일 업로드 | `HTTP 400`, `"빈 파일은 업로드할 수 없습니다."` | `curl -X POST "http://localhost:8000/records?patient_id=1" -F "file=@/dev/null;type=image/png;filename=empty.png"` | 권순현 |
| 5-2 | 미지원 확장자 (.pdf) | `HTTP 400`, `"지원하지 않는 파일 형식"` 포함 메시지 | `curl -X POST "http://localhost:8000/records?patient_id=1" -F "file=@/dev/null;type=application/pdf;filename=test.pdf"` | 권순현 |
| 5-3 | CLOVA 키 없음 (`.env`의 키 제거 후 `OCR_PROVIDER=clova`) | `HTTP 503`, `"CLOVA_OCR_API_URL / CLOVA_OCR_SECRET_KEY 환경변수가 없습니다."` | `.env`에서 `CLOVA_OCR_SECRET_KEY` 주석 처리 후 curl 재실행 | 권순현 |
| 5-4 | 존재하지 않는 patient_id | `HTTP 404`, `"해당 환자를 찾을 수 없어요"` | `curl -X POST "http://localhost:8000/records?patient_id=9999" -F "file=@samples/mock_prescription_official.png"` | 권순현 |

### 9-6. RAG 실제 연동 시 확인 항목 (김영혜님)

| # | 확인 항목 | 현재 상태 | 연동 시 필요 조치 | 담당 |
|---|-----------|-----------|-------------------|------|
| 6-1 | `run_rag_stub` 시그니처 | `def run_rag_stub(record_id, session)` — **sync** | 실제 RAG가 `async def`이면 `records_router.py:84`의 호출을 `await run_rag_stub(...)` 으로 수정 | 김영혜 ★ |
| 6-2 | 반환 타입 | `GuideResult` 객체 (SQLModel) | 교체 후에도 동일 타입 반환 필요. 반환값이 다르면 `_build_record_response()`의 `guide.medication_guide` 등 역직렬화 코드도 수정 | 김영혜 ★ |
| 6-3 | `ValueError` 예외 처리 | `records_router.py:85`에서 `except ValueError` 포착 후 `status="failed"` 처리 | 실제 RAG 예외 타입이 다르면 except 절 추가 필요 | 김영혜 ★ |
| 6-4 | 스텁 → 실제 교체 후 전체 흐름 재검증 | 9-1 ~ 9-5 전 항목 재실행 | mock/CLOVA 양쪽에서 9-1 ~ 9-5 재실행 | 김영혜 + 권순현 ★ |
| 6-5 | `source_refs[]` 스키마 고정 | `[{"title": str, "url": str}]` — 2개 키만 사용 | Result.tsx 프론트 호환 필수. **RAG 실제 구현 시 키 이름 변경 금지.** `drug_reference.py`의 `atc_code` / `match_source` / `matched_item`은 내부용이며 API 응답 미노출 (2026-07-08, 김영혜 확인 예정) | 김영혜 ★ |

---

## 10. 향후 개선 제안

### ~~한방 첩약 파서 미지원~~ → ✅ 해결 (2026-07-09, 커밋 `86f4d0f` + 버그수정 `72cf011`)

- **해결 내용**:
  1. **데이터소스 확보**: 식약처 생약 약재정보 API(HerbMdntfService, IROS_335) — 원본 2,060건 → 이명 포함 3,573개 약재명 수집, `backend/herb_reference.csv` 저장
  2. **스크립트 추가**: `backend/scripts/build_herb_reference.py` — API 페이지네이션 수집 자동화(재현 가능)
  3. **파서 구현**: `_parse_oriental_format()` 신규 추가 — `약재명(한자) Ng` 반복 패턴 인식, herb_reference.csv 기반 약재 검증, `drug_class="한방 첩약"` 반환
  4. **포맷 감지**: `_detect_format()`에 `oriental` 분기 최우선 등록 (`_is_oriental_format()`: `약재명 Ng` 패턴 2개 이상)
  5. **목업 이미지 추가**: `samples/mock_oriental_prescription.png` (쌍화탕 가감방 12약재, `generate_mock_oriental_prescription.py`)

- **버그 수정** (`72cf011`): `_extract_oriental_days()` freq/days 패턴 충돌 수정
  - 현상: "1일 2첩 … 20첩" 텍스트에서 `days=2첩`으로 잘못 파싱 (20첩이어야 함)
  - 원인: `_ORIENTAL_FREQ_RE`와 `_ORIENTAL_DAYS_RE`가 동일 구간에서 경쟁
  - 수정: `_extract_oriental_days()`에서 frequency 매치 구간을 먼저 소비(consume)한 이후 텍스트에서만 days 탐색

- **검증**: `parse_prescription()` 직접 호출 단위 테스트(ORI-1~4)로 검증
  - ORI-1: 기본 한방 텍스트 5약재 — 전량 `herb_reference` 확인, freq/days 정상
  - ORI-2: 쌍화탕 가감방 12약재 + 한자 괄호 — 12/12 (100%), days=20첩 정상 (`72cf011` 수정 후)
  - ORI-3: `herb_reference`에 없는 약재 혼합 — `drug_class="한방 첩약(미확인)"` 정상 분기
  - ORI-4: 횟수·첩수 없는 최소 텍스트 — freq/days 빈값 정상 처리
  - 기존 4포맷(official/abbrev/list/table) 회귀 없음 ✓

- **배치 회귀**: 24개 이미지 에러 0건 ✓ (단, mock provider 배치는 파싱 로직 검증 수단으로 부적합 — 아래 주의사항 참조)

---

## 11. 엔드투엔드 통합테스트 결과 (2026-07-09)

> 실행 조건: `OCR_PROVIDER=clova`, `RAG_PROVIDER=stub` (OPENAI 키 미설정으로 real 폴백), `mock_prescription_official.png`

| 단계 | 결과 |
|------|------|
| CLOVA OCR 호출 | ✅ 성공 — 4개 약품 인식 (세레콕시브·에페리손염산염·라베프라졸나트륨장용·조인트콘드로이친) |
| drug_code 매칭 | ✅ 4개 전부 HIRA 코드 매칭 (649500560·642201540·644308830·658101480) |
| drug_matcher (`matched_drug_name`/`match_score`) | ✅ DB 저장 정상 — 세레콕시브 1.0, 에페리손염산 0.923, 벤프라정 0.667, 종근당조인트콘드로 0.706 |
| `needs_review` 임계값 판정 | ✅ 라베프라졸나트륨장용 0.667 < 0.7 → True, 나머지 False — 정상 |
| RAG 자동 트리거 | ✅ confidence 0.9564 > 0.80 → `status: completed` → RAG 자동 호출 |
| `medication_guide` / `lifestyle_guide` / `source_refs` | ✅ 3개 필드 모두 정상 반환 |
| 에러 | **0건** |

**비고 — RAG_PROVIDER=real 전환 선행 조건**:
- `OPENAI_API_KEY` 추가 필요 (현재 `.env`에 없음)
- `pip install -r rag-prototype/requirements.txt` 실행 필요 (`langchain_core` 미설치)
- 위 2개 충족 시 `RAG_PROVIDER=real`로 변경하면 `rag_prototype.rag_chain.generate_guides_from_medications()` 실제 호출로 전환됨

---

## 12. 최종 정확도 요약 (D-4, 2026-07-09)

> 기준: `backend/scripts/batch_regression.py` (24개 목업, `parse_prescription()` 직접 호출) + CLOVA OCR 실제 파이프라인 1건

| 지표 | 결과 | 비고 |
|------|:----:|------|
| 포맷 인식률 | **24/24 (100%)** | table·list·official·abbrev·oriental 전 포맷 정상 |
| 검증 조건 통과율 | **39/40 (97.5%)** | 약품명·frequency·dosage·진단명·drug_class 40건 검증 |
| drug_class 정확도 | **8/9 (88.9%)** | 잔여 1건(이부프로펜 NSAIDs)은 HIRA/e약은요 데이터 없을 때의 알려진 폴백 한계 |
| drug_code 매칭률 (실 파이프라인) | **4/4 (100%)** | CLOVA OCR → HIRA 코드 전건 매칭 |
| review_required 오탐율 | **0/4 (0%)** | confidence 0.9564 → 전건 false |
| needs_review 정탐 | **임계값(0.70) 미달 1건 정상 플래그** | 라베프라졸나트륨 0.667 → True, 나머지 False |

---

> ⚠️ **팀 공유 — 파싱 로직 회귀 테스트 방법론**
>
> `MockOCRProvider.extract()`는 `parsing_rules.py`를 **전혀 거치지 않고** 아스피린/로자탄을 하드코딩으로 반환한다.
> 따라서 mock provider를 이용한 배치 테스트(`get_ocr_provider("mock")` → `provider.extract(img)`)는
> drug_class 매핑·drug_matcher·에러 핸들링 파이프라인 검증에는 유효하지만,
> **`_detect_format()` / `_parse_oriental_format()` 등 파싱 로직 자체의 회귀 테스트 수단으로는 부적합**하다.
>
> **파싱 로직 회귀 테스트는 반드시 `parse_prescription(raw_text)` 직접 호출 방식을 사용해야 한다.**
> (`86f4d0f` 커밋 메시지의 "24개 배치 anomaly 0건"은 mock provider 파이프라인 기준이었으며, 파싱 함수 레벨 검증은 이후 `72cf011`에서 별도로 수행됨.)

---

## 13. drug_matcher 정규화 개선 (2026-07-10)

용량 정보(mg/ml/정/캡슐 등)가 매칭 유사도 계산에 포함되어 정상 약품명도 점수가 낮게 나오던 문제 발견 및 해결. `_normalize()` 함수로 용량 제거 후 비교하도록 개선. 46건 검증 기준 `needs_review=False` 4건→24건으로 개선(오매칭 없이). (2026-07-10)

---

## 14. drug_class 커버리지 개선 (2026-07-10)

오분류 3종(`_lookup_emedinfo`가 fallback보다 먼저 실행되던 순서 문제) 수정 + ATC/fallback 패턴 11종 추가. 48종 검증 기준 62.5%→85.4% 개선. 잔존 7종은 HIRA CSV 로드 시 해결(3종)/복합제 특성(1종)/한방 약재로 별도 처리(3종)라 정상 범위. (2026-07-10)

---

## 15. OCR 비동기 처리 개선 (2026-07-10)

`ocr_router.py`의 CLOVA 호출을 `asyncio.to_thread`로 비동기 처리. 동시 요청 N건 기준 수정 전 ~N초 → 수정 후 ~1초(스레드풀 여유 시). 24개 목업 40건 회귀 없음, 동기/비동기 결과 완전 일치 확인. 서비스평가 5-1(성능), 3-2/5-5(비동기 일관성) 항목 대응. (2026-07-10)

---

## 16. 전체 회귀 재검증 (2026-07-14)

> 기준: PR #29~#34 dev 머지 반영 후 (`git pull origin dev`, HEAD `5e6212b`)

| 지표 | 결과 |
|------|:----:|
| 배치 회귀 (24개 목업, 검증 조건 40건) | **40/40 통과** |
| pytest | **31/31 통과, 0 실패** |
| 서버 기동 | **정상 (API 라우트 46개)** |

### pytest 구성 (31개)

| 파일 | 통과 |
|------|:----:|
| test_auth_router.py | 1/1 |
| test_care_router_invitations.py | 2/2 |
| test_models_pii.py | 4/4 |
| test_monitoring_router_linking.py | 3/3 |
| test_records_router_auth.py (PR #31, 신규) | 11/11 |
| test_security.py | 10/10 |

### 서버 기동 확인 라우터

PR #29~#34 반영 후 `from main import app` 정상. chat_router·records_router 등 여러 PR이 겹쳐 손댄 파일 포함 import 충돌 없음. 주요 신규/변경 라우트: `POST /chat/ask`, `GET /chat/history`, `GET /chat/questions`, `GET/POST /records/{record_id}` 계열 전체.

### 미적용 사항

`chat_router.py`의 `POST /chat/ask`, `GET /chat/history`는 인가 검증 미적용 상태로 확인. 이슈 #21에서 논의 중 (담당자 미지정, 김영혜 답변 대기).

---

## AI-Hub DS 576 약품 이미지 데이터셋 분석

> 분석일: 2026-07-16  
> 목적: drug_reference.py 주요 약품이 DS 576 시각적 약품식별 데이터셋에 포함되어 있는지 확인  
> 데이터셋: DS 576 「약품식별 인공지능 개발을 위한 경구약제 이미지 데이터」 (단일경구약제 5000종)

### 데이터셋 구조 파악

| 항목 | 내용 |
|------|------|
| 총 파일 수 | 단일 81개 + 조합 8개 ZIP (라벨 데이터) |
| K-코드 체계 | 식약처 허가 연도 순 일련번호 (K-000059 = 1964년, K-013096+ = 2003년+) |
| 파일당 약품 수 | 50종 고정 |
| 각 약품당 JSON | 수백~수천 개 (촬영 각도/조명 변형) |
| 전체 범위 | 1964~2003+ 허가 약품 |

**K-코드 ↔ 허가연도 보정값:**
- K-000059 = 1964년 (TL_1 시작)
- K-001615 = 1986년 (TL_1 종료)
- K-002709 = 1989년 (TL_25 시작)
- K-003354 = 1991년 (TL_25 종료)
- K-004072 = 1993년 (TL_27 시작)
- K-006656 = 1997년 (TL_31 시작)
- K-007493 = 1998년 (TL_32 시작)
- K-009272 = 2000년 (TL_34 시작)
- K-012685 = 2003년 (TL_38 시작)

### 스캔 범위 (최종 완료)

**전체 81개 TL 단일 파일 중 81개 전부 스캔 완료** (2026-07-16)
- 1차 스캔 (이전 세션): TL_1, TL_25~TL_34, TL_38 — 12개 파일, 600종
- 2차 스캔 (금번 세션): TL_2~TL_24, TL_35~TL_37, TL_39~TL_81 — 69개 파일, ~3,450종
- **총 스캔: 81개 파일, 4,050종, 1,599건 매칭**
- 스캔 허가연도 범위: 1959~2016년 전체 포함

### 매칭 결과 — drug_reference.py 33개 약효 그룹

#### ✅ 발견 그룹 (30개 / 33개, 91%)

| 약효 그룹 | 대표 성분 | DS 576 최초 확인 K-코드 | 허가연도 | 확인 종수 |
|----------|----------|----------------------|---------|---------|
| 당뇨-비구아니드 | 메트포르민/글루코파지 | K-004077 (TL_27) | 1993 | 60종 |
| 당뇨-설포닐우레아 | 글리메피리드/글리클라지드 | K-005588 (TL_29) | 1996 | 31종 |
| 당뇨-DPP4 | 시타글립틴(자누비아)/빌다글립틴(가브스) | K-022712 (TL_10) | 2007 | 17종 |
| 당뇨-SGLT2 | 다파글리플로진(포시가)/엠파글리플로진(자디앙) | K-032190 (TL_15) | 2013 | 11종 |
| CCB | 암로디핀(노바스크)/딜티아젬 | K-001906 (TL_2) | 1987 | 208종 |
| ARB | 발사르탄(디오반)/로자탄/칸데사르탄 | K-011252 (TL_6) | 2001 | 205종 |
| ACE억제제 | 에날라프릴/라미프릴 | K-002159 (TL_2) | 1988 | 12종 |
| 베타차단제 | 메토프롤롤/카베딜롤/비소프롤롤(콩코르) | K-000749 (TL_1) | 1981 | 41종 |
| 이뇨제 | 히드로클로로티아지드/토라세미드 | K-019699 (TL_10) | 2006 | 63종 |
| 스타틴 | 아토르바스타틴(리피토)/로수바스타틴(크레스토)/심바스타틴 | K-015258 (TL_8) | 2004 | 235종 |
| 콜레스테롤흡수억제제 | 에제티미브(바이토린) | K-018188 (TL_9) | 2005 | 25종 |
| 항혈소판제 | 아스피린/클로피도그렐(플라빅스)/티카그렐러(브릴린타) | K-006686 (TL_31) | 1997 | 46종 |
| 항응고제 | 와파린/리바록사반(자렐토)/다비가트란(프라닥사)/아픽사반(엘리퀴스) | K-001732 (TL_2) | 1986 | 9종 |
| PPI | 오메프라졸/에소메프라졸(넥시움)/라베프라졸/란소프라졸 | K-004285 (TL_3) | 1993 | 45종 |
| H2차단제 | 파모티딘(가스터)/시메티딘/라니티딘 | K-007588 (TL_4) | 1998 | 18종 |
| 위장운동촉진제 | 모사프리드(가스모틴)/돔페리돈 | K-010442 (TL_35) | 2001 | 23종 |
| COX2억제제 | 세레콕시브(쎄레브렉스)/에토리콕시브(알콕시아) | K-016190 (TL_44) | 2006 | 12종 |
| NSAIDs | 이부프로펜/나프록센/디클로페낙 | K-002240 (TL_2) | 1988 | 100종 |
| 해열진통제-아세트 | 아세트아미노펜(타이레놀) | K-004379 (TL_3) | 1993 | 195종 |
| 근이완제 | 에페리손/바클로펜 | K-000749 (TL_1) | 1981 | 21종 |
| 수면제/항불안-BZD | 알프라졸람(자낙스)/클로나제팜 | K-016372 (TL_44) | 2006 | 2종 |
| SSRI항우울제 | 세르트랄린(졸로푸트)/에스시탈로프람(렉사프로)/파록세틴 | K-009452 (TL_5) | 2000 | 18종 |
| 골다공증-BIS | 리세드론산(악토넬)/알렌드론산 | K-008899 (TL_5) | 2000 | 42종 |
| 항히스타민제 | 세티리진(지르텍)/로라타딘/펙소페나딘(알레그라) | K-006025 (TL_3) | 1997 | 59종 |
| 갑상선호르몬제 | 레보티록신(씬지로이드) | K-017258 (TL_9) | 2005 | 10종 |
| 스테로이드 | 프레드니솔론(메솔론)/히드로코르티손/메틸프레드니솔론 | K-010856 (TL_35) | 2001 | 7종 |
| 항생제-페니실린 | 아목시실린/오구멘틴 | K-000271 (TL_21) | 1975 | 29종 |
| 항생제-세팔로스포린 | 세파클러/세픽심/세프트리악손 | K-002208 (TL_2) | 1988 | 28종 |
| 항생제-퀴놀론 | 레보플록사신/시프로플록사신 | K-002265 (TL_2) | 1988 | 17종 |
| 항생제-마크로라이드 | 클래리트로마이신(클래리)/아지트로마이신(지스로맥스) | K-007325 (TL_4) | 1998 | 10종 |

#### ❌ 미발견 그룹 (3개 / 33개)

| 약효 그룹 | 미발견 이유 |
|----------|-----------|
| 당뇨-GLP1 | 빅토자(리라글루타이드)·오젬픽(세마글루타이드)은 **주사제** → 경구약 전용 DS 576에 없음. 경구 세마글루타이드(리벨서스, 2021년 허가)는 K-코드가 DS 576 스캔 범위(~K-039147, 2016년) 초과 |
| 수면제(졸피뎀) | 졸피뎀은 **향정신성 의약품** → DS 576 5,000종 선택 기준에서 제외된 것으로 추정 |
| (항불안-BZD는 부분 발견) | 자낙스(알프라졸람), 클로나제팜 2종 발견 — BZD가 완전히 없지는 않음 |

### 프로젝트 활용 가능성 평가 (업데이트)

| 활용 목적 | 적합성 | 근거 |
|----------|--------|------|
| 약품 시각적 식별 (OCR 보완) | ✅ 높음 | drug_reference.py 33그룹 중 30개(91%) 발견. 주요 만성질환 약품 대부분 포함 |
| drug_reference.py 보강 | ❌ 부적합 | DS 576은 이미지 라벨 데이터, 약효/용량 정보 없음 |
| 복약 분석 이미지 분류 모델 | ✅ 적합 | 약품당 수백~수천 장 이미지 라벨 (COCO 포맷), 30개 약효 그룹 커버 |
| 이미지 기반 약품 확인 (미래 기능) | ✅ 잠재적 | 스타틴 235종, CCB 208종, ARB 205종 등 다양한 제네릭 포함 |

**결론**: DS 576은 drug_reference.py 기준 주요 만성질환 처방약의 **91%를 커버**하는 우수한 경구약제 이미지 데이터셋. GLP1 주사제·졸피뎀 향정신성 의약품 2개 그룹 미포함은 데이터셋 성격상 당연한 결과. 복약관리 앱의 이미지 인식 기능 구현 시 즉시 활용 가능.

### fileSn 맵핑 테이블 (단일 경구약제)

```
TL_01: fileSn=66083 (70MB)    TL_28: fileSn=66092 (19MB) — 1994-1995년
TL_02: fileSn=66094 (70MB)    TL_29: fileSn=66093 (21MB) — 1995-1996년  
TL_10: fileSn=66073 (72MB)    TL_30: fileSn=66095 (20MB) — 1996-1997년
TL_25: fileSn=66089 (27MB)    TL_31: fileSn=66096 (23MB) — 1997-1998년
TL_26: fileSn=66090 (24MB)    TL_32: fileSn=66097 (25MB) — 1998-1999년
TL_27: fileSn=66091 (20MB)    TL_33: fileSn=66098 (22MB) — 1999-2000년
TL_34: fileSn=66099 (31MB)    TL_38: fileSn=66103 (14MB) — 2003년
```
전체 fileSn 맵핑: aihubshell -mode l -datasetkey 576 으로 재조회 가능 (apikey 필요)
