
| 날짜 | 2026.07.01 |
|---|---|
| **작성자** | 권순현 |
| **이슈** | PyCharm 이름 변경 다이얼로그에 슬래시(`/`) 포함 브랜치명 입력 시 “올바른 식별자가 아닙니다” 오류 |
| **발생 위치** | PyCharm IDE Rename 다이얼로그 |
| **원인** | `feature/ocr-day1-setup_soonhyun`은 Git 브랜치명이지 파일시스템 경로가 아니다. PyCharm의 Rename 다이얼로그는 파일·디렉터리 이름을 변경하는 UI이기 때문에, 슬래시(`/`)가 포함된 이름을 유효하지 않은 식별자로 판단한다. |
| **해결** | 브랜치 생성과 push는 파일 탐색기가 아니라 터미널 Git 명령어로 처리한다. |
| **핵심 패턴** | PyCharm의 Rename 다이얼로그는 파일명용이다. Git 브랜치는 반드시 터미널에서 `git checkout -b <name>` + `git push -u origin <name>`으로 생성한다. |

```bash
git checkout -b feature/ocr-day1-setup_soonhyun
git push -u origin feature/ocr-day1-setup_soonhyun
```

---

| 날짜 | (2026.07.07 이전 — 정확한 날짜 미상) |
|---|---|
| **작성자** | 박소정 |
| **이슈** | `docker compose up -d --build` 실행 시 모든 환경변수가 빈 값으로 인식됨(`WARN[0000] The "DB_PORT" variable is not set. Defaulting to a blank string. no port specified: :<empty>`) |
| **발생 위치** | 환경변수 파일 위치가 `envs/.local.env`(프로젝트 루트의 기본 `.env`가 아님) |
| **원인** | Docker Compose는 기본적으로 프로젝트 루트의 `.env`만 자동으로 읽는다. `envs/.local.env` 자체엔 값이 정상적으로 채워져 있었지만, 그 경로를 compose가 알 방법이 없어 모든 환경변수가 빈 값으로 처리됐다. |
| **해결** | `docker compose --env-file envs/.local.env up -d --build`로 커스텀 경로를 명시하거나, `ln -s envs/.local.env .env` 심볼릭 링크로 상시 해결. |
| **핵심 패턴** | Docker Compose는 `--env-file` 플래그로 커스텀 경로의 env 파일을 지정할 수 있다 — 기본 `.env` 경로가 아니면 반드시 명시해야 한다. |

---

| 날짜 | (2026.07.07 이전 — 정확한 날짜 미상) |
|---|---|
| **작성자** | 박소정 |
| **이슈** | `fastapi` 컨테이너가 `Restarting` 상태를 반복(`sh: 1: uv: not found`) |
| **발생 위치** | `docker-compose.yml`의 fastapi 서비스 `command: sh -c "uv run uvicorn app.main:app ..."`, 멀티스테이지 Dockerfile(builder → runtime) |
| **원인** | `uv` 바이너리를 builder 스테이지에만 복사해뒀고, runtime 스테이지엔 없었다. `docker-compose.yml`의 `command:`가 Dockerfile의 `CMD`를 덮어써서 `uv run`으로 실행되는 구조인데, 정작 실행에 필요한 `uv`가 최종 런타임 이미지엔 없었던 것. |
| **해결** | runtime 스테이지에도 `uv` 바이너리를 복사: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` |
| **핵심 패턴** | `docker-compose.yml`의 `command:`가 Dockerfile의 `CMD`를 덮어쓰므로, compose 파일의 실행 방식에 맞춰 런타임 이미지를 구성해야 한다. |

---

| 날짜 | (2026.07.07 이전 — 정확한 날짜 미상) |
|---|---|
| **작성자** | 박소정 |
| **이슈** | `ai-worker` 컨테이너가 에러 로그 없이 계속 `Restarting` 상태를 반복 |
| **발생 위치** | `ai_worker/main.py`, `docker-compose.yml`의 `restart: always` |
| **원인** | `docker compose logs ai-worker`는 로그가 완전히 비어있었고, `docker compose run --rm ai-worker python -m ai_worker.main`으로 직접 실행해도 출력 없이 즉시 종료됐다. `ls -la ai_worker/`로 확인한 결과 `main.py`가 0 bytes(완전히 빈 파일)였다 — 빈 파일을 실행하면 아무 동작 없이 정상 종료(exit 0)되고, `restart: always` 정책 때문에 종료→재시작이 무한 반복된 것. |
| **해결** | 실제 로직 구현 전까지 임시 대기 루프(`asyncio.sleep`)로 채워 컨테이너가 죽지 않고 대기하도록 함 — 실제 OCR/RAG 추론 로직은 추후 구현 필요. |
| **핵심 패턴** | 컨테이너가 에러 없이 재시작만 반복하면, 코드 자체가 비어있거나 즉시 종료되는 경우일 수 있다 — `run --rm`으로 직접 실행해서 확인. |

---

| 날짜 | (2026.07.07 이전 — 정확한 날짜 미상) |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 모바일 기기에서 개발 서버 접속 불가 |
| **발생 위치** | Vite dev server |
| **원인** | `npm run dev` 기본 실행 시 localhost에만 바인딩된다. |
| **해결** | `npm run dev -- --host` |
| **핵심 패턴** | 같은 네트워크의 다른 기기(휴대폰 등)에서 개발 서버에 접속하려면 `--host` 플래그로 모든 인터페이스에 바인딩해야 한다. |

---

| 날짜 | 2026.07.07 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | React 컴포넌트 렌더링 시 `Invalid hook call` 에러, `useRef` null 에러 |
| **발생 위치** | React + Vite + TypeScript, `react-router-dom` |
| **원인** | `react-router-dom`이 설치는 되어 있었지만 `package.json`의 `dependencies`에 실제로 등록이 안 되어 있어 React 버전 충돌이 발생한 것으로 확인(같은 날 겪은 다른 셋업 이슈들과 함께 아래 "7/7 문제들" 표 참고 — 근본 원인은 `react-router-dom` 자체가 `package.json`에서 누락된 것). |
| **해결** | `npm install react-router-dom` 후 전체 재설치. |
| **핵심 패턴** | "설치돼 있다"(`node_modules`에 존재)와 "`package.json`에 등록돼 있다"는 다르다 — 수동으로 옮기거나 복사한 프로젝트는 `package.json`/`package-lock.json` 정합성을 별도로 확인해야 한다. |

---

| 날짜 | 2026.07.07 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 프로젝트 초기 셋업 중 하루에 겪은 문제 6건 — Vite 무한 재시작부터 PR 머지 충돌까지 |
| **발생 위치** | Vite 설정, `react-router-dom` 의존성, `App.tsx`, `pages/`·`components/` 폴더, git merge/PR 흐름 |
| **원인** | 아래 표 참고 — 하루 안에 서로 다른 원인의 문제 6건이 연달아 발생 |
| **해결** | 아래 표 참고 |

| 이슈 | 원인 | 해결 |
| --- | --- | --- |
| Vite 무한 재시작(livelock) | 프로젝트가 iCloud Drive 동기화 폴더 안에 있어서 `vite.config.ts` 타임스탬프가 계속 갱신됨 | 프로젝트를 `~/dev/`(비동기화 폴더)로 이동 |
| `node_modules/tapable` 손상, Vite 설정 로드 실패 | iCloud 이동 중 대용량 폴더 손상 | `node_modules`, `package-lock.json` 삭제 후 재설치 |
| "Invalid hook call" (react-router-dom) | `package.json`에 `react-router-dom` 자체가 누락 | `npm install react-router-dom` 후 전체 재설치 |
| 화면 위 정체불명 메뉴바, URL과 실제 화면 불일치 | `App.tsx`가 실제로는 Figma Make 프로토타입(state 기반)이었고 react-router 미사용 상태였음 | 라우터 기반 `App.tsx`로 교체 |
| "Failed to resolve import './pages/Landing'" | `pages/`, `components/` 폴더가 실제 프로젝트에 반영된 적이 없었음 | 전체 프론트 파일 일괄 재적용 |
| `git merge --abort`가 미커밋 작업까지 되돌림 | OCR 통합 파일들이 커밋 전 상태였는데 merge abort로 함께 소실 | 파일 재적용 후 즉시 커밋하는 방식으로 전환 |
| PR 머지 시 관련없는 `app/`, `docs/` 파일 대량 충돌 | PR 브랜치가 dev 기준이 아니라 개인 작업폴더(`AH_04_02_soonhyun/`) 기준이었음 | `git merge` 대신 실제 코드 파일을 텍스트로 받아 `backend/`에 직접 포팅 |

**핵심 패턴**: 프로젝트 초기 셋업 단계에서는 iCloud 등 자동 동기화 폴더, 수동으로 옮긴 프론트 파일, 개인 작업폴더 기준 브랜치처럼 "겉보기엔 문제 없어 보이는" 환경 설정이 한꺼번에 여러 문제를 일으킬 수 있다 — `git merge --abort`처럼 되돌리기 쉬운 명령도 미커밋 작업이 있으면 위험하므로, 재적용 후 즉시 커밋하는 습관이 중요하다.

---

| 날짜 | 2026.07.02 |
|---|---|
| **이슈** | 토글 버튼 클릭 후 검은 테두리(outline)가 사라지지 않고 잔류 |
| **발생 위치** | `Check.tsx` 자가진단 버튼, `Dashboard.tsx` 복약 상태 버튼, `Connect.tsx` 관계 유형 버튼 |
| **원인** | React 인라인 스타일에서 `border` 단축속성과 `borderColor` 개별속성을 **동시에 사용**하면, 상태 전환 시 React가 이전 `border` 값을 제거하면서 브라우저 기본 `outline`(2.85px)이 노출됨. 크롬 DevTools Computed 탭에서 `outline-style: none` 이지만 `outline-width: 2.85714px` 가 남아있는 것으로 확인. 추가로 콘솔에 `"Removing a style property during rerender (borderColor)"` 경고 발생 |
| **시도한 방법 (실패)** | ① `index.css`에 `button:focus { outline: none }` 추가 → 효과 없음 ② `button:focus-visible`, `button:active`, `!important` 추가 → 효과 없음 ③ `onMouseDown={(e) => e.preventDefault()}` 단독 적용 → 효과 없음 ④ `borderWidth/borderStyle/borderColor` 개별속성으로 분리 → 오히려 테두리 두꺼워짐 ⑤ Grammarly 확장프로그램 비활성화 → 효과 없음 ⑥ Chrome DevTools Computed 탭에서 `outline-style: none`이지만 `outline-width: 2.85714px` 잔류 확인 ⑦ Console 경고 `"Removing a style property during rerender (borderColor)"` 확인 → 원인 특정 |
| **해결** | `styles` 객체에서 버튼 스타일을 분리하고, JSX 렌더링 시 **`isActive` 조건으로 모든 border 속성을 인라인으로 직접 계산**하여 적용. spread(`...`) 병합 없이 하나의 style 객체로 완성해서 React rerender 시 속성 충돌 원천 차단 |
| **핵심 패턴** | `border` 단축속성과 개별속성(`borderColor` 등)을 같은 컴포넌트에서 섞지 말 것. 상태에 따라 스타일이 바뀌는 버튼은 반드시 JSX 인라인 계산 방식 사용 |

```tsx
// ❌ 잘못된 패턴 — border 단축속성 + borderColor 개별속성 혼용
const styles = {
  btn: { border: "1px solid #E0D3C4" },
  btnActive: { borderColor: "#C16A45" },  // 충돌 발생!
}

// ✅ 올바른 패턴 — isActive로 전체 속성을 한번에 계산
<button style={{
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: isActive ? "#C16A45" : "#E0D3C4",
  background: isActive ? "#C16A45" : "#F5F0EA",
  outline: "none",
}}>
```

---

| 날짜 | 2026.07.09 |
|---|---|
| **이슈** | `CHAT_PROVIDER=real`로 실제 처방전 업로드 후 챗봇에 질문하면 응답을 못 받음(소정님 리포트) |
| **발생 위치** | `frontend/src/api/chat.ts`(`askChat`), `frontend/src/api/monitoringClient.ts` |
| **원인** | `monitoringClient`는 모든 요청에 전역 10초 타임아웃(`timeout: 10000`)을 씀. `CHAT_PROVIDER=real`일 때 `/chat/ask`는 백엔드에서 동기적으로 실제 OpenAI 호출(`chat_router.py`의 `_generate_llm_answer`)을 기다리는데, 이 호출이 10초를 넘기면 axios가 먼저 포기하고 요청을 취소함. 백엔드는 그 뒤에도 계속 처리해서 결국 200을 반환하지만(어떤 이유로 LLM 호출이 실패해도 `try/except`로 감싸 preset 답변으로 폴백하도록 이미 안전하게 설계돼 있음), 프론트는 이미 타임아웃 처리를 해버려서 "죄송해요, 답변을 가져오지 못했어요" 에러 버블만 보임 — 사용자 입장에선 "챗봇이 응답을 못한다"로 보임. 부수적으로 `ChatAnswer` 타입이 `source`로 선언돼 있는데 백엔드 응답 키는 `answer_source`라 늘 `undefined`였음(출처 라벨 미표시, 이건 크래시나 무응답의 원인은 아님) |
| **시도한 방법** | 백엔드(`chat_router.py`)를 먼저 의심했으나, `TestClient`로 직접 호출해보니 `CHAT_PROVIDER=stub`(기본값) 기준으로는 200 + 정상 답변이 즉시 나옴 — 백엔드 자체 로직엔 문제 없음을 먼저 배제. `main.py`에 `chat_router` 등록 여부도 재확인(정상 등록됨) |
| **해결** | `askChat()` 호출에만 `{ timeout: 30000 }`을 개별 지정(다른 CRUD 호출들은 그대로 10초 유지 — LLM 호출만 특별히 느릴 수 있는 케이스라 전역으로 늘리지 않음). `ChatAnswer.source` → `answer_source`로 필드명을 백엔드와 일치시키고 `Chat.tsx`의 참조도 함께 수정 |
| **핵심 패턴** | 외부 LLM API를 동기 호출로 감싼 엔드포인트는 일반 CRUD보다 훨씬 느릴 수 있으므로, 공용 axios 클라이언트의 전역 타임아웃에 의존하지 말고 해당 호출에만 개별 타임아웃을 지정할 것. 백엔드가 "실패해도 200 폴백"으로 안전하게 설계돼 있어도, 프론트의 타임아웃이 그보다 짧으면 사용자에게는 똑같이 "응답 없음"으로 보임 |

```ts
// ❌ 전역 타임아웃만 믿는 패턴 — LLM 호출엔 너무 짧음
export async function askChat(patientId: number, questionId: string) {
  const { data } = await monitoringClient.post<ChatAnswer>("/chat/ask", {
    patient_id: patientId, question_id: questionId,
  }); // 전역 10초 타임아웃 그대로 적용
  return data;
}

