
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
