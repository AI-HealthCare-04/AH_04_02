
---

| 날짜 | 2026.07.02 |
|---|---|
| **이슈** | 토글 버튼 클릭 후 검은 테두리(outline)가 사라지지 않고 잔류 |
| **발생 위치** | `Check.tsx` 자가진단 버튼, `Dashboard.tsx` 복약 상태 버튼, `Connect.tsx` 관계 유형 버튼 |
| **원인** | React 인라인 스타일에서 `border` 단축속성과 `borderColor` 개별속성을 **동시에 사용**하면, 상태 전환 시 React가 이전 `border` 값을 제거하면서 브라우저 기본 `outline`(2.85px)이 노출됨. 크롬 DevTools Computed 탭에서 `outline-style: none` 이지만 `outline-width: 2.85714px` 가 남아있는 것으로 확인. 추가로 콘솔에 `"Removing a style property during rerender (borderColor)"` 경고 발생 |
| **시도한 방법 (실패)** | ① `index.css`에 `button:focus { outline: none }` 추가 → 효과 없음 ② `!important` 추가 → 효과 없음 ③ `onMouseDown={(e) => e.preventDefault()}` 단독 적용 → 효과 없음 ④ `borderWidth/borderStyle/borderColor` 개별속성으로 분리 → 오히려 테두리 두꺼워짐 |
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