// ✅ LLM 호출 엔드포인트만 개별 타임아웃 연장
export async function askChat(patientId: number, questionId: string) {
  const { data } = await monitoringClient.post<ChatAnswer>(
    "/chat/ask",
    { patient_id: patientId, question_id: questionId },
    { timeout: 30000 },
  );
  return data;
}
```

---

| 날짜 | 2026.07.09 |
|---|---|
| **이슈** | 복약 가이드 화면에는 약물 부작용·주의사항이 정상적으로 보이는데, 같은 약의 "약물상세"(`DrugInfo.tsx`) 화면에서는 복용 방법·주의사항이 "등록된 주의사항이 없어요"로 나옴(소정님 리포트) |
| **발생 위치** | `frontend/src/pages/DrugInfo.tsx` |
| **원인** | `RAG_PROVIDER=real`일 때 백엔드가 내려주는 실제 응답 모양은 `medication_guide`/`precautions`(배열) 필드를 쓰고, `dosage_text`/`caution`(stub 전용 필드)는 아예 안 내려줌(`rag_prototype/schemas.py`의 `GuideResponse`엔 `caution` 필드 자체가 없음). `MedGuide.tsx`/`Result.tsx`는 PR #16에서 이미 두 모양을 다 처리하도록 고쳤지만, `DrugInfo.tsx`는 그 작업 대상에서 빠져서 여전히 `guideDrug?.dosage_text`/`guideDrug?.caution`만 읽고 있었음 — 실제 모드에서는 항상 `undefined`라 "정보 없음"으로 표시됨. 즉 데이터는 이미 같은 `record.guide`에 들어있는데 화면이 잘못된 필드명을 읽고 있던 것 |
| **시도한 방법** | `/ocr/drug-info`(적응증 조회용 별도 엔드포인트)와 `drug_matcher.py`/`drug_reference.py`를 먼저 의심했으나, 이 엔드포인트는 처음부터 적응증(효능효과)만 담당하고 부작용/주의사항 필드는 조회하지 않도록 설계돼 있어 관련 없음을 확인. 실제 원인은 이미 응답에 있는 `record.guide.medication_guide.drugs[].precautions`를 화면이 안 읽는 것이었음 |
| **해결** | `DrugInfo.tsx`에 `MedGuide.tsx`/`Result.tsx`와 동일한 분기 로직 추가: `guideText = guideDrug?.medication_guide ?? guideDrug?.dosage_text`, `cautionText = guideDrug?.precautions?.length ? guideDrug.precautions.join(" ") : guideDrug?.caution` |
| **핵심 패턴** | stub/실제 두 응답 모양을 처리하는 방어 로직을 한 화면에만 추가하고 끝내지 말 것 — 같은 `GuideDrug`/`LifestyleGuide` 데이터를 읽는 화면이 여러 개(Result/MedGuide/DrugInfo)면 전부 같은 분기를 적용해야 함. 새 화면을 추가할 때마다 "이 필드, stub에만 있는 필드 아닌가?"를 `docs/rag-real-response-sample.md`로 확인하는 습관이 필요 |

---

| 날짜 | 2026.07.15 |
|---|---|
| **작성자** | 권순현 |
| **이슈** | `backend/.env`의 `DATABASE_URL`을 수정하고 `docker compose restart`를 실행했는데, 로그에 여전히 이전 값(`APP_ENV=local`, SQLite)이 출력됨 |
| **발생 위치** | `docker-compose.yml` backend 서비스 |
| **원인** | `docker-compose.yml`의 `backend` 서비스에 `env_file`이나 `environment` 지시자가 없었다. 코드가 `load_dotenv()`로 `.env`를 직접 읽는 방식에만 의존하고 있어서 Compose 레벨에서는 이 파일의 존재를 알지 못했다. `docker compose restart`는 기존 컨테이너 프로세스를 그대로 재시작할 뿐이라, `.env` 파일을 수정해도 컨테이너 시작 시점에 이미 로드된 값이 유지된다. |
| **해결** | `docker compose down` → `docker compose up -d` 로 컨테이너를 완전히 재생성한다. |
| **검증** | `docker compose logs backend --tail=30 \| grep “\[db\]”` 로 `APP_ENV=development`로 변경됐는지 확인 |
| **핵심 패턴** | 환경변수 변경 시 `restart`만으로는 반영되지 않는다. `down` → `up` 습관화 필요. 근본 해결은 `docker-compose.yml`에 `env_file: - backend/.env` 추가. |

---

| 날짜 | 2026.07.20 |
|---|---|
| **작성자** | 권순현 |
| **이슈** | OCR이 “메트포르민정500mg”을 정확히 읽어도 `drug_matcher`가 `(“메트포르민정250mg”, score=1.0)`을 반환함 |
| **발생 위치** | `backend/services/drug_matcher.py` — `match_drug()` |
| **원인** | `_normalize()` 로직이 용량 표기를 제거하고 성분명만 남긴다. 서로 다른 용량의 약품(250mg / 500mg / 1000mg)이 모두 같은 정규화 키로 축약되는데, `dict[str, str]`로 관리하다 보니 먼저 등록된 값이 나중 값을 덮어써 나머지 후보가 소실됐다. score가 1.0으로 반환되어 “정확히 일치”로 오판되는 점이 더 위험하다. |
| **영향 범위** | 24개 목업 테스트에서는 충돌 8그룹이 전부 외용제라 미발생. HIRA 약가마스터(30만 건) 적용 시 실제 발생 가능. |
| **해결** | `dict[str, str]` → `dict[str, list[str]]`로 변경해 모든 후보를 보존하도록 수정(PR #57). 신규 테스트 15건 추가. |
| **핵심 패턴** | 정규화 키가 충돌할 수 있는 사전은 `dict[str, str]` 대신 `dict[str, list[str]]`로 설계해 덮어쓰기를 방지한다. |

```python
# ❌ 문제가 된 코드 — 나중에 등록된 용량이 덮어써짐
norm_to_raw: dict[str, str] = {}
for raw, norm in zip(raw_pool, norm_pool):
    if norm in close_norm and norm not in norm_to_raw:
        norm_to_raw[norm] = raw

# ✅ 수정 — 모든 후보 보존
norm_to_raws: dict[str, list[str]] = {}
for raw, norm in zip(raw_pool, norm_pool):
    if norm in close_norm:
        norm_to_raws.setdefault(norm, []).append(raw)
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 복약 가이드 화면에서 생활습관 안내와 주의사항이 비어 보이거나, RAG 근거가 있는데도 "특별히 주의할 사항이 없어요"처럼 표시됨 |
| **발생 위치** | `frontend/src/pages/MedGuide.tsx`, `rag/rag/rag_chain.py` |
| **원인 1 — 프론트 응답 구조 불일치** | 2026.07.21 회의 반영 이후 실제 RAG 파이프라인은 생활습관 안내를 의약품별이 아니라 진단명별로 생성하고, `lifestyle_guide.guides[] = { diagnosis, guide }` 구조로 내려준다. 그런데 `MedGuide.tsx`의 "주의사항" 탭은 여전히 stub/과거 구조인 `lifestyle_guide.diet.avoid`, `lifestyle_guide.diet.drug_specific`만 생활 속 주의사항으로 읽고 있었다. 그래서 백엔드가 생활습관 안내를 정상 생성해도 주의사항 탭에는 표시되지 않을 수 있었다. |
| **원인 2 — LLM 응답 누락 방어 부족** | 허가사항 상세(`NB_DOC_DATA`)의 `사용상의주의사항` 섹션이 RAG context/source_refs에 포함되어도, LLM이 JSON 응답의 `precautions` 배열을 빈 배열로 보내면 화면에서는 약물별 주의사항이 없는 것으로 보였다. 즉 데이터 검색 실패가 아니라, "근거는 있는데 LLM이 표시용 필드를 비워 보낸 경우"에 대한 fallback이 없었다. |
| **해결** | `MedGuide.tsx`의 "주의사항" 탭에서 새 실제 응답 구조인 `lifestyle_guide.guides`도 함께 읽어 `진단명별 생활 속 주의사항`으로 표시하도록 수정했다. 또한 `rag_chain.py`에 `_fallback_precautions_from_context()`를 추가해 `사용상의주의사항`, `경고`, `금기`, `상호작용` 근거가 있는데 LLM이 `precautions`를 비우면 해당 context text를 짧게 잘라 주의사항으로 보강하도록 했다. dry-run 모드에서도 같은 fallback을 적용한다. |
| **테스트/검증** | `rag/tests/test_rag_chain.py`에 "LLM이 precautions를 비워도 사용상의주의사항 근거가 있으면 주의문구를 보강한다" 테스트 추가. `env PYTHONPATH=/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/rag uv run pytest rag/tests/test_rag_chain.py -q` 결과 40개 통과. `uv run ruff check rag/rag/rag_chain.py rag/tests/test_rag_chain.py` 통과. `frontend`에서 `npm run build` 성공. |
| **핵심 패턴** | RAG 응답 구조를 바꿀 때는 백엔드 생성 로직뿐 아니라 해당 데이터를 읽는 화면의 필드 접근도 같이 바꿔야 한다. 특히 stub/real 응답이 공존하는 과도기에는 `diet/exercise` 같은 과거 구조와 `guides[]` 같은 실제 구조를 모두 방어해야 한다. 또한 LLM이 구조화 필드를 비워 보낼 수 있으므로, source_refs/context에 명확한 근거가 있는 고위험 정보(주의사항 등)는 표시용 fallback을 별도로 둔다. |

```ts
// 실제 RAG 생활습관 응답 구조
lifestyle_guide: {
  diagnosis: "고혈압",
  guides: [
    { diagnosis: "고혈압", guide: "소금 섭취를 줄이고 규칙적으로 운동하세요." },
  ],
}
```

```python
# LLM이 precautions=[]로 응답해도 사용상의주의사항 근거가 있으면 보강
precautions = [str(p) for p in raw_precautions if str(p).strip()]
if not precautions:
    precautions = _fallback_precautions_from_context(used_items or context_items)
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 프론트 화면에서 생활습관 안내 카드가 약 개수만큼 생성되고, 3개 카드가 생겼을 때 앞의 1~2개 카드가 공란으로 보임 |
| **발생 위치** | `frontend/src/api/records.ts`, `frontend/src/pages/Result.tsx`, `frontend/src/pages/MedGuide.tsx` |
| **원인** | 최신 백엔드/RAG 생성 로직은 생활습관 안내를 고유 진단명 기준으로 `lifestyle_guide.guides[] = { diagnosis, guide }` 형태로 내려주는 것이 맞다. 하지만 기존 캐시나 과거 응답에는 `guides`가 문자열 배열이거나, 약 개수만큼 만들어진 배열 안에 빈 문자열/빈 객체가 섞인 형태가 남아 있을 수 있었다. 프론트는 `guides` 배열이 존재하면 모든 원소가 `{ diagnosis, guide }` 객체라고 가정하고 그대로 `entry.guide`를 렌더링했다. 그래서 배열 길이만큼 카드는 생기지만 `entry.guide`가 없는 항목은 빈 카드처럼 보였다. |
| **해결** | 화면 컴포넌트별로 임시 분기하지 않고, `frontend/src/api/records.ts`의 `RecordResult` 수신 지점에서 `lifestyle_guide.guides`를 정규화했다. 문자열 원소는 `{ diagnosis, guide }`로 변환하고, 본문이 비어 있는 항목은 제거한다. 이 정규화를 `createRecord`, `getRecord`, `createManualRecord`, `addMedicationItem`, `removeMedicationItem`, `confirmMedications` 응답에 모두 적용해 Result/MedGuide 등 여러 화면에서 같은 문제가 재발하지 않도록 했다. |
| **테스트/검증** | `frontend`에서 `npm run build` 성공. `env PYTHONPATH=/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/rag uv run pytest rag/tests/test_rag_chain.py -q -k "lifestyle or generate_guides_from_medications"` 결과 12개 통과. |
| **핵심 패턴** | 백엔드 응답 구조가 바뀐 뒤에도 기존 DB 캐시나 과거 레코드는 오래된 JSON 모양을 유지할 수 있다. 화면 컴포넌트에서 매번 방어하기보다 API 레이어에서 응답을 한 번 정규화해, 화면은 항상 같은 형태의 데이터를 받게 만드는 것이 안전하다. 특히 배열 렌더링은 "배열 길이"만 믿지 말고 실제 표시 본문이 있는 항목만 남겨야 빈 카드가 생기지 않는다. |

```ts
// 레거시/캐시 응답 예: 카드 3개가 생기지만 앞 2개는 표시 본문이 없음
lifestyle_guide: {
  diagnosis: "고혈압",
  guides: ["", "", "소금 섭취를 줄이고 규칙적으로 운동하세요."],
}

