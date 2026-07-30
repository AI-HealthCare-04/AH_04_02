"""
처방전 raw_text 파싱 규칙

네 가지 처방전 포맷을 커버한다:
  1. 공식 포맷    : [급여/비급여][코드] 약품명 1회량 1일횟수 일수
  2. 테이블 포맷  : OCR이 약품명·용량·횟수·일수를 컬럼 그룹으로 출력
  3. 리스트 포맷  : 번호. 약품명 1회 N정, 1일 N회, N일분
  4. 약식(약어) 포맷: Dx: / Rx) / bid / qd / #N

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[진단 기록] 정규식 한계 — 약봉투 테이블 포맷 (2026-07-03 확인)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
mock_pharmacy_bag_format.png 같이 "약품명/성분 | 복약안내 | 투약량 | 횟수 | 일수"
컬럼이 순수 숫자(1 2 30)로만 구성된 약봉투 테이블 포맷은 정규식으로 해결 불가.

근거:
  1) DRUG_NAME_RE 오인식: 성분명(메트포르민염산염, 암로디핀베실산염)이
     제형 패턴(-산)에 걸려 브랜드명과 구분되지 않음 → 5개 매칭, 실제 약품 3개
  2) KOR_FREQ_RE 미검출: 복약안내가 "아침 식후 복용하세요" 형태이면
     "1일 N회" 표현이 없어 횟수 추출 불가
  3) 숫자 컬럼 행 소속 불명: CLOVA가 테이블을 flat string으로 병합하면
     "1 2 30 / 1 1 30 / 1 1 30"이 어느 약품 행인지 위치 정보가 소실됨

해결 방법 (Day2 이후 구현):
  CLOVA OCR 응답의 fields[].boundingPoly.vertices (x, y 좌표)를 활용해
  텍스트 필드를 y좌표 기준으로 행(row)으로 그룹핑한 뒤 컬럼 헤더 x범위로
  투약량·횟수·일수를 각 약품에 1:1 매핑하는 표 구조 파싱 레이어 필요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import csv
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 1. 약어 → 한국어 매핑
# ─────────────────────────────────────────────────────────────

FREQ_ABBREV_MAP: dict = {
    "qd":  "1회",
    "od":  "1회",
    "bid": "2회",
    "tid": "3회",
    "qid": "4회",
    "prn": "필요시",
    "hs":  "취침 전",
    "ac":  "식전",
    "pc":  "식후",
}

# ─────────────────────────────────────────────────────────────
# 2. 약효 분류 사전 (TODO: Day2 이후 실샘플 기반으로 계속 보강)
# ─────────────────────────────────────────────────────────────

DRUG_CLASS_DICTIONARY: dict = {
    "아스피린":   "항혈소판제",
    "로자탄":     "ARB(안지오텐신수용체차단제)",
    "메트포르민": "당뇨병용제(비구아니드)",
    "암로디핀":   "칼슘채널차단제",
    "심바스타틴": "HMG-CoA환원효소억제제(스타틴)",
    "오메프라졸": "양성자펌프억제제(PPI)",
    "세레브렉스": "COX-2선택적억제제(NSAIDs)",
    "졸피뎀":     "수면유도제(비벤조디아제핀계)",
    "파모티딘":   "H2수용체차단제",
}

# ─────────────────────────────────────────────────────────────
# 3. 정규식 상수
# ─────────────────────────────────────────────────────────────

DRUG_NAME_RE = re.compile(
    # (?<![가-힣\d]): 한글·숫자 바로 뒤 부분 매칭 방지 (예: '이지엔6프로연질캡슐'에서 '프로'만 잡히는 것 차단)
    # (?:\d+(?!연질)[가-힣A-Za-z]{2,})?: 숫자 삽입 복합 약품명 처리 (예: '이지엔6프로')
    #   — '연질' 앞 lookahead로 '오메가3연질캡슐'에서 3이 연질을 삼키는 것을 방지
    # [2026-07-27 버그수정] 정제/캡슐 위주로만 목록이 자라 있어 패치("패취"만 인식되고
    # 훨씬 흔한 표기인 "패치"는 누락)/점안액·점이액(안약/귀약)/환(알약)이 처방전에 있으면
    # 이 매칭 자체가 실패해 그 약이 통째로 인식 결과에서 사라졌다 — drug_matcher._DOSAGE_RE가
    # 이미 커버하던 제형 목록과 맞춰 추가한다.
    # [2026-07-27 추가] 나잘스프레이 등 "스프레이"(비강분무제) 제형도 같은 이유로 누락돼
    # 있었다.
    # [2026-07-27 추가] 팀에서 정리한 제형군 표(내용고형제/내용액제/주사제/외용액제/
    # 반고형제/좌제/질제/흡입제/패취제/구강붕해제/필름제/트로키/껌제) 기준으로 아직
    # 누락된 제형을 마저 추가한다 — 과립/세립(고형제), 엘릭서/드링크(액제),
    # 앰플/바이알/시린지(주사제), 페이스트(반고형제), 좌제/좌약, 필름, 트로키/로젠지, 껌.
    r"(?<![가-힣\d])([가-힣A-Za-z]{2,}(?:\d+(?!연질)[가-힣A-Za-z]{2,})?(?:\d+)?(?:연질)?"
    r"(?:정|캡슐|주|산|시럽|액|크림|연고|로션|겔|패취|패치|점안|점이|환|스프레이"
    r"|과립|세립|엘릭서|드링크|앰플|바이알|시린지|페이스트|좌제|좌약|필름|트로키|로젠지|껌)(?![가-힣])"
    # [2026-07-28 추가] "글루코파지XR"/"디아미크롱MR"처럼 한글 브랜드명 뒤에 영문 방출제어
    # 접미사(서방정 계열 SR/XR/ER/CR/MR/IR/LA/CD/SA)만 붙고 정/캡슐 같은 한글 제형어가
    # 따로 없는 이름은 위 첫 갈래로 못 잡혔다 — 접미사가 항상 대문자로 표기되는 관례를
    # 이용해 별도 갈래로 추가한다(소문자 오검출 방지를 위해 (?-i:...)로 이 갈래만 대소문자
    # 구분). CLOVA가 이 이름을 두 개의 bounding box로 쪼개 인식해도(예: "글루코파지" /
    # "XR"), ocr_interface.py의 _merge_split_name_fields()가 먼저 공백 없이 붙여주므로
    # 이 갈래가 온전한 한 단어로 매칭할 수 있다.
    # [2026-07-30 버그수정] 이 갈래가 "부분 문자열"까지 잡아버려서 "처방전OCR"/"기반OCR"/
    # "샘플은OCR" 같은, 실제 처방전과 무관한 안내문구·헤더·푸터 텍스트가 전부 약품명으로
    # 오인식됐다 — "OCR"의 마지막 두 글자 "CR"이 서방정 접미사로 걸리면서 그 앞 아무
    # 글자나 다 약품명 취급된 것(실사용 재현: 10개 국가서식 샘플 전부에서 "샘플은OCR"이
    # 나옴). 실제 서방정 접미사는 한글 브랜드명 바로 뒤에 오지, "O"처럼 또 다른 대문자
    # 뒤에 오지 않는다 — 접미사 직전이 대문자면 그건 "OCR"처럼 하나의 영문 약어이지
    # 브랜드명+접미사 조합이 아니라고 보고 매칭에서 제외한다.
    r"|[가-힣A-Za-z]{2,}?(?<!(?-i:[A-Z]))(?-i:SR|XR|ER|CR|MR|IR|LA|CD|SA)(?:정|캡슐)?"
    r"|(?-i:[A-Z][a-zA-Z]{4,})(?=\s+\d))"  # 영문 PascalCase 5자+, 바로 뒤에 숫자(용량/횟수) 필수
    # [2026-07-18] "정 5mg"처럼 띄어쓴 용량도 이름에 붙게 허용
    # [2026-07-19] "50/1000mg"같은 복합제 용량(성분 두 개를 슬래시로 묶고 단위는 한 번만
    # 표기)도 통째로 붙게 허용.
    # [2026-07-29] "228mg/5ml"처럼 슬래시 뒤에도 단위가 붙는 시럽 농도 표기도 통째로
    # 약품명에 남긴다.
    r"\s?(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?(?:mg|g|ml|%)"
    r"(?:\s*/\s*\d*(?:\.\d+)?(?:mg|g|ml|%))?)?"
    r"(?:\([^)]+\))?",
    re.IGNORECASE,
)

# [2026-07-19] "50/1000mg"(복합제, 예: 글리메피리드/메트포르민)처럼 슬래시로 묶인 두 성분
# 용량도 하나로 인식 — 뒷 숫자에 붙은 단위 하나만 mg/g/ml/%로 보고, 앞 숫자는 그대로 살린다.
DOSAGE_RE       = re.compile(r"(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*(mg|g|ml|%)", re.IGNORECASE)

# [2026-07-23 추가] "1회 복용량"(환자가 한 번에 몇 개/단위를 먹는지 — 예: "1정", "0.5정",
# "2캡슐")은 DOSAGE_RE가 잡는 mg/g/ml/%(주성분 함량, 약품명에 붙어 나옴)와 다른 정보다.
# 실제 처방전엔 보통 (1) "1회 1정"처럼 텍스트로 풀어 쓰거나, (2) "1T"/"1C" 같은 약식
# 표기로 나오거나, (3) 공식 표 포맷에서 단위 없이 "1.00"처럼 숫자만 있는 컬럼으로 나온다.
# [2026-07-27 버그수정, PR #99 코드 리뷰 반영 — pecs0310] "개"/"매"는 "1개월분"/"1매월"처럼
# 공급 기간(개월) 표기에도 나타난다 — "1개월분"의 "1개"를 복용량으로 오인식해서
# ("인슐린프리필드시린지 1개월분" → dosage="1개") 어르신에게 틀린 1회 복용량 정보가
# 노출되는 실제 버그가 재현됐다. 부정형 lookahead로 "월"이 바로 뒤따르는 경우만 제외한다.
DOSE_QTY_UNITS = "정|캡슐|캅셀|포|병|환|스틱|앰플|바이알|시린지|개(?!월)|매(?!월)"
DOSE_QTY_UNIT_RE   = re.compile(rf"(\d+(?:\.\d+)?)\s*({DOSE_QTY_UNITS})")
DOSE_QTY_ABBREV_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)\s*(T|C)\b")  # 1T(정)/1C(캡슐) 약식 표기
# [2026-07-27 추가] 시럽/점안액처럼 개수(정/캡슐 등)가 아니라 부피·방울 수로 1회
# 복용량을 표현하는 제형 — 이 단위들은 약품명의 제형 접미사로 나올 일이 없으므로
# DOSE_QTY_UNITS(DRUG_FORM_RE와 공유)와는 분리해서 관리한다. 이게 없으면 "1방울"의
# "1"이 단위 없는 숫자로 오인되어 (3) 폴백에서 약품명 제형("액" 등)이 엉뚱하게 붙어
# "1액" 같은 말이 안 되는 값이 만들어졌다.
# [2026-07-27 추가] 산제/과립제(g), 인슐린(단위/Unit), 스프레이·흡입제(분사/퍼프)도
# 같은 이유로 추가한다.
DOSE_QTY_VOLUME_UNITS = "ml|mL|방울|분무|분사|퍼프|g|단위"
DOSE_QTY_VOLUME_UNIT_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({DOSE_QTY_VOLUME_UNITS})", re.IGNORECASE)
# [2026-07-27 추가] 스프레이는 "1회 2분무"처럼 숫자가 분무/분사에 바로 붙기도 하지만,
# "양쪽 비공 1회씩 분사"/"1회 분무"처럼 숫자가 "회"(한 번 뿌릴 때)에 붙고 분무/분사가
# 뒤에 따로 오는 표기도 흔하다 — 이때는 그 "N회"의 N을 분무 횟수로 본다.
SPRAY_COUNT_RE = re.compile(r"(\d+)\s*회\s*씩?\s*(분무|분사)")
# 약품명(DRUG_NAME_RE group 1)이 실제로 끝나는 제형 — (3) 케이스에서 단위 없는 숫자 컬럼에
# 이 제형을 붙여 "1.00" + "정" → "1정"을 완성한다.
DRUG_FORM_RE = re.compile(
    rf"({DOSE_QTY_UNITS}|주|산|시럽|액|크림|연고|로션|겔|패취|패치|점안|점이|스프레이"
    r"|과립|세립|엘릭서|드링크|페이스트|좌제|좌약|필름|트로키|로젠지|껌)$"
)
# 단위 없는 순수 숫자 컬럼용 — 날짜/시각(-,:,.) 및 mg류/일/회/분/시/초/개월 단위에 이미
# 붙은 숫자는 제외한다(그런 숫자는 함량·횟수·일수·공급기간이지 복용량이 아니다).
# [2026-07-27 버그수정, PR #99 코드 리뷰 반영 — pecs0310] "개월"이 빠져 있어서 "1개월분"의
# "1"이 여기서도 바로 걸려, DOSE_QTY_UNITS의 "개"를 제외했는데도 약품명 제형이 그대로
# 붙는(예: "1시린지") 다른 형태로 여전히 복용량으로 오인식됐다.
_BARE_QTY_RE = re.compile(
    r"(?<![./\d:-])(\d+(?:\.\d+)?)(?!\s*(?:mg|g|ml|%|일|회|분|시|초|개월)|[./\d:-])"
)
KOR_FREQ_RE     = re.compile(r"(?:1\s*일|하루)\s*(\d+)\s*(?:회|번)")  # 1 일 3 회 같은 비표준 공백 허용
BARE_FREQ_RE    = re.compile(r"(?<!\d)(\d+)\s*회(?!\s*[가-힣\)])")
ABBREV_FREQ_RE  = re.compile(r"\b(qd|od|bid|tid|qid|prn|hs|ac|pc)\b", re.IGNORECASE)
# [2026-07-27 추가] "필요시"(PRN, 정해진 횟수·기간 없이 필요할 때만 복용)는 hs/ac/pc처럼
# "횟수"가 아니라 "조건"이라 extract_frequency/extract_days가 원래는 빈 값으로 걸러냈는데,
# 이 값 자체를 1일 투약횟수/총 투약일수 화면에 그대로 보여달라는 요청 — 영문 약어("prn")뿐
# 아니라 처방전에 바로 적히는 한글 표기("필요시")도 인식한다.
PRN_RE          = re.compile(r"필요\s*시|\bprn\b", re.IGNORECASE)
DAYS_KOR_RE     = re.compile(r"(\d+)\s*일\s*분")
DAYS_ABBREV_RE  = re.compile(r"#\s*(\d+)")
MAX_PRESCRIPTION_DAYS = 365
# [2026-07-20 버그수정] CLOVA가 표(연락처/발행일/처방 내역 등)를 개행 없이 한 줄로 합쳐
# 내보내면, 원래 있던 정지 조건(숫자+".)"+공백, "[\n■", 문자열 끝)이 전혀 안 걸려서
# "진단: 제2형 당뇨병" 뒤의 연락처·처방 목록·주의문구까지 전부 diagnosis로 삼켜버렸다
# (실제 재현: 300자 넘는 문자열이 ocr_results.diagnosis VARCHAR(255)를 초과해 저장 자체가
# 실패함). 실제 처방전에 진단명 바로 뒤에 자주 오는 필드 라벨(연락처/발행일/처방/조제)도
# 정지 조건에 추가했다 — 그래도 못 거른 경우를 대비해 extract_diagnosis()에서 길이도 자른다.
DIAGNOSIS_KOR_RE  = re.compile(
    r"진단(?:명)?\s*[:：]\s*([^\[\n■]+?)"
    r"(?=\s+\d+[.)]\s+|[\[\n■]|\s*(?:연락처|발행일|처방|조제)|\Z)"
)
_MAX_DIAGNOSIS_LEN = 100  # ocr_results.diagnosis VARCHAR(255)보다 여유 있게 짧게 — 실제 진단명은 이보다 훨씬 짧다
DRUG_CODE_RE      = re.compile(r"\[(?:급여|비급여)\]\[(\w+)\]")
DIAGNOSIS_EN_RE   = re.compile(r"Dx\s*[:：]\s*(.+?)(?=\s+Rx\b|\Z)", re.IGNORECASE)
DIAGNOSIS_CODE_RE = re.compile(r"질병분류기호\s*[:：]\s*\S+\s*[（(]([^)）]+)[)）]")
# [2026-07-29 추가] 실제 처방전/OCR 샘플은 "질병분류기호 I10, E11.9 처방구분"처럼
# 괄호 안 한글 진단명이 없이 KCD/ICD 코드만 적히는 경우가 있다. 기존 정규식은
# "I10 (고혈압)" 형태만 처리해서 diagnosis가 빈 값으로 저장됐고, 그 결과 진단명 기준
# 생활습관 RAG가 이어지지 않았다. 코드만 있어도 주요 만성질환은 한글 진단명으로 매핑한다.
DIAGNOSIS_CODE_LIST_RE = re.compile(
    r"질병분류기호\s*[:：]?\s*([A-Z]\d{2}(?:\.\d+)?(?:\s*,\s*[A-Z]\d{2}(?:\.\d+)?)*)",
    re.IGNORECASE,
)
DIAGNOSIS_CODE_MAP: dict[str, str] = {
    "E11": "당뇨병",
    "E55.9": "비타민D 결핍",
    "E78.5": "이상지질혈증",
    "G43.9": "편두통",
    "H10.1": "알레르기 결막염",
    "I10": "고혈압",
    "I20.9": "협심증",
    "I25.1": "허혈성 심장질환",
    "J02.9": "급성 인두염",
    "J30.9": "알레르기 비염",
    "J45.9": "천식",
    "K21.0": "위식도역류질환",
    "K29.7": "위염",
    "L30.9": "피부염",
    "M54.5": "요통",
    "M81.0": "골다공증",
    "N18.3": "만성 신장병",
    "R11": "오심 및 구토",
    "R50.9": "발열",
}
# [2026-07-23 추가] 같은 처방인지 판단할 근거로 "처방번호"는 6개 mock 포맷 중 1개에만
# 등장해 신뢰도가 낮다(별도로 팀원이 조사 중) — 대신 "조제일자/처방일자/진료일자/조제일"은
# 6개 포맷 전부에 있고 "YYYY-MM-DD"/"YYYY.MM.DD" 두 형식만 확인됐다.
PRESCRIPTION_DATE_RE = re.compile(
    r"(?:조제일자|처방일자|진료일자|조제일)\s*[:：]?\s*(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})"
)

# ── 한방 첩약 포맷 전용 ──────────────────────────────────────────
# "당귀 8g", "천궁(川芎) 4g" 형태: 한글 약재명(2~6자) + 선택 한자괄호 + 중량g
_HERB_ITEM_RE    = re.compile(r"([가-힣]{2,6})(?:\([^\)]*\))?\s+(\d+(?:\.\d+)?)g\b", re.IGNORECASE)
_HERB_DETECT_RE  = re.compile(r"[가-힣]{2,6}(?:\([^\)]*\))?\s+\d+(?:\.\d+)?g\b", re.IGNORECASE)
_ORIENTAL_FREQ_RE = re.compile(r"(?:1일|하루)\s*(\d+)\s*(?:첩|회|번)")
_ORIENTAL_DAYS_RE = re.compile(r"(\d+)\s*첩")

# ─────────────────────────────────────────────────────────────
# 4. 유틸리티 함수 (공개 API)
# ─────────────────────────────────────────────────────────────

def extract_dosage(text: str) -> str:
    m = DOSAGE_RE.search(text)
    if not m:
        return ""
    # "50 / 1000mg"처럼 슬래시 앞뒤에 공백이 있어도 "50/1000mg"로 통일해서 저장한다.
    return f"{m.group(1).replace(' ', '')}{m.group(2)}"


def extract_dose_quantity(text: str, form: str = "") -> str:
    """1회 복용량 — "1정", "0.5정", "2캡슐"처럼 환자가 한 번에 먹는 개수/단위.

    1) "1회 1정"/"1정"처럼 텍스트에 단위가 그대로 있으면 그걸 쓴다.
    2) "10ml"/"1방울"처럼 부피·방울 단위(시럽/점안액 등)가 있으면 그걸 쓴다.
    3) "1회씩 분사"/"1회 분무"처럼 숫자가 분무/분사가 아니라 "회"에 붙어 나오는
       스프레이 표기를 본다.
    4) "1T"/"1C" 같은 약식 표기(T=정, C=캡슐)를 본다.
    5) 그래도 없으면 단위 없이 숫자만 있는 컬럼(예: "1.00")을 찾아, 약품명의 제형(form,
       예: "정"/"캡슐")을 붙여 완성한다 — form이 없으면 조합할 수 없어 빈 문자열을 반환한다.
    """
    m = DOSE_QTY_UNIT_RE.search(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = DOSE_QTY_VOLUME_UNIT_RE.search(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = SPRAY_COUNT_RE.search(text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = DOSE_QTY_ABBREV_RE.search(text)
    if m:
        unit = "정" if m.group(2).upper() == "T" else "캡슐"
        return f"{m.group(1)}{unit}"
    if form:
        m = _BARE_QTY_RE.search(text)
        if m:
            qty = m.group(1)
            if "." in qty and float(qty) == int(float(qty)):
                qty = str(int(float(qty)))  # "1.00" → "1" (소수부가 전부 0이면 정수로)
            return f"{qty}{form}"
    return ""


def _dm_dosage(dm: "re.Match") -> str:
    """DRUG_NAME_RE 매치의 트레일링 용량 그룹(group 2)을 "50/1000mg"처럼 공백 없이 반환.
    그룹이 없으면(용량이 이름에 안 붙어 나온 경우) 빈 문자열."""
    if not dm.group(2):
        return ""
    return dm.group(2).replace(" ", "")


# [2026-07-25 추가] "1회 투여량"(mg/ml 등 질량·부피 단위) — "1회 사용량"(정/캡슐 등
# 개수 단위)과 별개 필드. 처방전 문구에 따로 적혀 있으면(예: "1회 10mg 경구 투여") 그걸
# 쓰고, 없으면 약품명에 붙어 나오는 단위당 함량(예: "암로핀정5밀리그람"의 5mg)을 그대로
# 쓴다 — 대부분의 정제 처방전은 후자뿐이라, 이 폴백이 없으면 이 필드가 거의 항상
# 비어 있게 된다.
def extract_dose_amount(post_text: str, dm_dosage: str = "") -> str:
    return extract_dosage(post_text) or dm_dosage


def _strip_dose_column_labels(text: str) -> str:
    """수량/일수 후보를 찾기 전에 컬럼 라벨의 '1회' 숫자를 제거한다."""
    return re.sub(r"1\s*회\s*(?:투여량|투약량|사용량|복용량)", " ", text)


def _match_inside_spans(match: "re.Match", spans: list[tuple[int, int]]) -> bool:
    return any(start <= match.start() < end for start, end in spans)


# [2026-07-25 추가] 1회 사용량(dosage)과 1회 투여량(dose_amount)의 인식 결과를 조합한다.
# reconcile_dose_fields 자체는 "사용량이 비었을 때 채우는" 역할만 한다 — dose_amount는
# 이미 파싱 단계에서 결정된 값을 그대로 받는다.
#
#   사용량 O                    → 그대로 둔다(투여량 유무 무관, 이미 충분).
#   사용량 X, 투여량 O          → 약품명에 포함된 단위당 함량으로 나눠서 개수를 역산한다.
#                                  단위가 다르거나(mg vs ml), 복합제(성분 2개)거나, 약품명에서
#                                  함량을 못 찾으면 억지로 지어내지 않고 빈 문자열로 남긴다.
#   사용량 X, 투여량 X          → 빈 문자열(호출부가 review_required로 잡아냄).
def reconcile_dose_fields(dosage: str, dose_amount: str, drug_name: str) -> str:
    if dosage or not dose_amount:
        return dosage

    amount_m = DOSAGE_RE.fullmatch(dose_amount.strip())
    strength_m = DOSAGE_RE.search(drug_name)
    if not amount_m or not strength_m:
        return ""
    # drug_name은 "약품명(제형으로 끝) + ' ' + 함량(mg 등)" 구조라(_dm_dosage 조합 규칙),
    # 제형은 함량이 시작되기 직전 부분에서 찾아야 한다 — 함량이 붙으면 제형이 더 이상
    # 문자열 끝(DRUG_FORM_RE의 $ 앵커)이 아니게 되기 때문.
    form_m = DRUG_FORM_RE.search(drug_name[:strength_m.start()].rstrip())
    if not form_m:
        return ""
    # 복합제(예: "50/1000mg", 성분 2개)는 단순 나눗셈으로 개수를 정할 수 없다.
    if "/" in amount_m.group(1) or "/" in strength_m.group(1):
        return ""
    if amount_m.group(2).lower() != strength_m.group(2).lower():
        return ""  # mg vs ml처럼 단위가 다르면 나눌 수 없음

    try:
        strength_value = float(strength_m.group(1))
        if strength_value == 0:
            return ""
        qty = float(amount_m.group(1)) / strength_value
    except ValueError:
        return ""

    qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}".rstrip("0").rstrip(".")
    return f"{qty_str}{form_m.group(1)}"


def extract_frequency(text: str) -> str:
    """한국어 횟수 우선, 없으면 약어, 없으면 식사타이밍, 없으면 단독 N회 패턴.

    [2026-07-18] "1일" 접두어는 뺀다 — 프론트 라벨이 "1일 투약횟수"라 값에서
    또 반복하면 "1일 1일 1회"처럼 겹쳐 보인다. 값은 "1회"/"2회"만 담는다.

    [2026-07-18] 식전/식후(MEAL_RE) 폴백은 제거했다 — "1일 투약횟수"는 하루에 몇 번
    먹는지(횟수)를 묻는 필드인데, 식전/식후는 언제 먹는지(타이밍)라 전혀 다른 정보다.
    명시적인 횟수를 못 찾았으면 "식후"를 억지로 끼워맞추지 말고 빈 값으로 남겨서
    사용자가 직접 채우게 한다(모르는 걸 아는 척 지어내지 않음).

    [2026-07-27 추가] "필요시"(PRN)는 위와 같은 이유(횟수가 아니라 조건)로 원래는
    hs/ac/pc와 함께 걸러졌는데, 이 값 자체를 화면에 그대로 보여달라는 요청이 있어
    hs/ac/pc와 분리해 예외로 반환한다 — 영문 약어("prn")와 한글 표기("필요시") 둘 다.
    """
    m = KOR_FREQ_RE.search(text)
    if m:
        return f"{m.group(1)}회"
    if PRN_RE.search(text):
        return "필요시"
    m = ABBREV_FREQ_RE.search(text)
    if m:
        mapped = FREQ_ABBREV_MAP.get(m.group(1).lower(), m.group(1))
        # hs/ac/pc는 횟수가 아니라 타이밍이라("취침 전"/"식전"/"식후") 여기서도 걸러낸다
        # — 진짜 횟수(qd/od/bid/tid/qid)만 반환.
        if mapped.endswith("회"):
            return mapped
        return ""
    m = BARE_FREQ_RE.search(text)
    if m:
        return f"{m.group(1)}회"
    return ""


def extract_drug_code_list(text: str) -> list:
    """공식 처방전의 [급여/비급여][코드] 패턴을 순서대로 추출해 리스트로 반환."""
    return DRUG_CODE_RE.findall(text)


def _format_total_days(value: str) -> str:
    """투약일수 후보를 표시값으로 변환한다. 비현실적인 OCR 숫자열은 버린다."""
    try:
        days = int(value)
    except ValueError:
        return ""
    if 1 <= days <= MAX_PRESCRIPTION_DAYS:
        return f"{days}일"
    return ""


def extract_days(text: str) -> str:
    """[2026-07-27 추가] 명시적인 일수("30일분"/"#30")를 못 찾았는데 "필요시"(PRN)가
    있으면 정해진 기간이 없다는 뜻이므로, 빈 값 대신 그 자체를 총 투약일수로 보여준다."""
    m = DAYS_KOR_RE.search(text)
    if m:
        return _format_total_days(m.group(1))
    m = DAYS_ABBREV_RE.search(text)
    if m:
        return _format_total_days(m.group(1))
    if PRN_RE.search(text):
        return "필요시"
    return ""


def extract_diagnosis(text: str) -> str:
    if matches := DIAGNOSIS_KOR_RE.findall(text):
        parts = [m.strip().rstrip(",/ ") for m in matches if m.strip()]
        seen: set = set()
        deduped = [p for p in parts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        result = ", ".join(deduped)
    elif m := DIAGNOSIS_EN_RE.search(text):
        result = m.group(1).strip()
    elif m := DIAGNOSIS_CODE_RE.search(text):
        result = m.group(1).strip()
    elif m := DIAGNOSIS_CODE_LIST_RE.search(text):
        codes = [code.strip().upper() for code in m.group(1).split(",") if code.strip()]
        parts = [_diagnosis_name_from_code(code) for code in codes]
        seen: set = set()
        deduped = [p for p in parts if p and not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        result = ", ".join(deduped)
    else:
        result = ""
    # [2026-07-20] 정지 조건을 다 못 거른 텍스트가 와도(예: 예상 못 한 OCR 포맷) DB
    # 컬럼(ocr_results.diagnosis VARCHAR(255)) 저장 자체가 실패하지 않도록 방어적으로 자른다.
    return result[:_MAX_DIAGNOSIS_LEN]


def _diagnosis_name_from_code(code: str) -> str:
    """KCD/ICD 코드 → 앱에서 생활습관 RAG 조회에 쓰는 한글 진단명."""
    if code in DIAGNOSIS_CODE_MAP:
        return DIAGNOSIS_CODE_MAP[code]
    if "." in code:
        base = code.split(".", 1)[0]
        if base in DIAGNOSIS_CODE_MAP:
            return DIAGNOSIS_CODE_MAP[base]
    return ""


def extract_prescription_date(text: str) -> str:
    """조제일자/처방일자/진료일자/조제일 → "YYYY-MM-DD". 못 찾으면 빈 문자열
    (날짜를 모르면 그냥 모르는 대로 두고, 이름만으로 비교하던 기존 중복판정 방식으로 폴백한다)."""
    m = PRESCRIPTION_DATE_RE.search(text)
    if not m:
        return ""
    year, month, day = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def lookup_drug_class(drug_name: str) -> str:
    for key, cls in DRUG_CLASS_DICTIONARY.items():
        if key in drug_name:
            return cls
    return ""


# ── 한방 첩약 보조 함수 ──────────────────────────────────────────

_herb_name_set: set | None = None


def _load_herb_names() -> set[str]:
    """herb_reference.csv의 herb_name 컬럼을 set으로 지연 로드."""
    global _herb_name_set
    if _herb_name_set is not None:
        return _herb_name_set
    try:
        csv_path = Path(__file__).parent.parent / "herb_reference.csv"
        names: set[str] = set()
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("herb_name", "").strip()
                if name:
                    names.add(name)
        _herb_name_set = names
    except Exception:
        _herb_name_set = set()
    return _herb_name_set


def _is_oriental_format(text: str) -> bool:
    """'약재명 Ng' 패턴이 2개 이상이면 한방 첩약 처방전으로 판정."""
    return len(_HERB_DETECT_RE.findall(text)) >= 2


def _extract_oriental_frequency(text: str) -> str:
    m = _ORIENTAL_FREQ_RE.search(text)
    if m:
        unit = "첩" if "첩" in m.group(0) else "회"
        return f"{m.group(1)}{unit}"
    return extract_frequency(text)


def _extract_oriental_days(text: str) -> str:
    # frequency 패턴("1일 N첩/회")을 먼저 소비한 나머지에서 days를 탐색.
    # 이렇게 하지 않으면 "1일 2첩 … 20첩"에서 2첩이 days로 잘못 잡힌다.
    freq_m = _ORIENTAL_FREQ_RE.search(text)
    search_text = text[freq_m.end():] if freq_m else text
    m = _ORIENTAL_DAYS_RE.search(search_text)
    if m:
        return f"{m.group(1)}첩"
    return extract_days(text)


# ─────────────────────────────────────────────────────────────
# 5. 포맷 감지
# ─────────────────────────────────────────────────────────────

def _detect_format(text: str) -> str:
    """'oriental' | 'official' | 'abbrev' | 'list' | 'table' 반환."""
    if _is_oriental_format(text):
        return "oriental"
    if re.search(r"\[(?:급여|비급여)\]\[\w+\]", text):
        return "official"
    if re.search(r"\b(?:bid|qd|tid|qid)\b", text, re.IGNORECASE):
        return "abbrev"
    # [2026-07-27 버그수정] DRUG_NAME_RE가 이미 커버하는 제형 목록보다 좁아서, 크림/연고/
    # 로션/겔/패치류 처방전이 리스트 포맷인데도 (더 약한 파싱을 쓰는) table로 빠졌다 —
    # DRUG_NAME_RE와 동일한 제형 목록으로 맞춘다.
    if re.search(
        r"\d+[.)]\s+[가-힣A-Za-z]+(?:\d+)?(?:연질)?"
        r"(?:정|캡슐|시럽|액|주|산|크림|연고|로션|겔|패취|패치|점안|점이|환|스프레이"
        r"|과립|세립|엘릭서|드링크|앰플|바이알|시린지|페이스트|좌제|좌약|필름|트로키|로젠지|껌)",
        text,
    ):
        return "list"
    return "table"


# ─────────────────────────────────────────────────────────────
# 5-b. 국가 표준 처방전 표 서식 — bbox 기반 전용 파서
# ─────────────────────────────────────────────────────────────
# [2026-07-30 추가] "No / 처방 의약품 명칭 / 1회 투약량 / 1일 횟수 / 총일수 / 용법·용량 /
# 조제시 참고" 표 헤더를 쓰는 국가 표준 처방전 서식은 위 4개 포맷(official/abbrev/list/
# oriental) 어디에도 안 걸려 가장 약한 "table" 폴백으로 떨어졌다. table 폴백은 raw_text로
# 평탄화한 뒤 "마지막 횟수 매치 이후 텍스트 전체"에서 숫자를 긁어와 총일수를 정하는데,
# 이 서식엔 정지 조건("진단명")이 없어 면허번호·전화번호까지 총일수로 잘못 뽑힌다
# (실사용 재현: 10개 국가서식 샘플 전부에서 총일수가 "123456일"(면허번호)/"031일"(전화
# 지역번호) 같은 값으로 나옴). 표 밖 헤더·환자정보·참고사항 텍스트가 약품명 정규식에
# 걸리는 오탐(예: "샘플은OCR", "장다정"(환자 이름))도 10개 전부에서 재현됐다.
#
# ocr_interface.py가 raw_text로 펼치기 전 가지고 있는 CLOVA fields(boundingPoly 포함)를
# 여기서 그대로 받아 표 구조를 복원한다 — 헤더 7개 라벨의 x좌표로 각 컬럼의 가로 범위를
# 구하고, "처방 의약품 명칭" 컬럼에서 DRUG_NAME_RE에 걸리는 필드만 행(row)의 기준으로
# 삼는다. 그 결과 표 밖 텍스트는 애초에 약품명 후보 자체가 될 수 없고(표의 "처방 의약품
# 명칭" 컬럼 x범위 밖이므로), 총일수도 그 약의 행 안에서 "총일수" 컬럼 x범위에 있는
# 필드만 가져오므로 다른 행·다른 컬럼의 숫자가 섞일 수 없다.
_TABLE_HEADER_COLUMNS: list[tuple[str, set[str]]] = [
    ("no", {"No"}),
    ("drug_name", {"처방", "의약품", "명칭"}),
    ("dosage", {"1회", "투약량"}),
    ("frequency", {"1일", "횟수"}),
    ("total_days", {"총일수"}),
    ("usage", {"용법·용량"}),
    ("note", {"조제시", "참고"}),
]


def _bbox_center_y(field: dict) -> float:
    verts = field.get("boundingPoly", {}).get("vertices", [])
    if not verts:
        return 0.0
    return sum(v.get("y", 0) for v in verts) / len(verts)


def _bbox_left_x(field: dict) -> float:
    """필드의 x축 왼쪽 끝(min x). [2026-07-30 버그수정] 처음엔 중심 x로 컬럼을
    판정했는데, "처방 의약품 명칭" 컬럼은 왼쪽 정렬이라 짧은 이름("칼디비타정")과 긴
    이름("포사맥스플러스디정70밀리그램/5600IU")의 중심 x가 서로 크게 달라져서 짧은
    이름이 그 왼쪽 "No" 컬럼 범위로 잘못 판정됐다(실사용 재현: sample_07에서 칼디비타정
    행 자체가 통째로 누락). 실측 결과 이 표의 모든 컬럼은 왼쪽 정렬이라(예: 세 약품명
    전부 left=171.0으로 동일) 왼쪽 끝이 텍스트 길이와 무관한 안정적인 기준이다."""
    verts = field.get("boundingPoly", {}).get("vertices", [])
    if not verts:
        return 0.0
    return min(v.get("x", 0) for v in verts)


def is_official_prescription_table(fields: list) -> bool:
    """이 표 헤더(No/처방 의약품 명칭/1회 투약량/1일 횟수/총일수)가 있는 국가 표준
    처방전 서식인지 판정한다."""
    texts = {f.get("inferText", "") for f in fields}
    return {"총일수", "투약량", "횟수", "명칭"}.issubset(texts)


def _locate_table_columns(fields: list) -> list[tuple[str, float, float]] | None:
    """헤더 행에서 각 컬럼의 (key, 왼쪽 경계, 오른쪽 경계)를 x좌표(왼쪽 끝) 중간점
    기준으로 구해 왼쪽부터 정렬해 반환한다. 헤더 라벨을 하나라도 못 찾으면 None
    (호출부가 raw_text 기반 파싱으로 폴백하게 한다)."""
    total_days_field = next((f for f in fields if f.get("inferText") == "총일수"), None)
    if total_days_field is None:
        return None
    header_y = _bbox_center_y(total_days_field)

    anchors: list[tuple[str, float]] = []
    for key, labels in _TABLE_HEADER_COLUMNS:
        matched = [
            f for f in fields
            if f.get("inferText") in labels and abs(_bbox_center_y(f) - header_y) <= 15
        ]
        if not matched:
            return None
        xs = [_bbox_left_x(f) for f in matched]
        anchors.append((key, (min(xs) + max(xs)) / 2))
    anchors.sort(key=lambda a: a[1])

    columns = []
    for i, (key, cx) in enumerate(anchors):
        left = -1.0 if i == 0 else (anchors[i - 1][1] + cx) / 2
        right = float("inf") if i == len(anchors) - 1 else (cx + anchors[i + 1][1]) / 2
        columns.append((key, left, right))
    return columns


def _column_range(columns: list[tuple[str, float, float]], key: str) -> tuple[float, float]:
    for k, left, right in columns:
        if k == key:
            return left, right
    return (-1.0, float("inf"))


# [2026-07-30 추가] 헤더 라벨 위치로 계산한 컬럼 경계는 근사치일 뿐이다 — "용법·용량"
# 헤더는 그 컬럼 안에서 오른쪽으로 치우쳐 표기돼 있어(넓은 라벨), 경계를 헤더 위치
# 중간점으로만 잡으면 그 컬럼의 실제 내용(예: "아침", "식후")이 "총일수" 컬럼 경계
# 안쪽으로 잘못 포함된다(실사용 재현: 총일수가 "30일아침"처럼 나옴). 컬럼 경계를 더
# 정교하게 구하는 대신, 각 숫자 컬럼에 실제로 들어갈 수 있는 값의 "모양"을 정의해서
# 그 모양에 맞는 필드만 취한다 — 경계에 걸치는 서술형 텍스트("아침", "동중 부위에")는
# 애초에 이 모양에 안 맞아 자동으로 걸러진다.
_DOSAGE_VALUE_RE = re.compile(
    r"^\d+(?:\.\d+)?\s*(?:정|캡슐|캅셀|포|병|환|스틱|앰플|바이알|시린지|개|매|mL|ml|g|단위|방울|분무|분사)$",
    re.IGNORECASE,
)
_FREQUENCY_VALUE_RE = re.compile(r"^(?:주\s*)?\d+\s*회$")
_TOTAL_DAYS_VALUE_RE = re.compile(r"^\d+(?:\.\d+)?\s*(?:일|주|개월|년)$")
_PRN_VALUE_RE = re.compile(r"^필요\s*시$")
_DOSAGE_LITERAL_VALUES = {"소량"}  # 후시딘연고처럼 숫자 없이 "소량"만 적히는 경우


def _first_matching_cell_value(
    fields: list, top: float, bottom: float, col_range: tuple[float, float],
    value_res: list, literals: frozenset = frozenset(),
) -> str:
    """y범위 [top, bottom)·x범위(col_range) 안에서, 정의된 값 모양(value_res/literals)에
    맞는 첫 필드의 텍스트를 반환한다. 컬럼 경계가 근사치라 다른 컬럼 텍스트가 섞여
    들어와도, 그 값이 기대하는 모양(숫자+단위 등)이 아니면 그냥 건너뛴다."""
    left, right = col_range
    matched = sorted(
        (f for f in fields if top <= _bbox_center_y(f) < bottom and left <= _bbox_left_x(f) < right),
        key=lambda f: _bbox_left_x(f),
    )
    for f in matched:
        text = f.get("inferText", "").strip()
        if text in literals or any(rx.match(text) for rx in value_res):
            return text
    return ""


def parse_official_table_by_bbox(fields: list) -> list[dict]:
    """국가 표준 처방전(No/처방 의약품 명칭/1회 투약량/1일 횟수/총일수 표) 전용 파서.

    헤더를 못 찾거나 표의 "처방 의약품 명칭" 컬럼에서 실제 약품명으로 보이는 행을
    하나도 못 찾으면 빈 리스트를 반환한다 — 호출부(parse_prescription)가 그 경우
    기존 raw_text 기반 파싱으로 폴백한다.
    """
    columns = _locate_table_columns(fields)
    if columns is None:
        return []

    header_y = _bbox_center_y(next(f for f in fields if f.get("inferText") == "총일수"))
    drug_name_range = _column_range(columns, "drug_name")

    # [2026-07-30 버그수정] "처방 의약품 명칭" 헤더 라벨(3어절, 넓음)은 그 컬럼 안에서
    # 가운데 정렬돼 있어 실제 데이터(왼쪽 정렬, 예: 모든 약품명이 x=171에서 시작)보다
    # 훨씬 오른쪽에 위치한다 — 이 헤더 위치로 계산한 컬럼 왼쪽 경계를 그대로 쓰면 실제
    # 약품명 데이터가 전부(짧은 이름뿐 아니라 긴 이름까지) 그 경계 밖으로 밀려나 행을
    # 하나도 못 찾는다(실사용 재현: 모든 국가서식 샘플에서 바로 위 raw_text 폴백으로
    # 떨어져 총일수가 다시 면허번호/전화번호로 깨짐). "No" 컬럼과 "1회 투약량" 컬럼은
    # 둘 다 좁은 숫자 전용 컬럼이라 헤더 위치가 데이터와 잘 맞으므로, 왼쪽 경계 대신
    # 오른쪽 경계("1회 투약량" 컬럼 시작 전)만으로 표 밖 텍스트를 걸러낸다 — 환자정보·
    # 의료기관정보(표보다 위, header_y 이전)는 아래 y 조건으로 이미 배제된다.
    row_anchors = sorted(
        (
            f for f in fields
            if _bbox_left_x(f) < drug_name_range[1]
            and _bbox_center_y(f) > header_y + 5
            and DRUG_NAME_RE.search(f.get("inferText", ""))
        ),
        key=lambda f: _bbox_center_y(f),
    )
    if not row_anchors:
        return []

    row_ys = [_bbox_center_y(f) for f in row_anchors]
    dosage_range = _column_range(columns, "dosage")
    frequency_range = _column_range(columns, "frequency")
    total_days_range = _column_range(columns, "total_days")

    # [2026-07-30 버그수정] 마지막 행의 아래쪽 경계를 무한대로 두면 "4. 의약품 조제 시
    # 참고사항"·서명란·푸터까지 전부 마지막 행의 칸으로 잡혀버린다(실제 재현: 마지막 약의
    # dosage/frequency/total_days에 "조제약사 서명:", "PHARMACY USE" 같은 문구가 통째로
    # 섞임) — 앞선 행 간격(없으면 헤더~첫 행 간격)의 절반만큼만 아래로 확장해 표 실제
    # 마지막 행 높이만큼만 본다.
    if len(row_ys) >= 2:
        half_gap = (row_ys[-1] - row_ys[-2]) / 2
    elif row_ys:
        half_gap = (row_ys[0] - header_y) / 2
    else:
        half_gap = 0.0

    results = []
    for i, anchor in enumerate(row_anchors):
        # [2026-07-30 버그수정] i==0일 때 top을 header_y와 같게 두면(비교가 <=라서) 헤더
        # 라벨 자신("1회"/"투약량" 등)이 첫 행의 칸으로 같이 잡혔다(실제 재현: 첫 행
        # dosage가 "1회1정투약량"으로 나옴) — 헤더 행 아래로 확실히 내려서 제외한다.
        top = header_y + 5 if i == 0 else (row_ys[i - 1] + row_ys[i]) / 2
        bottom = row_ys[i] + half_gap if i == len(row_anchors) - 1 else (row_ys[i] + row_ys[i + 1]) / 2

        dm = DRUG_NAME_RE.search(anchor.get("inferText", ""))
        if dm is None:
            # row_anchors 자체가 이 regex로 걸러 뽑은 필드들이라 이론상 항상 매치되지만,
            # 이 파일의 다른 파서들과 동일하게 방어적으로 처리한다(ty의 None 내로잉도 만족).
            continue
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")

        dosage = _first_matching_cell_value(
            fields, top, bottom, dosage_range, [_DOSAGE_VALUE_RE], _DOSAGE_LITERAL_VALUES
        )
        frequency = _first_matching_cell_value(
            fields, top, bottom, frequency_range, [_FREQUENCY_VALUE_RE, _PRN_VALUE_RE]
        )
        total_days = _first_matching_cell_value(
            fields, top, bottom, total_days_range, [_TOTAL_DAYS_VALUE_RE, _PRN_VALUE_RE]
        )

        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      dosage,
            "dose_amount": _dm_dosage(dm),
            "frequency":   frequency,
            "total_days":  total_days,
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


# ─────────────────────────────────────────────────────────────
# 6. 포맷별 파서
# ─────────────────────────────────────────────────────────────

def _split_by_number(text: str) -> list:
    """'1) ...\n2) ...' 또는 '1. ... 2. ...' 형식을 번호 기준으로 분리."""
    return [s.strip() for s in re.split(r"(?<![A-Za-z가-힣])\d+\s*[).](?!\d)", text) if s.strip()]


def _parse_official_format(text: str) -> list:
    """공식 처방전 포맷: [급여/비급여][코드] 약품명 1회량 1일횟수 일수"""
    segments = re.split(r"\[(?:급여|비급여)\]\[\w+\]", text)

    all_freqs = [f"{n}회" for n in KOR_FREQ_RE.findall(text)]
    all_codes = extract_drug_code_list(text)

    results = []
    drug_idx = 0
    for seg in segments:
        seg = seg.strip()
        dm = DRUG_NAME_RE.search(seg)
        if not dm:
            continue
        # [2026-07-18] 약품명에 제형(정/캡슐 등)과 용량을 그대로 남긴다 — "암로디핀"이
        # 아니라 "암로디핀정 5mg"까지가 그 약을 특정하는 실제 이름이라, e약은요·HIRA
        # 매칭에도 이쪽이 더 정확하다.
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")

        post_raw = seg[dm.end():]
        post = post_raw.split("■")[0]
        # [2026-07-23 수정] dosage는 이제 "1회 복용량"(예: "1정") — 약품명의 제형을
        # 이 약의 단위로 보고, post(약품명 뒤 텍스트, 여기 "1회 투약량" 컬럼 값이 있다)에서
        # 수량을 찾는다. mg 등 성분 함량(_dm_dosage/extract_dosage)은 더 이상 dosage로
        # 쓰지 않는다 — 그건 이미 drug_name에 그대로 남아있다.
        form_m = DRUG_FORM_RE.search(dm.group(1))
        dosage = extract_dose_quantity(post, form_m.group(1) if form_m else "")
        dose_amount = extract_dose_amount(post, _dm_dosage(dm))
        # 날짜(2026-07-09)·시각(10:00) 앞뒤 숫자를 col_nums에서 제외하기 위해
        # 기존 패턴에 '-' ':' 추가
        post_without_labels = _strip_dose_column_labels(post)
        col_nums = re.findall(
            r"(?<![./\d:-])(\d+)(?![./\d:-]|mg|g|ml|분|시|초)", post_without_labels
        )

        seg_clean = seg.split("■")[0]

        # [중단]/[중지] 약물은 복약 횟수 없음
        if re.search(r"\[중단\]|\[중지\]", seg):
            freq = ""
        else:
            freq = extract_frequency(seg_clean)
            if not freq:
                # ① col_nums[1] 우선 (1일 최대 6회 기준 — 초과 시 일수로 판단)
                # ② col_nums[1]이 일수로 추정되면 col_nums[0] 시도
                # ③ 숫자 컬럼 없거나 모두 범위 초과 시 all_freqs 폴백
                #    (CLOVA 컬럼 그룹 출력: 약품명 전체→횟수 전체 순으로 출력되는 경우)
                if len(col_nums) >= 2 and 0 < int(col_nums[1]) <= 6:
                    freq = f"{col_nums[1]}회"
                elif len(col_nums) >= 1 and 0 < int(col_nums[0]) <= 6:
                    freq = f"{col_nums[0]}회"
                elif drug_idx < len(all_freqs):
                    freq = all_freqs[drug_idx]

        days = extract_days(post_without_labels) or next(
            (formatted for n in col_nums[2:] if (formatted := _format_total_days(n))), ""
        )
        drug_code = all_codes[drug_idx] if drug_idx < len(all_codes) else ""

        results.append({
            "drug_name":   drug_name,
            "drug_code":   drug_code,
            "dosage":      dosage,
            "dose_amount": dose_amount,
            "frequency":   freq,
            "total_days":  days,
            "drug_class":  lookup_drug_class(drug_name),
        })
        drug_idx += 1
    return results


def _parse_abbrev_format(text: str) -> list:
    """약식(약어) 포맷: Rx) 1) 약품명 1T bid #14"""
    rx_m = re.search(r"Rx\s*[)]", text, re.IGNORECASE)
    body = text[rx_m.end():] if rx_m else text

    results = []
    for item in _split_by_number(body):
        dm = DRUG_NAME_RE.search(item)
        if not dm:
            continue
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        form_m = DRUG_FORM_RE.search(dm.group(1))
        post = item[dm.end():]
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      extract_dose_quantity(post, form_m.group(1) if form_m else ""),
            "dose_amount": extract_dose_amount(post, _dm_dosage(dm)),
            "frequency":   extract_frequency(item),
            "total_days":  extract_days(item),
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


