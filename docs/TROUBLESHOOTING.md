
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