// API 레이어에서 화면용으로 정규화
guides = rawGuides
  .map((entry) => {
    if (typeof entry === "string") {
      const text = entry.trim();
      return text ? { diagnosis: guide.diagnosis || "", guide: text } : null;
    }
    // 객체형도 guide 본문이 비어 있으면 제거
  })
  .filter((entry) => entry !== null);
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 복약가이드의 `주의사항`·`생활습관` 탭이 다시 비어 보임 |
| **발생 위치** | `backend/routers/rag_router.py`, `rag/rag/rag_chain.py` |
| **원인 1 — 기존 가이드 캐시 재사용** | 이전에 `precautions=[]` 또는 `lifestyle_guide.guides=[]`처럼 빈 결과가 `GuideCache`에 저장된 경우, 이후 코드를 고쳐도 같은 처방 조합은 캐시 히트가 나서 최신 생성 로직을 타지 않는다. 기본 `GUIDE_DATA_VERSION`이 계속 `v1.0`이라 이전 빈 캐시가 자연 무효화되지 않았다. |
| **원인 2 — 생활습관 LLM 빈 본문 방어 부족** | 의약품 주의사항은 `_fallback_precautions_from_context()`로 보강했지만, 생활습관은 LLM이 `lifestyle_guide`를 빈 문자열로 반환하면 검색 근거가 있어도 빈 본문 그대로 저장될 수 있었다. |
| **해결** | `GUIDE_DATA_VERSION` 기본값을 `v1.1`로 올려 기존 빈 캐시를 우회하도록 했다. 또한 `rag_chain.py`에 `_fallback_lifestyle_guide_from_context()`를 추가해 LLM이 생활습관 본문을 비워 보내면 질병관리청/curated 생활지침 컨텍스트 문구를 표시용으로 보강하도록 했다. |
| **재발 방지** | RAG 응답 구조 또는 표시용 fallback을 바꿀 때는 캐시 키에 쓰는 `GUIDE_DATA_VERSION`도 함께 올린다. LLM이 구조화 필드를 비워 보내는 케이스는 의약품 주의사항뿐 아니라 생활습관 본문에도 동일하게 방어한다. |

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 챗봇/가이드 생성이 느리게 느껴지고, Langfuse에서 ChromaDB retrieve와 LLM generation 구간을 분리해서 확인하기 어려움 |
| **발생 위치** | `rag/rag/rag_chain.py`, `rag/rag/vectorstore.py`, `backend/routers/chat_router.py` |
| **원인 1 — 복약가이드 생성 비용 구조** | 복약가이드 생성은 self-consistency를 위해 `SELF_CONSISTENCY_SAMPLES=3` 기본값으로 같은 질문을 3회 생성하고 가장 일관된 답을 고른다. 처방전 약이 3개이고 고유 진단명이 1개면 `3 * (약 3개 + 진단명 1개) = 12회` LLM 호출이 직렬로 발생한다. 따라서 RAG 검색 자체보다 LLM 반복 호출이 전체 지연의 주된 원인이 될 수 있다. |
| **원인 2 — 스트리밍 Langfuse 관측 누락** | `/chat/ask`는 `chat-ask` span 아래에 `chat-llm-answer` generation이 남지만, `/chat/ask/stream`은 `chat-ask-stream` trace만 남고 스트리밍 LLM 생성 구간이 별도 generation observation으로 남지 않았다. 그래서 Langfuse에서 "retrieve가 느린지, LLM 생성이 느린지"를 스트리밍 경로 기준으로 분리해 보기 어려웠다. |
| **해결** | `backend/routers/chat_router.py`의 `/chat/ask/stream` 경로에 `chat-stream-llm-answer` Langfuse generation observation을 추가했다. generation input에는 마스킹된 질문, 환자 컨텍스트 줄 수, RAG 참고자료 수, DUR 참고자료 수를 넣고, output에는 마스킹된 답변을 남긴다. 기존 `rag/rag/vectorstore.py`의 `retrieve-from-chromadb` retriever span과 함께 보면 한 질문에서 retrieve → generation 흐름을 분리해 확인할 수 있다. |
| **ChromaDB retrieve 테스트 기준** | 생활습관/음식/운동 질문은 `doc_type=kdca_health_info`를 우선 조회한다. 의약품 효능/주의사항 질문은 `doc_type=drug`를 우선 조회한다. KDCA 필터에서 결과가 없으면 필터 없는 전체 검색으로 폴백한다. 임부금기/노인주의/병용금기 같은 DUR 전용 질문은 ChromaDB가 아니라 DUR 조회 경로를 타며, 이 경우 `retrieve-dur-lookup` retriever span을 남긴다. |
| **테스트/검증** | `env PYTHONPATH=/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/backend:/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/rag uv run pytest backend/tests/test_chat_router_context.py backend/tests/test_chat_ask_stream.py -q` 결과 34개 통과. `uv run ruff check backend/routers/chat_router.py backend/tests/test_chat_ask_stream.py` 통과. |
| **평가 방법** | Langfuse에서 한 질문 trace를 열고 `retrieve-from-chromadb` 또는 `retrieve-dur-lookup`이 먼저 찍히는지 확인한다. 이후 `chat-stream-llm-answer` generation의 duration을 보고 LLM 생성 지연을 판단한다. 품질 평가는 최소 기준으로 (1) 질문 유형에 맞는 retriever 필터를 탔는지, (2) `retrieved_count > 0`인지, (3) 프론트 `source_refs`에 실제 참고자료가 표시되는지, (4) 답변이 검색 근거와 모순되지 않는지를 본다. |

```text
질문 유형별 기대 retrieve 경로

고혈압에 좋은 음식이 뭐야?        -> ChromaDB filter={"doc_type": "kdca_health_info"}
이 약 효능이 뭐야?                 -> ChromaDB filter={"doc_type": "drug"}
임부금기야? / 같이 먹으면 안 돼?   -> DUR 조회, retrieve-dur-lookup span
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | Langfuse에서 병용금기 질문인데 `retrieve-from-chromadb`가 찍히고, `노바스크정5밀리그람 효능` 질문의 참고자료에 `타이레놀` 문서가 표시됨 |
| **발생 위치** | `backend/routers/chat_router.py` |
| **원인 1 — DUR 질문 분류 누락** | DUR은 ChromaDB에 넣지 않고 DUR API/CSV 직접 조회로 처리해야 한다. 그런데 챗봇의 DUR 전용 질문 판별 키워드가 일부 병용 표현을 충분히 잡지 못하면 `_retrieve_chat_rag_docs()`가 실행되어 ChromaDB `doc_type=drug` 검색으로 빠질 수 있었다. 이 경우 Langfuse에는 `retrieve-dur-lookup`이 아니라 `retrieve-from-chromadb`가 찍인다. |
| **원인 2 — 약명 명시 질문에도 의미검색만 사용** | `노바스크정5밀리그람 효능`처럼 질문 안에 약명이 명확히 있어도 기존 `_retrieve_chat_rag_docs()`는 `doc_type=drug` 필터를 건 ChromaDB 유사도 검색만 수행했다. 유사도 검색은 `효능` 같은 일반 의도 단어에 끌려 질문 속 약명과 다른 약 문서(예: 타이레놀)를 가져올 수 있고, 프론트는 이 검색 결과를 그대로 `source_refs`에 표시했다. |
| **해결** | DUR 키워드에 `병용 가능`, `병용가능`, `병용해도`를 추가해 병용금기/병용 가능성 질문이 ChromaDB로 새지 않게 했다. 단, `먹어도`처럼 너무 넓은 표현은 일반 복약 질문까지 DUR로 오분류해 제거했다. 또한 일반 의약품 RAG 질문에서 약명 후보를 추출하고, ChromaDB 유사도 검색 전에 `search_by_item_name()` 정확 조회를 먼저 수행하도록 했다. 정확 조회가 없어서 유사도 검색으로 폴백하더라도, 질문 속 약명과 `item_name`이 맞지 않는 문서는 참고자료에서 제거한다. |
| **테스트/검증** | `backend/tests/test_chat_router_context.py`에 병용 가능 질문이 ChromaDB를 호출하지 않는 테스트, 약명 명시 질문이 item_name 직접 조회를 우선하는 테스트, 노바스크 질문에 타이레놀 문서가 검색돼도 source_refs로 노출하지 않는 테스트를 추가했다. `backend/tests/test_chat_router_context.py backend/tests/test_chat_ask_stream.py` 결과 36개 통과. `ruff check backend/routers/chat_router.py backend/tests/test_chat_router_context.py backend/tests/test_chat_ask_stream.py` 통과. |
| **핵심 패턴** | 안전성 판정(DUR 병용금기/임부금기/연령금기/노인주의)은 의미검색으로 추정하지 말고 규칙 조회 경로로 보내야 한다. 반대로 일반 의약품 효능/주의사항 질문은 ChromaDB를 쓰되, 질문에 특정 약명이 명시되어 있으면 유사도 점수보다 `item_name` 일치 여부를 우선해야 잘못된 참고자료가 붙지 않는다. |

```text
기대 Langfuse 흐름

노바스크정5밀리그람과 타이레놀 병용 가능해?
-> retrieve-dur-lookup
-> retrieve-from-chromadb 없음

노바스크정5밀리그람 효능 알려줘
-> retrieve-from-chromadb 또는 item_name 직접 조회
-> source_refs에 노바스크 계열 문서만 허용
-> 타이레놀 문서는 제거
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | Langfuse에서 DUR 질문의 `retrieve-dur-lookup` duration이 약 21초까지 길어짐 |
| **발생 위치** | `backend/routers/chat_router.py` |
| **원인** | DUR 데이터는 현재 CSV가 아니라 식약처 Open API 4종(병용금기/노인주의/연령금기/임부금기)을 직접 호출한다. 따라서 "필요 없는 컬럼 삭제"로는 큰 개선을 기대하기 어렵다. 실제 병목 후보는 질문에서 추출한 약명 후보를 e약은요/허가정보로 확장한 뒤, 확장된 조회어마다 병용금기와 caution 계열 API를 모두 호출하는 구조였다. 예를 들어 병용금기 질문인데도 노인주의·연령금기·임부금기 API까지 함께 호출될 수 있어 네트워크 호출 수가 불필요하게 늘어났다. |
| **해결** | `retrieve-dur-lookup` 안에 `dur-extract-candidates`, `dur-resolve-lookup-names`, `dur-query-api` 하위 span을 추가해 Langfuse에서 후보 추출/약명 매핑/실제 API 조회 시간을 분리해서 볼 수 있게 했다. 또한 `_dur_lookup_modes()`를 추가해 병용금기 질문은 병용금기 API만, 임부금기/노인주의/연령금기 질문은 caution 계열 API만 조회하도록 불필요한 호출을 줄였다. 질문 의도가 애매하면 안전하게 양쪽을 모두 조회한다. |
| **테스트/검증** | `backend/tests/test_chat_router_context.py`에 병용금기 질문에서 caution 조회를 생략하는 테스트, 임부금기 질문에서 병용금기 조회를 생략하는 테스트를 추가했다. `env PYTHONPATH=/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/backend:/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/rag uv run pytest backend/tests/test_chat_router_context.py backend/tests/test_chat_ask_stream.py -q` 결과 39개 통과. `uv run ruff check backend/routers/chat_router.py backend/tests/test_chat_router_context.py` 통과. |
| **확인 방법** | 서버 재시작 후 병용금기 질문을 다시 보내고 Langfuse trace에서 `retrieve-dur-lookup`을 펼친다. `dur-query-api`가 여전히 길면 실제 식약처 API 응답 지연 또는 조회어 수 과다를 의심한다. `dur-resolve-lookup-names`가 길면 e약은요/허가정보 이름 매핑 API가 병목이다. |
| **핵심 패턴** | 관측(span)은 속도를 직접 올리는 기능이 아니라 병목 위치를 찾는 장치다. 속도 개선은 실제 호출 수를 줄이거나 캐시/인덱스를 적용해야 한다. 외부 API 기반 조회에서는 컬럼 삭제보다 "질문 의도에 맞는 엔드포인트만 호출하기"와 "같은 조회어 반복 호출 방지"가 우선이다. |

```text
Langfuse에서 기대되는 DUR 세부 span

retrieve-dur-lookup
├─ dur-extract-candidates     # 질문에서 약명 후보와 DUR 카테고리 판단
├─ dur-resolve-lookup-names   # e약은요/허가정보 기반 품목명·성분명 확장
└─ dur-query-api              # 식약처 DUR API 실제 호출
```

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | Langfuse 실측 결과 `노바스크정5밀리그람과 타이레놀 병용 가능해?` 질문의 전체 응답이 40.88초까지 걸림 |
| **발생 위치** | `backend/routers/chat_router.py` |
| **관측 결과** | `chat-ask-stream` 40.88초 중 `retrieve-dur-lookup`이 36.02초를 차지했고, 그 안에서 `dur-resolve-lookup-names` 8.10초, `dur-query-api` 27.73초가 걸렸다. 반면 `chat-stream-llm-answer`/`ChatOpenAI`는 2.43초라 LLM 생성이 주 병목은 아니었다. |
| **원인** | 질문 후보 추출에서 `가능해`가 의약품명 후보로 잘못 들어가 `raw_candidate_names = ["노바스크정5밀리그람", "타이레놀", "가능해"]`가 됐다. 이후 e약은요/허가정보 확장 결과가 최대 10개까지 늘어나면서, 병용금기 API를 10개 조회어에 대해 호출했다. 외부 DUR API 호출 자체가 느린 상황에서 불필요한 후보와 과도한 조회어 수가 지연을 키웠다. |
| **해결** | DUR 후보 stopword에 `가능`, `가능해`, `가능한가요`, `가능한지`, `가능할까요`를 추가해 질문 의도 표현이 약명 후보로 들어가지 않게 했다. 또한 `_resolve_dur_lookup_names()`의 최종 조회어 수를 10개에서 6개로 줄여 한 질문에서 발생하는 외부 DUR API 호출 수를 제한했다. |
| **테스트/검증** | `env PYTHONPATH=/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/backend:/Users/kim-yunghye/Documents/Medication_guidance_based_on_medical_records/rag uv run pytest backend/tests/test_chat_router_context.py backend/tests/test_chat_ask_stream.py -q` 결과 39개 통과. `uv run ruff check backend/routers/chat_router.py backend/tests/test_chat_router_context.py` 통과. |
| **다음 확인** | 같은 질문을 다시 보내 Langfuse에서 `dur-extract-candidates`가 `["노바스크정5밀리그람", "타이레놀"]`처럼 의약품 후보만 남는지 확인한다. 그래도 `dur-query-api`가 길면 외부 API 자체 지연이므로, 다음 단계는 DUR 결과 캐시 TTL 확대 또는 로컬 DUR 마스터 파일/인덱스 전환을 검토한다. |

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 개별 약품 상세 화면에서 `노바스크정5밀리그람` 주의사항이 백엔드에는 있는데 프론트에는 `등록된 주의사항이 없어요`로 표시됨 |
| **발생 위치** | `frontend/src/api/records.ts`, `frontend/src/pages/DrugInfo.tsx`, `backend/routers/ocr_router.py` |
| **관측 결과** | `GET /ocr/drug-info?drug_name=노바스크정5밀리그람`을 직접 호출하면 `precautions`와 `patient_summary`가 정상 반환됐다. 즉 백엔드 조회 실패가 아니라 프론트 요청 처리 문제였다. 같은 live 조회는 약품에 따라 시간이 크게 달라졌고, 직접 호출 기준 `아스피린`은 약 13초, `노바스크정5mg`은 약 22초까지 걸렸다. |
| **원인** | `getDrugIndication()`이 공통 `monitoringClient` timeout 10초를 그대로 사용했다. `/ocr/drug-info`는 e약은요/허가사항/DUR live 조회와 환자용 LLM 요약을 한 번에 수행하므로 10초를 넘을 수 있다. 이 경우 axios가 먼저 timeout으로 실패하고 `DrugInfo.tsx`가 `setDrugInfo(null)`로 폴백하면서 화면에는 데이터가 없는 것처럼 보였다. |
| **해결** | `getDrugIndication()` 호출에 OCR 등록/가이드 생성 경로와 같은 `timeout: 120000`을 별도로 지정했다. 서버가 실제로 데이터를 반환하는 느린 약품 상세 조회는 프론트가 중간에 포기하지 않고 기다리도록 한다. |
| **재발 방지** | 외부 공공 API 또는 LLM 요약이 포함된 화면 조회는 공통 10초 timeout을 그대로 쓰지 않는다. 사용자에게 로딩 문구를 보여주는 화면이라면 API 클라이언트 timeout도 그 로딩 시간에 맞게 별도 지정해야 한다. |

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 환자 화면의 `환자 연결관리`에서 보호자/요양보호사/생활지원사/사회복지사를 초대하는 기능이 사라짐 |
| **발생 위치** | `frontend/src/pages/Connect.tsx`, `backend/routers/care_router.py` |
| **원인** | 2026.07.21 회의 내용 반영 과정에서 “보호자/지원인력의 초대하기 삭제”를 보호자류 사용자의 초대 UI 정리로만 적용해야 했는데, 환자가 보호자·지원인력을 초대하는 기존 흐름까지 함께 삭제됐다. 백엔드는 이미 생성된 환자→보호자 초대를 수락하는 코드는 남아 있었지만, `InvitationCreate` 스키마와 `/care/invitations` 생성 로직이 `relation_type="patient"`만 허용하게 줄어 새 초대를 만들 수 없었다. |
| **해결** | `/care/invitations` 생성 API를 양방향으로 분기했다. `relation_type="patient"`이면 기존처럼 보호자/지원인력이 환자를 초대하고, `guardian/caregiver/life_support_worker/social_worker`이면 환자 접근 권한을 검증한 뒤 환자가 보호자·지원인력을 초대하도록 복구했다. 프론트 `Connect.tsx`에는 환자 로그인일 때만 보이는 보호자·지원인력 초대 패널을 다시 추가했다. |
| **재발 방지** | 회의 문구가 “삭제”일 때는 어떤 사용자 그룹의 어떤 진입점인지 명확히 구분한다. 특히 같은 `초대하기`라도 환자→보호자 초대와 보호자→환자 초대는 업무 흐름이 다르므로 API 스키마/수락 로직/화면 진입점을 함께 확인해야 한다. |