def _parse_list_format(text: str) -> list:
    """리스트 포맷: 1. 약품명 1회 1정, 1일 1회, 30일분"""
    results = []
    for item in _split_by_number(text):
        dm = DRUG_NAME_RE.search(item)
        if not dm:
            continue
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        form_m = DRUG_FORM_RE.search(dm.group(1))
        post = item[dm.end():]
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      extract_dose_quantity(post, form_m.group(1) if form_m else ""),
            "dose_amount": extract_dose_amount(post, _dm_dosage(dm)),
            "frequency":   extract_frequency(item),
            "total_days":  extract_days(item),
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


def _parse_oriental_format(text: str) -> list:
    """한방 첩약 처방전: '약재명 Ng' 반복 패턴.

    herb_reference.csv 로드 후 herb_name 컬럼으로 검증.
    CSV에 없는 약재명도 포함하되 drug_class를 '한방 첩약(미확인)'으로 표시.
    """
    herb_names = _load_herb_names()
    freq = _extract_oriental_frequency(text)
    days = _extract_oriental_days(text)

    results = []
    for m in _HERB_ITEM_RE.finditer(text):
        name = m.group(1).strip()
        weight = m.group(2)
        in_ref = name in herb_names
        results.append({
            "drug_name":   name,
            "drug_code":   "",
            "dosage":      f"{weight}g",
            "dose_amount": "",
            "frequency":   freq,
            "total_days":  days,
            "drug_class":  "한방 첩약" if in_ref else "한방 첩약(미확인)",
        })
    return results


