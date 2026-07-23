# 트러블슈팅 — 권순현

## 1. EasyOCR 한글 인식 안 됨

**원인**
EasyOCR은 Reader 초기화 시 선언한 언어 코드에 해당하는 모델만 로드한다. `["en"]`만 선언하면 한국어 모델 자체를 불러오지 않아 한글 텍스트를 인식하지 못한다.

**증상**
한글이 포함된 처방전 이미지를 OCR에 넣었을 때 한글 부분이 전부 빈 결과로 반환됨

**해결**
```python
reader = easyocr.Reader(["en", "ko"])
```

---

## 2. PIL 한글 폰트 렌더링 실패

**원인**
PIL(Pillow)의 기본 폰트(`ImageFont.load_default()`)는 ASCII 문자만 지원한다. 한글을 렌더링하려면 시스템에 설치된 한글 폰트 파일 경로를 직접 지정해야 한다.

**증상**
한글이 포함된 샘플 이미지를 PIL로 생성했을 때 한글 부분이 깨지거나 빈 박스로 출력됨

**해결**
```python
KOREAN_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"  # macOS 기준
font = ImageFont.truetype(KOREAN_FONT, size=24)
```

---

## 3. OCR 오인식 (한글 받침·숫자 혼동)

**원인**
EasyOCR이 시각적으로 유사한 문자를 혼동하는 경우가 있다. 의약품 도메인에서는 한글 받침 혼동("캡슐" → "캡쑬")이나 숫자·문자 혼동(`0` → `O`)이 처방 용량이나 약품명 오인식으로 직결되기 때문에 raw 결과를 그대로 사용하면 안 된다.

**증상**
"캡슐500mg" → "캡쑬50Omg" 처럼 약품명과 용량이 동시에 오인식됨

**해결**
2단계 후처리 파이프라인으로 교정

```python
# 1단계: 자주 혼동되는 패턴을 사전에 정의해 일괄 치환
CHAR_CORRECTIONS = {"캡쑬": "캡슐", "캡술": "캡슐"}

# 2단계: 의약품 도메인 사전과 유사도 비교 후 가장 가까운 단어로 교정
def correct_with_domain_dict(text, domain_dict, threshold=0.8):
    matches = difflib.get_close_matches(text, domain_dict, n=1, cutoff=threshold)
    return matches[0] if matches else text
```

---

## 4. 브랜치명에 슬래시 포함 시 PyCharm 오류

**원인**
`feature/ocr-day1-setup_soonhyun`은 Git 브랜치명이지 파일시스템 경로가 아니다. PyCharm의 이름 변경(Rename) 다이얼로그는 파일·디렉터리 이름을 변경하는 UI이기 때문에, 슬래시(`/`)가 포함된 이름을 입력하면 유효하지 않은 식별자로 판단하고 오류를 낸다.

**증상**
PyCharm 이름 변경 다이얼로그에 브랜치명 입력 시 "올바른 식별자가 아닙니다" 오류 발생

**해결**
브랜치 생성과 push는 파일 탐색기가 아니라 터미널 Git 명령어로 처리한다.
```bash
git checkout -b feature/ocr-day1-setup_soonhyun
git push -u origin feature/ocr-day1-setup_soonhyun
```

---

## 5. drug_matcher.py — 용량 오매칭 버그

**원인**
`match_drug()` 내부의 정규화(`_normalize`) 로직이 용량 표기를 제거하고 성분명만 남긴다. 서로 다른 용량의 약품(메트포르민정 250mg / 500mg / 1000mg)이 모두 "메트포르민정"으로 축약되는데, `dict[str, str]`로 관리하다 보니 먼저 등록된 값이 나중 값을 덮어써 나머지 후보가 소실된다.

```python
# 문제가 된 코드
norm_to_raw: dict[str, str] = {}
for raw, norm in zip(raw_pool, norm_pool):
    if norm in close_norm and norm not in norm_to_raw:
        norm_to_raw[norm] = raw  # 250mg가 먼저 등록되면 500mg, 1000mg는 무시됨
```

score가 1.0으로 반환되기 때문에 "정확히 일치"로 오판되어 잘못된 결과가 신뢰도 높은 결과로 그대로 통과한다는 점이 더 위험하다.

**증상**
OCR이 "메트포르민정500mg"을 정확히 읽어도 사전에 250mg이 먼저 등록되어 있으면 `("메트포르민정250mg", score=1.0)`을 반환함

**영향 범위**
- 24개 목업 테스트: 정규화 충돌 8그룹이 전부 외용제라 현재 목업에서는 미발생
- HIRA 약가마스터(30만 건) 적용 시: 같은 성분 다른 용량이 대량 존재하므로 실제 발생 가능

**해결 (PR #57)**
```python
norm_to_raws: dict[str, list[str]] = {}
for raw, norm in zip(raw_pool, norm_pool):
    if norm in close_norm:
        norm_to_raws.setdefault(norm, []).append(raw)  # 모든 후보 보존
```
신규 테스트 15건 추가, "메트포르민정500mg 입력 시 정확히 500mg 선택" 케이스 포함

---

## 6. docker-compose.yml — 환경변수 주입 설정 누락

**원인**
`docker-compose.yml`의 `backend` 서비스에 `env_file`이나 `environment` 지시자가 없었다. 코드가 `load_dotenv()`로 `.env`를 직접 읽는 방식에만 의존하고 있어서 Compose 레벨에서는 이 파일의 존재를 알지 못했다. `docker compose restart`는 기존 컨테이너 프로세스를 그대로 재시작할 뿐이라, `.env` 파일을 수정해도 컨테이너 시작 시점에 이미 로드된 값이 유지된다.

**증상**
`backend/.env`의 `DATABASE_URL`을 수정하고 `docker compose restart`를 실행했는데, 로그에 여전히 이전 값(`APP_ENV=local`, SQLite)이 출력됨

**해결**
```bash
docker compose down
docker compose up -d
```

**검증**
```bash
docker compose logs backend --tail=30 | grep "\[db\]"
# [db] APP_ENV=development host=aiven-db-url... 로 변경된 것 확인
```

**개선 여지**
```yaml
services:
  backend:
    env_file:
      - backend/.env
```
`restart`만으로는 반영되지 않을 수 있어 환경변수 변경 시 `down` → `up` 습관화가 더 안전하다.