---

| 날짜 | 2026.07.22 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 등록내역에서 삭제를 눌러도 다음 로그인 때 삭제가 안 된 것처럼 보이고, 연결관리의 대기중 초대를 취소할 수 없음. 보호자 `환자 관리`에서도 환자 삭제 버튼이 동작하지 않음 |
| **발생 위치** | `backend/routers/records_router.py`, `frontend/src/pages/Records.tsx`, `backend/routers/care_router.py`, `frontend/src/pages/Connect.tsx`, `frontend/src/pages/PatientManagement.tsx` |
| **원인** | 등록내역 삭제 API는 `MedicalRecord.deleted_at`과 `MedicationSchedule.record_id` 기반 일정 비활성화만 처리했다. 따라서 처방전에서 파생된 `PatientMedication.prescription_id` 데이터와 그 내약 기반 일정이 있으면 다른 화면에 계속 남아 “삭제가 안 됐다”고 보일 수 있었다. 프론트도 삭제 성공 후 로컬 배열만 필터링하고 서버 목록을 다시 확인하지 않았다. 연결관리의 대기중 초대는 목록 조회만 있고 보낸 초대를 취소하는 API/버튼이 없었다. 또한 보호자 `환자 관리`의 X 버튼은 보호자-환자 연결 해제가 아니라 환자 계정 자체 삭제 API(`/monitoring/patients/{patient_id}`)를 호출하고 있어, 환자에게 처방/일정/기록이 있으면 삭제가 실패할 수 있었다. |
| **해결** | 등록내역 삭제 시 `PatientMedication.prescription_id == record_id`인 내약을 soft-delete하고, 해당 내약에 연결된 일정도 비활성화하도록 보강했다. 프론트 `Records.tsx`는 삭제 후 `listRecords()`를 다시 호출해 서버 기준 목록으로 갱신한다. 연결관리에는 `DELETE /care/invitations/{invitation_id}`를 추가해 pending 초대를 `cancelled`로 바꾸고, `Connect.tsx`의 대기중 초대 목록에 삭제 버튼을 추가했다. 보호자 `PatientManagement.tsx`의 X 버튼은 환자 계정 삭제 대신 기존 `unlinkCaregiverPatient(caregiverId, patientId)`를 호출해 현재 보호자와의 연결만 해제하도록 바꿨다. |
| **재발 방지** | 사용자가 “삭제”라고 인식하는 범위가 화면 카드 1개인지, 그 카드에서 파생된 내약/일정까지인지, 또는 관계 해제인지 확인해야 한다. soft-delete를 쓰는 데이터는 삭제 후 프론트 로컬 상태만 바꾸지 말고 서버 재조회로 실제 영속 상태를 확인한다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 복약일정에서 복용시간대 삭제가 실제 DB 삭제로 이어지지 않고, 보호자/지원인력 화면의 사용자명·메뉴 구조가 환자 중심 흐름과 맞지 않음 |
| **발생 위치** | `backend/routers/monitoring_router.py`, `backend/routers/auth_router.py`, `frontend/src/pages/Schedule.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/MyPage.tsx`, `frontend/src/pages/PatientManagement.tsx`, `frontend/src/components/NavBar.tsx`, `frontend/src/pages/SignUp.tsx`, `frontend/src/pages/MonitoringDashboard.tsx`, `frontend/src/pages/MonitoringDayLogs.tsx`, `frontend/src/pages/DrugDetail.tsx`, `frontend/src/pages/CareEducation.tsx` |
| **원인** | `DELETE /monitoring/schedules/{schedule_id}`가 `MedicationRecord`만 정리하고 `NotificationLog`, 레거시 `MedicationLog` 참조는 정리하지 않아 알림/체크 기록이 붙은 일정은 FK 제약으로 삭제가 실패할 수 있었다. 일부 보호자 화면은 `NavBar userName="김보호"`를 하드코딩해 실제 로그인 이름과 다르게 보였다. 기관/지원인력 가입은 `Caregiver.name`에 기관명을 저장해 `test.worker@team.local`처럼 담당자명(`테스트요양보호사`)이 있는 계정도 화면 이름이 기관명(`행복요양원`)으로 보일 수 있었다. 또한 보호자/지원인력도 복약일정·알림설정·등록내역 메뉴를 직접 볼 수 있어, 환자관리 → 환자 리스트 → 환자별 하위 메뉴로 들어가는 흐름이 약했다. |
| **해결** | 일정 삭제 시 `MedicationRecord`, `MedicationLog`, `NotificationLog`를 먼저 삭제하고 flush한 뒤 `MedicationSchedule`을 삭제하도록 변경했다. 기관/지원인력 가입 시 화면 표시 이름은 담당자 이름(`managerName`)으로 저장하고 기관명은 `org_name`에만 저장하도록 분리했다. 백엔드 `create_caregiver()`도 기관 계정이면 `manager_name`을 표시 이름으로 저장하도록 방어 로직을 추가했다. 로그인/토큰 갱신/계정 전환 응답과 마이페이지는 기존 DB 데이터 대응을 위해 기관 계정의 `manager_name`을 우선 표시한다. 로그인 성공 시 보호자/지원인력은 기존 `patient_id`를 지우고 환자관리 화면으로 이동하도록 변경했다. 마이페이지와 상단 네비게이션은 역할별 메뉴를 분리해 보호자/지원인력은 `환자 관리`, `연결관리`, `설정` 중심으로 보이게 했다. 환자관리 목록에는 환자별 `복약일정`, `알림설정`, `등록내역`, `모니터링` 버튼을 추가해 선택한 환자의 하위 기능으로 이동하게 했다. `김보호` 하드코딩 화면은 `getCurrentUserName()`을 사용하도록 수정했다. |
| **테스트/검증** | `backend/tests/test_monitoring_missed_merge.py`에 체크 기록, 레거시 로그, 알림 로그가 붙은 일정도 삭제되는 회귀 테스트를 추가했다. `npm run build` 통과. `uv run pytest backend/tests/test_auth_switch_account.py backend/tests/test_update_email_normalization.py -q` 결과 9개 통과. |
| **확인 결과** | 원격 DB 단건 조회 결과 `test.worker@team.local`은 `name=행복요양원`, `relation_type=organization`, `org_name=행복요양원`, `manager_name=테스트요양보호사`로 저장돼 있었다. 따라서 화면 이름이 기관명으로 나온 원인은 기존 데이터의 표시 이름 컬럼이 기관명으로 저장된 것이 맞다. 신규 가입 데이터는 담당자명으로 저장되며, 기존 테스트 계정은 로그인 응답/마이페이지에서 `manager_name`을 우선 표시해 화면상 보정한다. |
| **재발 방지** | 역할별 화면을 수정할 때는 상단 네비게이션, 마이페이지, 로그인 후 이동 경로, 환자 선택 후 하위 화면 진입 경로를 한 세트로 본다. 하드코딩 표시명은 테스트 계정에서는 빨리 눈에 띄지만 실제 사용자 경험을 깨므로 `localStorage.user_name` 또는 인증 API 응답 기반으로 통일한다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 마이페이지 역할별 메뉴 분리 후 요양보호사/보호자 계정에서 "내 정보" 진입 경로가 사라졌고, 환자 관리 화면에 연결관리와 중복되는 "환자 연결"/"받은 초대" UI가 남아있었음 |
| **발생 위치** | `frontend/src/pages/MyPage.tsx`, `frontend/src/pages/PatientManagement.tsx` |
| **원인** | 마이페이지 메뉴를 `patientMenu`/`caregiverMenu`로 분리하는 과정(`d5025ca`)에서 "내 정보" 항목을 `caregiverMenu`에는 옮기지 않고 누락했다. `PatientManagement.tsx`에는 온보딩용으로 만들어둔 "환자 연결" 버튼과 "받은 초대" 카드가 그대로 남아있었는데, 같은 기능이 `Connect.tsx`(연결관리)에도 이미 있어 두 화면에서 중복 노출되고 있었다. |
| **해결** | `caregiverMenu` 맨 앞에 `{ label: "내 정보", to: "/mypage/info" }`를 복구했다. `PatientManagement.tsx`에서 "환자 연결" 버튼, `InvitePatientPanel`, "받은 초대" 카드와 관련 상태·핸들러·미사용 import를 전부 제거해 `연결관리` 화면과의 중복을 없앴다. |
| **테스트/검증** | `npm run build`, `npm run lint` 통과. |
| **재발 방지** | 역할별로 메뉴를 나눌 때는 기존 메뉴에 있던 항목이 새 메뉴 배열 전부에 빠짐없이 옮겨졌는지 diff로 확인한다. 같은 기능(초대 발송/수락)을 여러 화면에 중복 배치하지 말고 한 화면(연결관리)에만 두고 나머지 화면은 그 화면으로 안내한다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | (1) 지원인력 계정이 마이페이지 "화면·챗봇 설정"에 들어가면 설정 화면 대신 환자 관리 화면으로 튕김 (2) 회원가입 생년월일 입력란에 형식 안내/오류 표시가 전혀 없음 (3) 이메일이 기관/보호자 등 관계(역할) 구분 없이 테이블 전체에서 유니크해서, 같은 사람이 보호자이면서 동시에 요양보호사로도 같은 이메일로 가입할 수 없었음(전화번호는 이미 역할별로 허용됨) (4) 회원가입 휴대폰 본인인증 6자리 코드 입력칸에서 숫자가 칸 밖으로 넘침 |
| **발생 위치** | `frontend/src/pages/Settings.tsx`, `frontend/src/lib/session.ts`, `frontend/src/pages/SignUp.tsx`, `backend/models.py`, `backend/routers/monitoring_router.py`, `backend/alembic/versions/dd2141948419_...py` |
| **원인** | (1) `Settings.tsx`가 Dashboard/Schedule 등과 동일하게 `useGuardedPatientId()`를 그대로 써서, 케어하는 환자가 0명이거나 2명 이상인데 아직 하나를 고르지 않은 지원인력은 이 화면에 들어오는 즉시 `/patients`로 강제 이동됐다 — "글자 크기"처럼 환자와 무관한 설정까지 덩달아 막혔다. (2) `SignUp.tsx`의 생년월일 `Field`에는 애초에 힌트/에러를 표시할 로직 자체가 없었다(값은 그냥 자유 텍스트로 저장). (3) `Caregiver.email`이 `unique=True`(DB 유니크)라 relation_type과 무관하게 테이블 전체에서 막혔다 — `phone_hash`는 2026-07-22에 이미 relation_type별로 풀어뒀지만 email은 그대로였다. (4) 인증코드 input이 `flex-1`인데 min-width가 브라우저 기본값(auto)이라, `font-size 26px + letterSpacing 0.5em` 기준 6자리 내용 너비가 타이머 박스와 함께 있는 flex row보다 넓어지면 줄어들지 못하고 넘쳤다. |
| **해결** | (1) `useGuardedPatientId(options?: { silent?: boolean })`에 `silent` 옵션을 추가해 리다이렉트를 끌 수 있게 하고, `Settings.tsx`는 `{ silent: true }`로 호출 — 환자가 아직 안 정해졌으면 챗봇 이름 카드만 숨기고 글자 크기 설정은 그대로 보여준다. (2) 생년월일 입력란 위에 "현재 이후로도 가입이 가능해요."(대리 가입 등으로 정확한 생년월일을 모를 수 있어 미래 날짜도 허용한다는 안내) 힌트를 추가하고, `isValidBirthDate()`로 연/월/일이 실제 존재하는 날짜인지만 검사해(미래 여부는 검사하지 않음) 형식이 잘못됐을 때 "생년월일이 정확한지 확인해주세요."를 표시하도록 했다. (3) `Caregiver.email`의 DB 유니크 인덱스를 제거하는 마이그레이션을 추가하고(`ix_caregivers_email`을 `unique=False`로 재생성), `create_caregiver`/`check_caregiver_duplicate`/`update_caregiver`의 이메일 중복 검사에 phone_hash와 동일하게 `relation_type` 조건을 추가했다. (4) 인증코드 input에 `min-w-0`을 추가해 실제로 줄어들 수 있게 하고, 폰트 크기(26px→22px)와 자간(0.5em→0.35em)도 여유 있게 줄였다. |
| **테스트/검증** | `backend/tests/test_auth_signup_login.py`에 "같은 이메일로 relation_type이 다르면 가입 허용, 같으면 409" 회귀 테스트 추가. `uv run pytest tests/test_auth_signup_login.py tests/test_auth_switch_account.py tests/test_care_router_invitations.py tests/test_invitation_accept_caregiver_id_auth.py tests/test_login_lockout_and_password_reset.py tests/test_scheduler.py tests/test_update_email_normalization.py -q` 77개 통과. `npm run build`, `npm run lint` 통과. 복약일정 삭제는 실제 로컬 서버에서 일정 생성→체크인(알림/기록 연결)→삭제→목록 재조회까지 실행해 FK 삭제와 화면 반영(로컬 상태 필터링) 모두 정상 동작을 재확인했다(코드 변경 없음). |
| **재발 방지** | 여러 화면이 같은 가드 훅(`useGuardedPatientId` 등)을 공유할 때는, 그 화면이 정말로 "환자가 반드시 정해져야만" 보여줄 수 있는 화면인지 먼저 따진다 — 화면 일부만 환자 종속적이면 훅에 silent 옵션을 주거나 화면을 쪼갠다. 관계(역할)별로 중복을 허용해야 하는 필드(phone_hash)가 있다면, 같은 계정에 있는 유사한 필드(email)도 나중에 똑같은 요구가 생길 수 있다는 걸 염두에 두고 한 번에 점검한다. `flex-1` + 큰 `letterSpacing`/폰트 조합의 입력창은 항상 `min-w-0`을 같이 붙여야 실제로 줄어든다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | PR #79 리뷰 코멘트 — `NavBar.tsx`가 `localStorage.getItem("caregiver_id")`를 직접 읽어 나머지 코드베이스가 쓰는 `lib/session.ts`의 `getCurrentCaregiverId()` 관례와 어긋남 |
| **발생 위치** | `frontend/src/components/NavBar.tsx` |
| **원인** | NavBar가 지원인력/환자 메뉴를 나누는 로직을 짜면서, 이미 있던 `getCurrentCaregiverId()` 헬퍼를 쓰지 않고 `localStorage.getItem`을 직접 호출했다. |
| **해결** | `lib/session.ts`의 `getCurrentCaregiverId()`를 import해서 `localStorage.getItem("caregiver_id")` 대신 쓰도록 교체. 동작은 동일(값이 있으면 지원인력 메뉴, 없으면 환자 메뉴). |
| **테스트/검증** | `npm run build`, `npm run lint` 통과. |
| **재발 방지** | localStorage의 로그인/역할 관련 키(`caregiver_id`, `patient_id`, `user_name`, `access_token`)는 화면에서 직접 읽지 말고 항상 `lib/session.ts`의 헬퍼를 거친다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | 회원가입 생년월일 입력이 순수 자유 텍스트라, 숫자만 입력하면 "."을 직접 타이핑해야 했음(사용자 요청 — 숫자 4자리 뒤/2자리 뒤에 "."이 자동으로 붙었으면 함) |
| **발생 위치** | `frontend/src/pages/SignUp.tsx` |
| **원인** | 생년월일 `Field`의 `onChange`가 입력값을 그대로 `setBirthDate`에 넣기만 해서 자동 서식 로직이 없었다. |
| **해결** | `formatBirthDateInput()`을 추가해 입력값에서 숫자만 추출한 뒤 4자리(연) 뒤, 6자리(연+월) 뒤에 "."을 붙여 재조립하도록 했다. 8자리(연월일)를 넘는 입력은 잘라낸다. 매 입력마다 숫자만 남기고 다시 조립하는 방식이라 백스페이스로 지울 때도 자연스럽게 재적용된다. |
| **테스트/검증** | `npm run build`, `npm run lint` 통과. |
| **핵심 패턴** | 자동 구분자 삽입은 "매번 숫자만 추출 → 자리수 기준으로 구분자를 다시 붙여 조립"하는 방식이 커서 위치를 직접 추적하는 것보다 단순하고 backspace에도 안전하다. 다만 구분자 바로 뒤에서 backspace를 누르면 자리수가 그대로라 아무 변화가 없어 보일 수 있는 건 이 방식의 알려진 한계다. |