def _parse_table_format(text: str) -> list:
    """테이블 포맷: OCR이 컬럼을 그룹으로 출력."""
    drug_matches = list(DRUG_NAME_RE.finditer(text))
    if not drug_matches:
        return []

    # KOR_FREQ_RE("1일 N회")와 BARE_FREQ_RE(독립 "N회") 모두 수집, 중복 없이 위치 순 정렬.
    # KOR 매치 구간을 consumed로 표시해 BARE가 같은 숫자를 다시 소비하지 않도록 한다.
    kor_spans: list[tuple[int, int]] = []
    freq_entries: list[tuple[int, int, str]] = []  # (start, end, freq_str)
    for m in re.finditer(r"(?:1\s*일|하루)\s*(\d+)\s*(?:회|번)", text):
        freq_entries.append((m.start(), m.end(), f"{m.group(1)}회"))
        kor_spans.append((m.start(), m.end()))
    for m in BARE_FREQ_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in kor_spans):
            freq_entries.append((m.start(), m.end(), f"{m.group(1)}회"))
    freq_entries.sort()
    frequencies = [freq for _, _, freq in freq_entries]

    # 마지막 freq 매치 이후 텍스트에서만 일수를 탐색 (freq 숫자를 일수로 오인하지 않도록)
    last_freq_end = max((end for _, end, _ in freq_entries), default=0)
    tail = text[last_freq_end:]
    diag_m = re.search(r"진단명", tail)
    if diag_m:
        tail = tail[:diag_m.start()]
    tail = _strip_dose_column_labels(tail)
    day_nums = [
        n
        for n in re.findall(r"(?<![.\d])(\d+)(?![.\d]|mg|g|ml|일|분)", tail)
        if _format_total_days(n)
    ]

    # [2026-07-23 추가] "1회 복용량"(예: "1정", "1T") — 단위가 붙은 수량 표기만 위치 순으로
    # 모아 약품 순서에 매핑한다. 단위 없는 숫자 컬럼(공식 포맷의 "1.00" 같은)은 이 포맷에서는
    # 어느 약의 것인지 위치 정보가 약해 신뢰도가 낮으므로 시도하지 않는다.
    qty_entries: list[tuple[int, str]] = []
    for m in DOSE_QTY_UNIT_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{m.group(2)}"))
    for m in DOSE_QTY_ABBREV_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{'정' if m.group(2).upper() == 'T' else '캡슐'}"))
    # [2026-07-27 추가] 시럽/점안액처럼 부피·방울 단위로 복용량을 쓰는 제형도 다른 단위와
    # 동일하게 위치 순으로 모은다 — 이게 없으면 정/캡슐 처방과 섞인 테이블에서 시럽/점안액
    # 항목의 복용량만 항상 빈 값이 된다.
    for m in DOSE_QTY_VOLUME_UNIT_RE.finditer(text):
        qty_entries.append((m.start(), f"{m.group(1)}{m.group(2)}"))
    qty_entries.sort()
    dose_quantities = [qty for _, qty in qty_entries]

    drug_spans = [(dm.start(), dm.end()) for dm in drug_matches]
    dose_amount_entries = [
        (m.start(), f"{m.group(1).replace(' ', '')}{m.group(2)}")
        for m in DOSAGE_RE.finditer(text)
        if not _match_inside_spans(m, drug_spans)
    ]
    dose_amounts = [amount for _, amount in sorted(dose_amount_entries)]
    has_dose_amount_column = re.search(r"1\s*회\s*(?:투여량|투약량)", text) is not None

    results = []
    for i, dm in enumerate(drug_matches):
        drug_name = dm.group(1) + (f" {_dm_dosage(dm)}" if dm.group(2) else "")
        dose_amount = dose_amounts[i] if has_dose_amount_column and i < len(dose_amounts) else _dm_dosage(dm)
        dosage = dose_quantities[i] if i < len(dose_quantities) else ""
        if has_dose_amount_column:
            dosage = reconcile_dose_fields("", dose_amount, drug_name) or dosage
        results.append({
            "drug_name":   drug_name,
            "drug_code":   "",
            "dosage":      dosage,
            # [2026-07-25 추가] 테이블 포맷은 컬럼 그룹 출력이라 사용량처럼 위치 기반으로
            # 신뢰도 있게 "1회 투여량" 문구를 찾기 어렵다 — 약품명에 붙어 나오는 단위당
            # 함량(_dm_dosage)만 폴백으로 쓴다.
            "dose_amount": dose_amount,
            "frequency":   frequencies[i] if i < len(frequencies) else "",
            "total_days":  _format_total_days(day_nums[i]) if i < len(day_nums) else "",
            "drug_class":  lookup_drug_class(drug_name),
        })
    return results