---

| 날짜 | 2026.07.23 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | (1) 처방전 등록 시 "1회 투약량"이 실제로는 성분 함량(mg)이라 "환자가 한 번에 정/캡슐 몇 개를 먹는지"(1회 복용량)를 알 수 없었음 (2) 처방전 확인 화면에서 복용시간대를 하나만 골라도 그 즉시 "확인 완료"로 카드가 접혀, "1일 3회"처럼 여러 시간대를 골라야 하는 경우 나머지를 고르기 전에 잠겨버림 (3) 복약 가이드의 "주의사항" 탭이 복약 지도 탭(약물별 부작용)과 내용이 겹치고, "생활습관" 탭은 진단명당 자유 텍스트 한 단락이라 식사/운동/그 외, 권장/비권장 구분이 안 됨 |
| **발생 위치** | `backend/services/parsing_rules.py`, `backend/services/ocr_interface.py`, `backend/models.py`, `frontend/src/pages/PrescriptionReview.tsx`, `rag/rag/schemas.py`, `rag/rag/rag_chain.py`, `backend/routers/rag_router.py`, `backend/routers/chat_router.py`, `frontend/src/api/records.ts`, `frontend/src/pages/MedGuide.tsx`, `frontend/src/pages/Result.tsx` |
| **원인** | (1) `dosage` 필드는 `DOSAGE_RE`/`_dm_dosage`로 약품명에 붙은 mg/g/ml/% 성분 함량만 추출했고, 실제 처방전에 있는 "1회 복용량"(정/캡슐 개수, 예: "1.00", "1정", "1T")은 어디서도 추출하지 않았다 — 공식 포맷의 수량 컬럼은 소수점 때문에 기존 `col_nums` 정규식에서 오히려 제외되고 있었다. (2) `PrescriptionReview.tsx`의 `addDoseTiming`/`addCustomTime`/`addInterval`이 시간대를 추가할 때마다 `maybeConfirm(id)`를 호출해, `computeIssues`가 복용시간을 검사하지 않는데도(필수 항목이 아님) 첫 클릭 즉시 카드가 완료 처리로 접혔다. (3) `LifestyleGuideResult.guide`가 진단명당 자유 텍스트 한 단락이라 애초에 카테고리·권장/비권장 구분이 스키마에 없었고, "주의사항" 탭은 복약 지도 탭에서 약을 눌러 들어가는 DrugDetail.tsx와 같은 내용(약물별 부작용)을 중복 표시하고 있었다. |
| **해결** | (1) `extract_dose_quantity()`를 추가해 "1회 1정"/"1T"(약식) 같은 명시적 단위 표기를 우선 인식하고, 단위 없이 숫자만 있는 컬럼(예: "1.00")은 약품명의 제형(정/캡슐 등)을 붙여 완성하도록 했다. `official`/`abbrev`/`list`/`table` 네 포맷 파서 전부에 적용하고, 프론트 라벨/검증 메시지를 "1회 복용량"으로 바꿨다. (2) 시간대 추가 함수들에서 `maybeConfirm` 호출을 제거하고, "복용시간 확인 완료" 버튼을 새로 만들어 사용자가 다 고른 뒤 직접 눌러야 확정되게 했다. (3) "주의사항" 탭을 삭제하고(약물별 부작용은 복약 지도 → DrugDetail.tsx에서 계속 볼 수 있음), `LifestyleGuideResult`를 `diet`/`exercise`/`other` × `recommended`/`avoid`로 구조화했다(LLM 프롬프트·Pydantic 스키마·`rag_router.py`의 stub/실제 페이로드·`chat_router.py`의 챗봇 컨텍스트 요약·프론트 타입/렌더링까지 전부 반영). 챗봇 컨텍스트와 프론트 정규화 로직은 이번 변경 이전에 이미 저장된 옛 모양(자유 텍스트 `guide`, 더 옛 문자열 배열, 가장 옛 최상위 `diet`/`exercise` 고정 JSON)도 죽지 않고 요약하도록 하위호환을 유지했다. `GUIDE_DATA_VERSION`을 v1.2로 올려 옛 캐시를 자연스럽게 무효화했다. |
| **테스트/검증** | `backend/tests/test_parsing_rules_dose_quantity.py` 신규(공식/약봉투/약식 포맷 각각 실제 mock 텍스트로 검증). `rag/tests/test_rag_chain.py`·`backend/tests/test_chat_router_context.py` 관련 테스트를 새 구조에 맞게 수정. 백엔드 전체 335개, RAG 전체 76개 통과. `npm run build`/`npm run lint` 통과. `uv run ruff check`로 수정 파일 전부 확인(무관한 기존 파일의 E402는 베이스라인). |
| **핵심 패턴** | "필수 아닌 항목"이라도 그 항목을 채우는 액션(시간대 추가 등)이 다른 상태(확인 완료)를 자동으로 건드리면 안 된다 — 액션과 확정은 분리하고 명시적 완료 버튼을 둔다. LLM 응답 스키마를 자유 텍스트에서 구조화된 형태로 바꿀 때는 프롬프트·Pydantic 스키마·저장/직렬화 계층·소비하는 화면(여러 개일 수 있음)·캐시 버전을 한 세트로 보고, 이미 저장된 옛 모양 데이터에 대한 하위호환 폴백을 반드시 남긴다. |

---

| 날짜 | 2026.07.27 |
|---|---|
| **작성자** | 권순현 |
| **이슈** | Duck DNS 도메인(`yakcong.duckdns.org`) + nginx + HTTPS 적용 후, 기존 IP:포트(`http://52.200.250.115:5173`) 접속에서 잘 되던 로그인이 새 도메인(`https://yakcong.duckdns.org`)에서 네트워크 에러/CORS 에러로 실패함 |
| **발생 위치** | EC2 서버의 `backend/.env` (`CORS_ALLOWED_ORIGINS`), `frontend/.env` (`VITE_MONITORING_API_URL`) |
| **원인** | ① `backend/.env`의 `CORS_ALLOWED_ORIGINS`가 예전 IP 기준(`http://52.200.250.115:5173`)으로 남아있어, 새 도메인에서 오는 요청을 CORS가 차단함. ② `frontend/.env`의 `VITE_MONITORING_API_URL`도 예전 IP:포트(`http://52.200.250.115:8000`)를 그대로 가리켜, HTTPS 페이지에서 HTTP로 요청이 나가면서 Mixed Content로 차단되거나 CORS 에러가 발생함 |
| **해결** | 도메인/HTTPS로 배포 방식이 바뀔 때마다 아래 두 값을 함께 갱신한다. EC2에서 실행: |
| **재발 방지** | 배포 환경(IP/포트 → 도메인/HTTPS)이 바뀌면 `CORS_ALLOWED_ORIGINS`·`VITE_MONITORING_API_URL` 두 값을 반드시 함께 갱신한다. 회원가입/로그인 데이터는 DB(Aiven MySQL)에 그대로 남아있으므로 데이터 손실 걱정 없음. `backend/.env`·`frontend/.env`는 `.gitignore`로 git에 올라가지 않는 EC2 인스턴스 로컬 파일이라, 인스턴스를 새로 만들거나 재설정할 경우 이 항목을 참고해 다시 세팅해야 함 |

```bash
sed -i 's|CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://yakcong.duckdns.org|' backend/.env
echo 'VITE_MONITORING_API_URL=https://yakcong.duckdns.org/api' > frontend/.env
docker compose restart backend frontend
```

> ⚠️ 주의: 위 sed/echo 명령어는 파일 전체 값을 덮어씁니다. CORS_ALLOWED_ORIGINS에 이미 다른 도메인(예: 스테이징)이 콤마로 함께 등록되어 있거나, frontend/.env에 다른 변수가 있다면 이 명령어 대신 직접 파일을 열어 해당 줄만 수정하세요.

---

| 날짜 | 2026.07.27 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | (1) 처방전 OCR이 정제/캡슐 외 제형(시럽·주사·패치·점안·점이·나잘스프레이 등)을 인식 못해 그 약이 결과에서 통째로 빠짐 (2) 처방약물 정보의 부작용/보관방법이 실제로는 있는데도 "확인하지 못했어요"로 표시됨 (3) 복약가이드 생활습관 안내에 같은 내용이 중복 기재됨 (4) 1일 투약횟수/총 투약일수에 "필요시"(PRN)가 있으면 값이 그냥 비어서 표시됨 (5) 다른 역할로 가입한 계정으로 초대를 수락하면 이유를 알 수 없이 "수락 처리에 실패했어요"만 뜸 |
| **발생 위치** | `backend/services/parsing_rules.py`, `backend/services/drug_matcher.py`, `backend/services/drug_reference.py`, `backend/routers/ocr_router.py`, `rag/rag/rag_chain.py`, `frontend/src/pages/InviteAccept.tsx` |
| **원인** | (1) `DRUG_NAME_RE`/`DRUG_FORM_RE`/`drug_matcher._DOSAGE_RE`/`drug_reference._FORM_STARTERS` 등 제형 키워드 목록이 정제/캡슐 위주로만 자라있었고, 4개 파일에 각각 따로(하드코딩) 관리되며 서로 다른 부분집합을 갖고 있었다(예: "패치"는 없고 "패취"만, "점안"/"점이"/"환"/"스프레이"는 일부 파일에만 있음) — 이름 인식(`DRUG_NAME_RE`) 자체가 실패하면 그 약이 파싱 결과에서 통째로 사라진다. 시럽/점안액처럼 부피·방울 단위로 복용량을 쓰는 제형은 단위 없는 숫자로 오인되어 약품명의 제형이 그대로 붙는(예: "1방울"→"1액") 부수 증상도 있었다. (2) `_fetch_eyakeun_info`가 약품명 후보(원문→용량표기 제거명) 중 부분일치 히트가 하나라도 있으면 그 자리에서 멈춰서, e약은요 partial-match API 특성상 첫 후보가 정보 부실한 품목에 걸리면 실제로 있는 부작용/보관법도 가져오지 못했다. (3) 생활습관 안내 항목을 파싱하는 `_str_list`에 중복 제거 로직이 아예 없어서, 근거 문서(질병관리청 건강정보, k=3 청크)가 같은 내용을 여러 청크로 나눠 갖고 있으면 LLM이 사실상 같은 문장을 두 번 적어도 그대로 노출됐다. (4) `extract_frequency`/`extract_days`가 prn/hs/ac/pc를 전부 "횟수가 아니라 타이밍/조건"으로 보고 빈 값으로 걸렀는데, hs/ac/pc(취침전/식전/식후)와 달리 "필요시" 자체는 사용자가 값으로 보고 싶어하는 정보였다 — 영문 약어("prn") 인식은 있었지만 처방전에 바로 적히는 한글 "필요시" 텍스트는 인식하지 못했다. (5) `InviteAccept.tsx`의 `catch` 블록이 에러 객체를 아예 안 받고 항상 같은 문자열만 보여줘서, 백엔드가 이미 구체적으로 내려주는 사유(`_link_caregiver_to_invitation`의 relation_type 불일치 체크 — "이 초대는 요양보호사로 가입한 계정만 수락할 수 있어요" 등)를 사용자가 전혀 볼 수 없었다. |
| **해결** | (1) 4개 파일의 제형 키워드 목록을 팀 정리 제형군 표 기준으로 통일·확장(과립/세립/엘릭서/드링크/앰플/바이알/시린지/패치/점안/점이/스프레이/좌제/필름/트로키/껌 등), 1회 복용량 단위도 함께 확장(ml/방울/분무/분사/퍼프/g/단위/매/개/스틱). 나잘스프레이처럼 "1회씩 분사"/"1회 분무"처럼 숫자가 분무/분사가 아니라 "회"에 붙는 표기도 분무 수량으로 인식하도록 `SPRAY_COUNT_RE`를 추가했다. (2) 부작용·보관법이 둘 다 채워진 히트를 찾을 때까지 남은 후보를 계속 시도하고, 끝까지 못 찾으면 첫 히트로 폴백하도록 수정. (3) `_str_list`가 공백 차이만 다른 문장도 같은 것으로 보고, 먼저 나온 순서를 유지하며 제거하도록 수정. (4) `PRN_RE`(한글 "필요시" 또는 영문 "prn")만 hs/ac/pc와 분리해 예외로 두고 그 값 자체를 반환하도록 수정. (5) `describeError()` 헬퍼(`Schedule.tsx`에 이미 있던 패턴 재사용)로 `err.response.data.detail`을 그대로 보여주도록 수정. |
| **테스트/검증** | 신규 `test_parsing_rules_dosage_forms.py`(34개), `test_parsing_rules_prn.py`(9개), `test_drug_matcher.py`/`test_drug_reference.py`/`test_ocr_router_drug_info.py`/`rag/tests/test_rag_chain.py` 추가분 포함 — 백엔드 전체 486개 통과. 프론트엔드 타입체크(`tsc --noEmit`) 통과. |
| **핵심 패턴** | 같은 분류 기준(제형)을 여러 파일에 독립적으로 하드코딩하면, 각자 필요할 때만 늘어나서 서로 다른 부분집합을 갖게 되고 그 차이 자체가 버그가 된다 — 정규식 키워드 목록은 공유 상수로 묶거나, 최소한 "이 목록들은 항상 같이 늘려야 한다"는 주석으로 서로를 가리키게 해야 한다. axios 에러의 `catch` 블록에서 에러 객체를 아예 버리고 고정 문자열만 보여주면, 백엔드가 이미 구체적인 사유를 내려줘도 사용자에게는 "이유 없이 실패"로만 보인다 — `describeError` 패턴처럼 최소한 `detail`은 항상 꺼내 보여줄 것. |

---

| 날짜 | 2026.07.28 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | duckdns 도메인(`yakcong.duckdns.org`)으로 서버를 띄웠을 때 Langfuse로 챗봇 호출이 추적되지 않음 |
| **발생 위치** | `backend/services/langfuse_tracing.py`, EC2 서버의 `backend/.env` (`LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_BASE_URL`) |
| **원인** | Langfuse 연동은 "추적 실패가 챗봇 자체를 절대 깨면 안 된다"는 설계 때문에, 키 누락이든 SDK 오류든 네트워크 문제든 모든 예외를 `except Exception: return None`으로 조용히 삼키고 **로그를 전혀 남기지 않았다** — 그래서 추적이 안 될 때 서버 로그 어디를 봐도 원인을 알 수 없었다. 7/27 도메인 전환 시 EC2 인스턴스를 재설정하면서 그때 문서화된 재발방지 체크리스트(`CORS_ALLOWED_ORIGINS`/`VITE_MONITORING_API_URL`)에는 `LANGFUSE_*` 세 값이 포함돼 있지 않았다 — 인스턴스를 새로 만들거나 `.env`를 재작성하는 과정에서 이 세 값 중 하나가 누락/오타났을 가능성이 가장 유력하다(langfuse 추적은 프론트→백엔드 요청과 무관한 백엔드→Langfuse Cloud 아웃바운드 호출이라, CORS/Mixed-Content 문제와는 무관함). |
| **해결** | `langfuse_tracing.py`의 모든 `except Exception` 블록에 `logger.warning(..., exc_info=True)`를 추가했다(챗봇 동작은 여전히 막지 않음 — 로그만 남김). 키 자체가 없는 경우(`_enabled() == False`)는 흔한 정상 상황(로컬 개발 등)일 수 있어 요청마다 남기지 않고 프로세스당 한 번만 info 레벨로 남긴다. 이 로그로 "키 누락"과 "키는 있는데 SDK/네트워크 문제"를 서버 로그만 보고 구분할 수 있다. **EC2 서버의 실제 `backend/.env`에 `LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_BASE_URL` 세 값이 전부 정확히 들어있는지는 직접 확인이 필요함(로컬 코드만으로는 확인 불가) — 서버 로그에 "Langfuse tracing disabled" 메시지가 있는지 먼저 확인해보면 바로 알 수 있다.** |
| **테스트/검증** | `backend/tests/test_langfuse_tracing.py`에 disabled 상태 1회만 로그하는지, 자격증명 없을 때 예외 없이 None을 반환하는지 검증하는 테스트 3개 추가 — 통과 확인. |
| **재발 방지** | 배포 환경(EC2 인스턴스)이 바뀌면 `CORS_ALLOWED_ORIGINS`/`VITE_MONITORING_API_URL`뿐 아니라 `LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_BASE_URL`도 함께 다시 세팅해야 한다. "실패해도 절대 죽지 않아야 하는" 선택적(optional) 연동이라도, 최소한 로그 한 줄은 남겨야 한다 — 안 그러면 "이게 꺼진 건지, 설정이 잘못된 건지, 코드가 고장난 건지"조차 알 수 없다. |

---

| 날짜 | 2026.07.29 |
|---|---|
| **작성자** | 김영혜 |
| **이슈** | OCR 테스트 처방전에서 실제 약품이 아닌 문구 또는 낮은 신뢰도 보정명이 복약가이드 생성 대상에 들어갈 수 있음. 예: "튼튼정" 같은 OCR 결과가 실제 존재 약품인 "고리튼정"으로 보정되어 환자 화면/RAG 가이드에 사용될 위험 |
| **발생 위치** | `backend/routers/ocr_router.py`, `backend/routers/rag_router.py`, `backend/services/ocr_quality.py` |
| **원인** | `match_drug()`는 오타 보정을 위해 유사도 기반 후보를 반환한다. 이 자체는 필요하지만, OCR 원문과 매칭명이 서로 다른데 점수가 0.85 미만인 경우까지 자동 가이드 생성에 사용하면, 처방전 주변 문구·샘플 문구·낮은 신뢰도 OCR 조각이 그럴듯한 실제 약품명으로 바뀌어 들어갈 수 있었다. 기존 `MATCH_THRESHOLD`는 "사용자에게 후보를 보여줄 수 있는 최소 기준"에 가까웠고, "환자용 복약가이드를 자동 생성해도 되는 기준"으로는 충분히 엄격하지 않았다. 또한 v1.2 캐시에 이미 잘못된 OCR 항목으로 만든 가이드가 남아 있으면 코드 수정 후에도 화면이 같은 결과를 재사용할 수 있었다. |
| **해결** | `ocr_quality.py`를 추가해 OCR 약품명 품질 게이트를 분리했다. 샘플/OCR/가상/병원/환자 등 명백한 비약품 문구는 검토 필요로 표시하고, OCR 원문과 매칭명이 달라졌는데 점수가 0.85 미만이면 자동 가이드 대상에서 제외한다. OCR 저장 시 해당 항목은 `needs_review=True`, 처방전은 `review_required` 상태로 남긴다. RAG 생성 시에도 같은 게이트를 적용해 검토 필요한 약품은 캐시 키·LLM 입력·stub fallback에서 모두 제외한다. 모든 약품이 제외되면 잘못된 가이드를 만들지 않고 "약품명을 먼저 확인"하도록 오류를 반환한다. `GUIDE_DATA_VERSION` 기본값을 v1.3으로 올려 기존 v1.2 캐시를 우회한다. |
| **추가 발견/해결** | 테스트 중 Langfuse observation wrapper가 내부의 정상 예외(`ValueError`)까지 "observation 시작 실패"로 오인해 `RuntimeError: generator didn't stop after throw()`로 바꾸는 문제가 드러났다. `optional_observation()`을 수동 enter/exit 구조로 바꿔 observation 시작 실패만 폴백하고, 라우터 내부 예외는 원래 예외 그대로 전달되도록 수정했다. |
| **테스트/검증** | `backend/tests/test_ocr_quality.py` 신규 추가. `backend/tests/test_rag_cache.py`에 검토 필요한 OCR 항목이 RAG 생성 대상에서 제외되는지, 전부 제외되면 가이드를 만들지 않는지 회귀 테스트 추가. `uv run pytest backend/tests/test_ocr_quality.py backend/tests/test_rag_cache.py backend/tests/test_langfuse_tracing.py backend/tests/test_ocr_router_drug_info.py backend/tests/test_langfuse_scoring.py -q` 결과 47개 통과. `uv run ruff check backend/services/ocr_quality.py backend/services/langfuse_tracing.py backend/routers/rag_router.py backend/tests/test_ocr_quality.py backend/tests/test_rag_cache.py` 통과. |
| **재발 방지** | 의약품 fuzzy matching은 "후보 제안"과 "자동 환자 안내 생성"의 기준을 분리한다. OCR 원문을 다른 약품명으로 바꾸는 경우에는 더 높은 신뢰도 기준을 적용하고, 검토 필요한 OCR 항목은 RAG 입력과 캐시 키에서 모두 제외한다. 캐시 결과 모양이나 생성 대상 정책이 바뀌면 `GUIDE_DATA_VERSION`도 함께 올려 기존 캐시가 새 정책을 가리지 않게 한다. |

---

| 날짜 | 2026.07.30 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 여러 환자를 관리하는 보호자·기관 계정이 알림설정 페이지에 들어가면 기기알림설정 섹션만 나오고 그 아래(복약 알림/돌봄 알림 등)는 안 나오다가, 렉이 걸리듯 잠깐 있다 곧바로 환자관리(`/patients`) 화면으로 강제 이동됨 |
| **발생 위치** | `frontend/src/lib/session.ts`(`useGuardedPatientId`), `frontend/src/pages/Notification.tsx`, `frontend/src/components/PatientContextBanner.tsx`, `frontend/src/components/NavBar.tsx` |
| **원인** | 같은 페이지 로드 시 NavBar의 안 읽음 배지 계산, `PatientContextBanner`, `Notification.tsx` 자신의 `useGuardedPatientId` 호출이 각자 독립적으로 동시에 `GET /monitoring/caregivers/{id}/patients`를 호출한다. 브라우저 네트워크 탭으로 직접 확인한 결과 이 동시 요청 중 일부가 `net::ERR_ABORTED`로 실패했고, `useGuardedPatientId`가 이 실패를 "케어하는 환자 0명"과 동일하게 취급해 `/patients`로 강제 이동시키고 있었다(실제로는 환자가 여러 명 있었음). |
| **시도한 방법 (부분 실패)** | 처음엔 `.catch()` 핸들러에 한 번 더 재시도(retry-once)하는 로직을 추가했으나, 재시도 자체가 총 요청 수를 더 늘려 오히려 `net::ERR_ABORTED` 발생 빈도가 늘어나는 것을 재현 확인 — 근본 원인(동시 호출 자체)을 건드리지 않고 증상만 완화하려 한 접근이 실패함을 인지하고 철회. |
| **해결** | 재시도 로직을 되돌리고, `frontend/src/api/monitoring.ts`의 `getCaregiverPatients()`에 진행 중인 요청을 공유하는 모듈 레벨 캐시(in-flight promise cache)를 추가했다 — 같은 `caregiverId`로 동시에 호출되면 실제 네트워크 요청은 하나만 나가고 나머지 호출자는 그 결과를 공유해서 받는다. 요청이 끝나면 캐시를 비워 다음 호출은 새로 나간다. |
| **테스트/검증** | 브라우저에서 진짜 fresh 탭으로 재확인 — 수정 전엔 같은 `caregivers/2/patients` 요청이 한 번의 페이지 로드에 4~6개씩(StrictMode 이중 렌더 + 여러 호출자) 동시에 나가고 그중 일부가 aborted였는데, 수정 후엔 정확히 1개의 요청만 나가고 200 OK로 정상 처리됨을 `read_network_requests`로 확인. 환자 전환(다른 환자로 배너에서 전환)까지 포함해 전체 플로우 재검증. |
| **핵심 패턴** | 한 페이지에서 여러 독립된 컴포넌트/훅이 같은 데이터를 각자 fetch하는 구조라면, 실패를 재시도로 완화하려 하지 말고 API 레이어에서 요청 자체를 공유(dedupe)하는 게 근본 해결이다 — 재시도는 총 요청량을 늘려 경쟁 상태를 악화시킬 수 있다. |

---

| 날짜 | 2026.07.30 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | (위 항목 디버깅 중 재현 목적으로 테스트 환자를 연결하다가 발견한 별개의 실제 버그) 보호자가 관리하는 환자 중 PII 암호화 키가 안 맞는 계정이 단 하나만 있어도 `GET /monitoring/caregivers/{id}/patients` 전체가 500으로 죽어서, 그 보호자의 정상 환자들까지 전부 안 보임 |
| **발생 위치** | `backend/routers/monitoring_router.py`(`list_patients_of_caregiver`) |
| **원인** | 이전 세션에서 이미 발견됐던 팀 전체 PII 키 불일치 이슈(팀원마다 로컬 `PII_ENCRYPTION_KEY`가 다른 상태에서 만든 테스트 계정들)로 인해, 한 환자(id=77)의 `name_encrypted`/`phone_encrypted`가 현재 설정된 키로 복호화 불가능한 상태였다. `PatientPublic.model_validate(patient, from_attributes=True)`가 이 환자 한 명을 변환하는 시점에 `InvalidToken`을 던졌는데, 이 예외가 목록 순회 루프 전체를 중단시켜서 나머지 정상 환자들까지 응답에서 사라졌다. |
| **해결** | 환자별 `model_validate` 호출을 개별 try/except로 감싸, 복호화 실패한 환자 하나만 `continue`로 건너뛰고 나머지는 정상 응답에 포함시키도록 방어 코드 추가. |
| **테스트/검증** | `backend/tests/test_caregiver_patients_pii_resilience.py` 신규 추가 — `cryptography.fernet.Fernet(Fernet.generate_key())`로 의도적으로 다른 키의 암호문을 주입해 재현, 200 응답에 정상 환자만 포함되는지 검증. 재현에 썼던 임시 연결(caregiver 2 ↔ patient 77)은 검증 직후 삭제해 공유 dev DB를 정리함. |
| **핵심 패턴** | 목록 조회 API에서 항목 하나의 변환 실패가 전체 목록을 죽이지 않도록, 컬렉션 순회 시 항목별 방어 코드(try/except + skip)를 기본으로 고려한다 — 특히 PII 복호화처럼 외부 요인(키 불일치)으로 실패할 수 있는 변환에서는 필수. |

---