# ─────────────────────────────────────────────────────────────
# 7. 공개 메인 API
# ─────────────────────────────────────────────────────────────

def parse_prescription(raw_text: str, fields: list | None = None) -> tuple:
    """raw_text → (약품 목록, 진단명)

    [2026-07-30 추가] fields(CLOVA boundingPoly 포함 원본, ocr_interface.py가 raw_text로
    평탄화하기 전 값)가 주어지고 국가 표준 처방전 표 서식이면, raw_text를 버리고 표
    구조를 그대로 이용해 파싱한다(5-b 참고) — 이 표 형식에서는 이쪽이 항상 더 정확하다.
    fields가 없거나(예: Tesseract 폴백) 이 서식이 아니거나 행을 하나도 못 찾으면 기존
    raw_text 기반 포맷 감지+정규식 파싱으로 폴백한다.
    """
    if fields and is_official_prescription_table(fields):
        meds = parse_official_table_by_bbox(fields)
        if meds:
            for m in meds:
                m["dosage"] = reconcile_dose_fields(m["dosage"], m.get("dose_amount", ""), m["drug_name"])
            return meds, extract_diagnosis(raw_text)

    fmt = _detect_format(raw_text)
    if fmt == "oriental":
        meds = _parse_oriental_format(raw_text)
    elif fmt == "official":
        meds = _parse_official_format(raw_text)
    elif fmt == "abbrev":
        meds = _parse_abbrev_format(raw_text)
    elif fmt == "list":
        meds = _parse_list_format(raw_text)
    else:
        meds = _parse_table_format(raw_text)
    for m in meds:
        m["dosage"] = reconcile_dose_fields(m["dosage"], m.get("dose_amount", ""), m["drug_name"])
    return meds, extract_diagnosis(raw_text)


def parse_line(line: str) -> dict:
    return {
        "dosage":    extract_dosage(line),
        "frequency": extract_frequency(line),
    }