| 날짜 | 2026.07.30 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 초대 링크로 새 계정(환자 본인/보호자)을 만들면 "수락 성공" 화면은 뜨는데, 실제로는 로그인이 안 된 상태라 다음 화면부터 API 요청이 전부 401로 실패 — 초대 연결 자체가 "제대로 안 되는" 것처럼 보임 |
| **발생 위치** | `backend/routers/care_router.py`(`accept_invitation`), `frontend/src/pages/InviteAccept.tsx` |
| **원인** | `POST /care/invitations/{token}/accept`가 새 계정을 만드는 두 분기(환자 신규 가입, 보호자 신규 가입) 모두에서 `{patient_id, status}`/`{caregiver_id, patient_id, status}`만 반환하고 `access_token`을 전혀 발급하지 않았다. 프론트는 이 값만 보고 `patient_id`/`caregiver_id`를 localStorage에 저장한 뒤 로그인된 것처럼 다음 화면으로 넘어갔지만, 실제 인증 토큰이 없어 그 다음 요청부터 전부 401 → 강제 로그아웃으로 이어졌다. |
| **해결** | `login()`과 동일한 방식(`_issue_login_response`)으로 신규 계정 생성 두 분기 모두에 `access_token` 발급을 추가했다. 기존 로그인 계정으로 초대를 수락한 경우(`payload.caregiver_id`가 이미 있는 경우)는 이미 유효한 토큰이 있으므로 재발급하지 않는다. 기존 테스트들이 `accept_invitation(token, payload, session[, actor[, patient_actor]])` 위치 인자 관례로 직접 호출하고 있어서, 새로 추가한 `response: Response` 파라미터는 기본값과 함께 맨 뒤에 둬서 기존 호출부를 깨지 않게 했다. 프론트(`InviteAccept.tsx`)는 응답의 `access_token`을 저장하고, 환자 계정 생성 시 이 브라우저에 예전에 남아있을 수 있는 `caregiver_id`도 같이 제거하도록 했다(안 지우면 다른 화면이 보호자로 착각해 엉뚱한 API를 호출). |
| **테스트/검증** | 백엔드 관련 테스트 32개(`-k "invite or invitation"`) 통과, 전체 568개 통과. `tsc --noEmit` 클린. |
| **핵심 패턴** | 신규 계정을 만드는 인증 관련 엔드포인트는 "계정 생성"과 "로그인"을 별개로 취급하기 쉬운데, 계정을 새로 만드는 모든 경로는 `login()`이 하는 것과 동일하게 즉시 사용 가능한 토큰까지 발급해야 한다 — 그렇지 않으면 "성공 화면은 보이는데 실제로는 로그인이 안 된" 상태가 된다. |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 김영혜 (Claude 세션) |
| **이슈** | 로컬 서버에서 팀 자체 제작 OCR 테스트지(`mock_prescription_05.png`, "정검증" 환자, 심바스타틴정/노바스크정/니트로링구알스프레이 3종)를 업로드하면 3번째 약(니트로링구알스프레이)의 용법·횟수·일수가 비어서 나옴. "PR #127에서 국가 표준 처방전 bbox 파서를 신설해 이 부분을 해소하고 테스트도 통과했다"고 했는데도 로컬에서 여전히 재현됨 |
| **발생 위치** | `backend/services/parsing_rules.py`(`DRUG_NAME_RE`, `_parse_table_format`) |
| **이미지 확인** | Claude가 이미지를 직접 읽어 표(No/의약품명/용법/일수) 3행을 확인: ①심바스타틴정20밀리그램/1일 1회 저녁 1정/30일 ②노바스크정5밀리그램/1일 1회 아침 1정/30일 ③니트로링구알스프레이/흉통 시 혀 밑에 1회 분무/필요시. 대각선 "MOCK TEST ONLY" 워터마크가 3번째 행을 가로지르고 있음. |
| **원인 0 — PR #127과의 관계(오해 아님, 서로 다른 범위)** | PR #127의 bbox 파서(`parse_official_table_by_bbox`)는 CLOVA가 `fields`(좌표 포함)를 내려주고 `is_official_prescription_table(fields)`가 참일 때, 즉 **정부 국가 표준 처방전 양식**에서만 동작한다(`prescription_sample_*.png` 10종이 이 양식이라 실제로 정상 동작 — 직접 재현해 확인). 팀이 자체 제작한 "처방전 OCR 테스트지"(`mock_prescription_*.png` 5종)는 이 표준 양식이 아니라서 `is_official_prescription_table`이 거짓으로 판정되고, PR #127 이전부터 있던 구식 `_parse_table_format`(원문 텍스트 기반 정규식) 폴백을 그대로 탄다 — PR #127 테스트가 통과한 것과 이 이미지가 안 되는 것은 애초에 서로 다른 코드 경로라 모순이 아니다. |
| **원인 1 — 진단명의 "질환"이 "환"(알약) 제형으로 오매칭** | `mock_prescription_03.png`(심혈관질환 예방)에서 재현: `DRUG_NAME_RE`가 "정|캡슐|...|환|..." 제형 접미사로 "환"을 인식하는데, 진단명 줄의 "심혈관**질환**"의 마지막 글자도 우연히 "환"이라 "심혈관질"이 가짜 약품명으로 잡혔다. 이 가짜 항목이 실제 약보다 앞선 위치에 끼어들면서, 위치(인덱스) 기반으로 약에 배정되는 용법/일수 배열이 한 칸씩 밀려 마지막 실제 약(크레스토정)이 빈 값이 됐다. |
| **원인 2 — "1회 분무"처럼 숫자 뒤에 한글이 바로 오는 PRN 표기를 인식 못함** | `BARE_FREQ_RE`가 `(?<!\d)(\d+)\s*회(?!\s*[가-힣\)])`라서 "1회" 뒤에 한글(분무)이 바로 오면 매칭을 포기한다(다른 오탐 방지용으로 원래 있던 제외 규칙). 그런데 `_parse_table_format` 자체엔 다른 포맷 파서(`extract_frequency`/`extract_days`)가 가진 "필요시"(PRN) 폴백이 없어서, 니트로링구알스프레이 행은 횟수·일수 모두 빈 값이 됐다. |
| **원인 3 — 일수(총 투약일수) 배열이 "마지막 횟수 매치 이후" 텍스트에서만 찾음** | `_parse_table_format`의 기존 로직은 "약품명 1일 N회 ... N일"이 약마다 한 행씩 반복 출력되는(컬럼이 아니라 행 단위) 이 목업 텍스트에서, 앞쪽 약들의 "30일"이 전부 검색 범위(마지막 횟수 매치 이후) 밖에 있어 아예 못 찾고, 대신 각주/헤더의 엉뚱한 숫자가 위치 순서대로 잘못 배정됐다(mock_prescription_01~05 전체에서 재현 — 실제 "30일"/"60일" 대신 "1일"/"3일" 등으로 저장됨). |
| **해결** | (1) `DRUG_NAME_RE`의 "환" 접미사에 `(?<!질)`(질 바로 뒤는 제외) 부정 전방탐색 추가 — "우황청심환" 같은 실제 "환"제형 약품명은 그대로 인식하면서 "질환"만 제외. (2) `_parse_table_format`에서 위치 기반 횟수가 비어있을 때만, 그 약과 다음 약 사이 구간을 잘라 `extract_frequency`(PRN 인식 포함)로 한 번 더 확인. (3) 총 투약일수를 "이 약 자신의 횟수 매치 뒤 ~ 다음 약 시작 전" 구간에서 직접 "N일" 패턴으로 찾고, 없으면 PRN을, 그래도 없으면 기존 위치 기반 값으로 폴백하도록 재작성. 부수적으로 이 구간 탐색용 bare-number 정규식에 "회"(횟수) 제외 조건이 빠져 있어 "1회"의 "1"이 다시 일수로 오매칭되는 것도 같이 막았다. |
| **검증 방법** | 로컬 서버(`uv run uvicorn --reload`)를 띄운 채 실제 `/ocr/test` 엔드포인트에 `/Users/kim-yunghye/Desktop/ocr_test_prescriptions/` 폴더의 이미지 15장(`mock_prescription_01~05.png` + `prescription_sample_01~10_*.png`) 전부를 업로드해 DB에 저장된 실제 `OcrResult`를 직접 조회하는 방식으로 회귀 검증(단위 테스트 목업이 아니라 실제 CLOVA OCR 응답으로 end-to-end 확인). 수정 전/후 41개 약품 행을 전부 비교. |
| **남은 한계(코드 버그 아님, 참고용)** | (a) `mock_prescription_02.png`의 글루코파지정 "28일"이 CLOVA OCR 자체에서 "8일"로 읽힘(원문에 "28"이 아예 없음) — 이미지 인식 품질 문제라 `parsing_rules.py` 수정 범위 밖. (b) `mock_prescription_05.png`의 니트로링구알스프레이는 "1회 복용량"(dosage)이 여전히 빈 값인데, 원본 문구가 "혀 밑에 1회 분무"라 숫자가 "분무"에 직접 붙어있지 않아(예: "1분무") 애초에 추출할 수량 표기가 없다 — 데이터 자체의 표기 모호성이며, `prescription_sample_08_angina_antiplatelet.png`처럼 "1분무"로 붙여 쓴 같은 약은 정상 인식됨(직접 확인). (c) `_parse_table_format`은 여전히 위치(인덱스) 기반 매핑을 폴백으로 쓰고 있어서, PRN 약이 목록 중간에 있고 그로 인해 횟수 매치 개수가 실제 약 개수보다 적어지면 그 뒤 약들의 배정이 밀릴 여지가 이론적으로 남아있다(이번에 확인한 15장에서는 PRN 약이 전부 마지막 행이라 재현 안 됨) — 근본적으로는 이 표 폴백 파서 자체를 bbox/행 구조 기반으로 재작성하는 게 맞지만 이번엔 범위를 넘어서 다루지 않았다. |
| **테스트/검증** | `backend/tests/` 전체 588 passed, 1 failed(무관한 기존 flaky 테스트 `test_notification_inbox.py::test_lists_notifications_with_drug_name_newest_first` — 날짜 하드코딩 이슈, 이번 수정과 무관, 이전부터 실패해오던 것). `uv run ruff check backend/services/parsing_rules.py` 통과. |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 배포된 사이트에서 이전에 가입한 계정(전화번호 로그인)이 전부 로그인 실패("이메일/전화번호 또는 비밀번호가 올바르지 않습니다") |
| **발생 위치** | EC2 서버의 `backend/.env`(`PII_HASH_SECRET`), `backend/core/security.py`(`hash_phone`), `backend/routers/auth_router.py`(`_find_by_identifiers`) |
| **원인** | 전화번호 로그인은 매 요청마다 `hash_phone(identifier)`로 해시를 계산해 DB의 `phone_hash` 컬럼과 비교하는 방식이다. VAPID 키를 EC2 `.env`에 추가한 뒤 `docker compose down && up -d`로 컨테이너를 완전히 재생성했는데, 그 전까지는 오래 떠 있던 컨테이너가 예전에(맞는 값으로) 메모리에 로드해둔 `PII_HASH_SECRET`을 계속 쓰고 있었고, 재생성 과정에서 지금 `.env` 파일에 있던 다른 값을 새로 읽어들이면서 전화번호 해시가 전부 안 맞게 됐다. |
| **시도한 방법 (진단)** | 사용자가 알려준 전화번호 2개를 로컬 DB에서 직접 조회 — 계정 존재/미잠김 확인(로컬 `PII_HASH_SECRET`으로는 정상 조회됨, 즉 로컬 값은 맞는 값). 이것만으로는 EC2의 실제 값을 알 수 없어, 진단용 테스트 계정을 직접 만들어(`hashed_password`, `phone`, `email` 모두 실제 헬퍼로 설정) 배포된 API에 curl로 직접 로그인 요청 — 전화번호 로그인은 실패, 같은 계정·같은 비밀번호로 이메일 로그인은 성공. 이메일 로그인은 평문 비교(시크릿 무관)라 이 차이가 `PII_HASH_SECRET` 불일치를 확정적으로 증명했다. |
| **해결** | EC2에 SSH로 접속해 `docker compose exec backend env \| grep PII_HASH_SECRET`으로 실제 값을 확인, 로컬 `.env`의 원래 값과 다름을 확인 → `sed -i`로 정정 → `docker compose down && up -d`로 재생성 → 값 반영 확인 → 새 진단 계정으로 전화번호 로그인 재시도해 성공 확인. `PII_ENCRYPTION_KEY`는 다행히 일치해 개인정보 복호화 불가 문제(더 심각한 사고)는 없었음을 별도로 확인. |
| **테스트/검증** | 진단용으로 만든 테스트 계정(로컬 DB, EC2 API 양쪽)은 검증 직후 모두 삭제해 공유 DB에 남기지 않음. |
| **재발 방지** | `PII_HASH_SECRET`/`PII_ENCRYPTION_KEY`/`VAPID_*`처럼 "팀 전체가 항상 같은 값을 써야 하는" 시크릿은, 오래 떠 있던 컨테이너를 재생성하는 작업(`.env` 변경이 목적이 아니어도) 전에 반드시 현재 EC2 값과 로컬/팀 기준값이 일치하는지 먼저 확인한다. `docs/env-var-checklist.md`에 이미 이 값들이 "동기화 필요" 항목으로 명시돼 있었음에도 실제로 어긋난 채로 오래(정확한 시점 불명) 있었다는 것 자체가, 컨테이너를 오래 재생성하지 않고 두면 이런 어긋남이 겉으로 드러나지 않고 누적될 수 있음을 보여준다. |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 위 `PII_HASH_SECRET` 수정을 위해 `docker compose down`까지는 됐는데 `docker compose up -d`가 계속 실패해 사이트가 완전히 다운(`502 Bad Gateway`)된 상태로 이어짐 |
| **발생 위치** | EC2 인스턴스 디스크(`/dev/nvme0n1p1`), Docker 이미지/빌드캐시/볼륨 |
| **원인 1 — 디스크 100% 풀** | `df -h` 확인 결과 루트 파티션이 40G 중 40G(99%) 사용 중. `docker system df`로 보니 이미지 4.01GB + 로컬 볼륨 21.18GB(15개, 전부 미사용) + 빌드 캐시 11.86GB, 전부 100% 회수 가능한 상태였다. `docker-compose.yml`이 매 배포마다 `up -d --build`로 새 이미지를 만드는데, CI 배포 스크립트에 정리 단계가 전혀 없어서 예전 이미지·빌드캐시·(컨테이너 재생성마다 새로 생기는) 익명 볼륨이 한 번도 안 지워지고 계속 누적된 것이 원인이었다. |
| **원인 2 — 컨테이너 이름 충돌** | 디스크 정리(`docker system prune -af --volumes`, 36.8GB 회수) 후 재시도했으나, 이전 실패 시도가 남겨둔 컨테이너(`ah_04_02-backend-1`)가 이름을 이미 점유하고 있어 `Error response from daemon: Conflict` 발생. |
| **원인 3 — overlay2 xattrs 오류** | 이름 충돌 컨테이너를 `docker rm -f`로 제거하고 재시도했으나, 이번엔 `failed to copy xattrs: ... no such file or directory`(overlay2 그래프 드라이버 레이어 손상)로 재차 실패 — 앞서 디스크 풀 상태에서 파일 복사가 중간에 끊긴 여파로 보임. |
| **해결** | 컨테이너 이름 충돌은 `docker rm -f <container_id>`로 제거. overlay2 오류는 곧바로 재시도(`docker compose up -d`)한 것만으로 해결됨 — 재시도 시점엔 문제가 재현되지 않아, 직전의 불완전한 상태가 남긴 일시적 현상이었던 것으로 보임(도커 데몬 재시작까지는 필요 없었음). |
| **테스트/검증** | `docker compose ps`로 `backend`/`frontend` 컨테이너가 둘 다 `Up` 상태인지 확인, 실제 배포 도메인에 브라우저로 접속해 `502` 대신 로그인 페이지가 정상 렌더링되는지 확인. |
| **재발 방지** | CI 배포 스크립트(`.github/workflows/ci.yml`)의 `docker compose up -d --build` 다음에 `docker image prune -af`를 추가해 배포마다 자동으로 dangling 이미지를 정리하도록 함(PR #137). |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 보호자와 기관이 같은 환자에 동시에 연결돼 있을 때, 처방전 수정을 한쪽(예: 기관)이 요청하면 환자에게만 알림이 가고 다른 쪽(보호자)은 화면을 직접 열어봐야만 요청이 있었다는 걸 알 수 있음 |
| **발생 위치** | `backend/routers/records_router.py`(`request_correction`), `frontend/src/pages/Notifications.tsx` |
| **원인** | `request_correction`이 `RecordCorrectionNotice(recipient_role="patient", ...)` 하나만 생성하고, 같은 환자에 연결된 다른 caregiver에게는 별도 notice를 만들지 않았다. 반대 방향(환자가 수정을 다 끝내면 연결된 caregiver 전원에게 알림)은 이미 구현돼 있어서 비대칭이었다. |
| **해결** | 요청을 보낸 caregiver 본인을 제외하고, 같은 환자에 연결된(`status != "revoked"`) 나머지 caregiver 전원에게 `RecordCorrectionNotice(event="correction_requested")` + (기기별 알림이 켜져있으면) 푸시를 추가로 보내도록 수정. 프론트 `Notifications.tsx`의 `correction_requested` 클릭 시 이동 경로도 같이 수정 — 지금까지 이 이벤트는 무조건 환자용 수정 화면(`/records/{id}/review?mode=correction`)으로 보냈는데, 보호자·기관이 받는 경우엔 직접 고치는 게 아니라 지켜보는 입장이라 다른 caregiver 알림과 동일하게 읽기 전용 가이드 화면(`/records/{id}/guide`)으로 보내도록 분기 추가. |
| **테스트/검증** | `test_record_review_flow.py`에 다중 caregiver 시나리오 회귀 테스트 추가(요청자 제외 나머지에게만 알림, 요청자 본인에게는 안 감) — 파일 전체 28개 통과. 로컬 dev 서버에서 실제로 기관 계정→수정요청 API 호출 후 같은 환자에 연결된 다른 보호자 계정으로 로그인해 알림함에서 "수정 요청" 알림 확인, 클릭 시 `/records/{id}/guide`로 정확히 이동하는 것까지 브라우저로 검증(PR #134). |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | 복약가이드/생활습관 화면이 로컬·배포 환경 양쪽에서 간헐적으로 나왔다가 안 나왔다가 함(사용자 제보: "로컬에서도 나왔다가 안 나왔다가, 배포에선 로컬보다 더 자주 안 나옴") |
| **발생 위치** | `frontend/src/api/records.ts`(`getRecord`), `frontend/src/api/monitoringClient.ts` |
| **가설 검토(제보자 제시)** | ① 비동기 처리에 wait 누락 — DB write가 덜 끝난 채로 read할 수 있음 ② wait을 넣어도 안 되면 DB 자체 문제(가이드가 실제로 저장 안 됐을 가능성) ③ 비동기 통신 처리가 애초에 없거나, 엉뚱한 레코드를 불러오는 것 아닌지 |
| **1차 조사(코드 트레이싱)** | `records_router.py`의 가이드 생성 흐름은 실제로 완전히 동기적이며 `run_rag`가 정확히 `await`되고, HTTP 응답이 나가기 전에 `GuideResult`가 확실히 commit+refresh된다 — 가설 ①(await 누락)은 근거 없음. `GuideCache` 키도 `record_id` 기준으로 정확히 스코프돼 있어 다른 환자/기록의 캐시가 섞이는 경로는 못 찾음 — 가설 ③(엉뚱한 거 불러옴)도 근거 없음. 코드 리딩만으로는 `rag/rag/rag_chain.py`의 생활습관 가이드 생성 LLM 호출에 try/except가 전혀 없다는 게 유력한 원인 후보로 보였음(가설 ②와 부합하는 듯 보임). |
| **2차 조사(공유 DB 직접 조회로 검증)** | `status IN ('review_required', 'failed')`인 기록 108건을 전부 조회. `review_required` 105건은 전부 연결된 `OcrResult.user_confirmed=False`(confirm을 시도하다 크래시난 흔적 없음, 그냥 미완료 테스트 기록). `failed` 3건은 전부 `failure_reason='알 수 없는 provider: real'`(환경변수 설정 실수, 07-28 09:10~09:11 1분 사이에만 발생하고 재발 없음). **즉 "가이드 생성이 실패해서 유실됐다"는 흔적이 DB에 전혀 없어, 1차 조사에서 유력해 보였던 LLM 예외처리 누락 가설은 실제 관찰된 증상의 원인이 아님이 확인됨.** |
| **원인** | `getRecord()`(MedGuide.tsx가 처방전+가이드+생활습관을 조회할 때 씀)만 공용 axios 클라이언트의 기본 10초 타임아웃(`monitoringClient.ts`)을 그대로 쓰고 있었다. `createRecord`/`getRecordImageBlobUrl` 등 다른 무거운 요청들은 이미 30~120초로 늘려놨는데(2026-07-09/07-28 항목 참고 — 이 코드베이스에 이미 한 번 있었던 정확히 같은 패턴의 버그), `getRecord`만 그때 빠뜨린 것으로 보인다. 가이드는 DB에 정상 저장돼 있는데, 화면에서 불러오는 요청만 로컬(loopback)에서는 거의 안 걸리고 배포 환경(브라우저→nginx→백엔드, DB도 원격 Aiven)에서만 가끔 10초를 넘겨 실패한 것으로 결론. |
| **해결** | `getRecord()`에 `timeout: 120000` 추가(다른 RAG 관련 요청과 동일 값). |
| **테스트/검증** | `tsc --noEmit` 클린. 로컬 dev 서버에서 실제 완료된 처방전 기록으로 `/records/:id/guide` 페이지 재확인 — 복약 가이드/복약 지도/생활습관 탭 전환과 데이터 로딩 정상 동작(200 응답, 콘텐츠 정상 렌더링) 확인(PR #135). |
| **핵심 패턴** | "간헐적으로 보였다 안 보였다"하는 증상을 마주하면, 코드 리딩만으로 짚이는 가설(특히 "예외처리가 없어 보인다" 류)을 바로 원인으로 단정하지 말고, 실제 DB/로그에서 그 가설이 예측하는 흔적(이 경우 `status=failed`나 크래시로 멈춘 레코드)이 정말 존재하는지 먼저 확인한다. 코드상 진짜 취약점이라도 실제 관찰된 증상의 원인이 아닐 수 있다. |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | (위 항목 조사 중 발견한 별개의 잠재적 취약점, 실제 발생 사례는 DB상 확인 안 됨) 생활습관 안내 생성 시 진단명 하나의 LLM 호출만 실패해도 예외가 그대로 전체 요청을 실패시켜, 이미 정상 생성된 약별 가이드까지 전부 날아감 |
| **발생 위치** | `rag/rag/rag_chain.py`(`generate_guides_from_medications`, `generate_lifestyle_guide_for_diagnosis`) |
| **원인** | 같은 함수의 약별 가이드 루프는 항목 하나가 실패해도 나머지는 정상 반환하도록 이미 `try/except`로 격리돼 있는데(`review_flags=["generation_error"]`), 바로 아래 진단명 기준 생활습관 안내를 생성하는 부분(`[generate_lifestyle_guide_for_diagnosis(d) for d in seen_diagnoses]`)은 이 보호가 전혀 없이 리스트 컴프리헨션으로 직접 호출되고 있었다. |
| **해결** | 리스트 컴프리헨션을 for 루프 + try/except로 바꿔 약별 가이드와 동일한 실패 격리 패턴을 적용. 실패한 진단명은 `review_required=True`, `review_reason`에 예외 메시지, `review_flags=["generation_error"]`인 안전한 `LifestyleGuideResult`로 대체하고 나머지 진단명 처리는 계속하도록 함. `rag/rag/schemas.py`의 `review_flags` 문서화 목록에도 `generation_error`를 추가(기존엔 약별 가이드 쪽에만 쓰이고 문서엔 없었음). |
| **테스트/검증** | `rag/tests/test_rag_chain.py`에 회귀 테스트 추가 — 진단명 2개 중 하나만 실패시켜, 실패한 진단명만 격리되고 다른 진단명 + 약별 가이드는 영향받지 않는지 검증. `rag/tests/` 전체 84개, `backend/tests/` 전체(593 passed, 1개는 기존 날짜 플레이키 테스트로 무관) 통과(PR #136). |
| **핵심 패턴** | 여러 항목을 순회하며 외부 API(LLM 등)를 호출하는 코드에서 "실패 격리"를 적용할 땐, 같은 함수 안에 유사한 성격의 루프가 여러 개 있는지 확인한다 — 하나만 보호하고 옆의 비슷한 루프를 빠뜨리기 쉽다. |

---

| 날짜 | 2026.07.31 |
|---|---|
| **작성자** | 박소정 |
| **이슈** | (2026.07.31 EC2 디스크 100% 풀 장애의 재발 방지 조치) CI 배포 파이프라인에 이미지/캐시 정리 단계가 없어 매 배포마다 디스크 사용량이 계속 누적됨 |
| **발생 위치** | `.github/workflows/ci.yml` |
| **원인** | 배포 스텝이 `docker compose -f docker-compose.yml up -d --build`만 실행하고 끝나, 매번 새로 만들어지는 이미지 레이어·빌드 캐시·컨테이너 재생성마다 새로 생기는 익명 볼륨이 전혀 정리되지 않았다. |
| **해결** | `docker compose up -d --build` 다음 줄에 `docker image prune -af` 추가 — 지금 실행 중인 컨테이너가 참조하는 이미지는 대상에서 제외되는 안전한 범위만 자동 정리. |
| **테스트/검증** | 실제 장애 당시 수동으로 동일한 정리(`docker system prune -af --volumes`)를 적용해 디스크 99%→7%로 복구, 이후 컨테이너 정상 기동을 이미 확인함 — 이 PR은 그 정리를 배포 파이프라인에 자동으로 넣는 것(PR #137). |
| **재발 방지** | 이미지 정리 외에 로컬 볼륨(익명 볼륨) 누적도 관찰됐으나(21GB), `docker-compose.yml`의 바인드마운트 제외 용도 익명 볼륨은 컨테이너 재생성마다 매번 새로 생기는 구조라 근본적으로는 named volume 전환 등 더 큰 변경이 필요 — 이번엔 가장 빠르고 안전한 이미지 정리만 우선 반영하고, 볼륨 누적이 다시 문제가 되면 별도로 재검토하기로 함. |
| **핵심 패턴** | 정규식 기반 "이 접미사가 나오면 약품명"류 판별은 그 접미사가 다른 흔한 한국어 단어의 끝 글자와 겹칠 수 있다("환"↔"질환") — 겹치는 게 확인되면 그 특정 단어만 부정 전방탐색으로 제외하는 게 전체 목록을 다시 설계하는 것보다 안전하다. "OCR이 컬럼을 그룹으로 출력한다"고 가정하고 짠 위치(인덱스) 기반 파서는, 실제로는 행 단위로 반복 출력되는 텍스트가 들어오면 뒤쪽 항목일수록 배정이 어긋난다 — 여러 항목을 다루는 파서는 "전체에서 한 번에 배열을 뽑아 인덱스로 매핑"하는 대신 "각 항목 자신의 위치 구간 안에서 값을 찾는" 방식이 더 안전하다(단, 진짜 컬럼-그룹 포맷을 위해 기존 방식도 폴백으로는 남겨둠). PR이 "해소했다"고 보고한 범위가 지금 겪는 문제와 코드 경로 자체가 다를 수 있으니, 재현이 안 되면 먼저 "같은 함수/같은 조건을 타는 게 맞는지"부터 확인할 것. |

---

## 과거 EasyOCR 실험 기록 (참고용, 현재 미사용 — 현재는 CLOVA OCR 사용)

> 아래 항목은 초기 프로토타입 단계에서 EasyOCR을 직접 사용하던 시기의 기록이다. 현재 OCR 처리는 `backend/routers/ocr_router.py`의 CLOVA OCR 인터페이스(`ocr_interface.py`)로 전환됐으며, EasyOCR 의존성은 제거됐다.

---

| 날짜 | (EasyOCR 실험 초기) |
|---|---|
| **작성자** | 권순현 |
| **이슈** | 한글이 포함된 처방전 이미지를 OCR에 넣었을 때 한글 부분이 전부 빈 결과로 반환됨 |
| **발생 위치** | EasyOCR `Reader` 초기화 |
| **원인** | EasyOCR은 Reader 초기화 시 선언한 언어 코드에 해당하는 모델만 로드한다. `[“en”]`만 선언하면 한국어 모델 자체를 불러오지 않는다. |
| **해결** | `reader = easyocr.Reader([“en”, “ko”])` |
| **현재 상태** | CLOVA OCR 전환으로 EasyOCR 미사용. 참고용으로만 보존. |

---

| 날짜 | (EasyOCR 실험 초기) |
|---|---|
| **작성자** | 권순현 |
| **이슈** | 한글이 포함된 샘플 이미지를 PIL로 생성했을 때 한글 부분이 깨지거나 빈 박스로 출력됨 |
| **발생 위치** | PIL(Pillow) 이미지 생성 코드 |
| **원인** | PIL의 기본 폰트(`ImageFont.load_default()`)는 ASCII 문자만 지원한다. 한글 렌더링에는 시스템에 설치된 한글 폰트 파일 경로를 직접 지정해야 한다. |
| **해결** | `font = ImageFont.truetype(“/System/Library/Fonts/AppleSDGothicNeo.ttc”, size=24)` (macOS 기준) |
| **현재 상태** | EasyOCR 테스트용 이미지 생성 코드였으므로 현재 미사용. |

---

| 날짜 | (EasyOCR 실험 초기) |
|---|---|
| **작성자** | 권순현 |
| **이슈** | “캡슐500mg” → “캡쑬50Omg” 처럼 약품명과 용량이 동시에 오인식됨 |
| **발생 위치** | EasyOCR raw 결과 후처리 |
| **원인** | EasyOCR이 시각적으로 유사한 문자를 혼동한다. 의약품 도메인에서는 한글 받침 혼동(“캡슐”→”캡쑬”)이나 숫자·문자 혼동(`0`→`O`)이 처방 용량이나 약품명 오인식으로 직결된다. |
| **해결** | 2단계 후처리: ① 자주 혼동되는 패턴 사전 치환(`CHAR_CORRECTIONS`) → ② 의약품 도메인 사전과 유사도 비교(`difflib.get_close_matches`) |
| **현재 상태** | CLOVA OCR 전환으로 후처리 파이프라인 불필요. 참고용으로만 보존. |
