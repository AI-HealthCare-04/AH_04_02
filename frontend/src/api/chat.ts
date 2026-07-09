import { monitoringClient } from "./monitoringClient";

export interface ChatQuestion {
  id: string;
  text: string;
}

export interface ChatAnswer {
  question: string;
  answer: string;
  created_at: string;
  // [7/9] 백엔드 응답 키는 answer_source — source로 잘못 선언돼 있어서 항상 undefined였음
  answer_source?: string;
}

export async function getChatQuestions() {
  const { data } = await monitoringClient.get<ChatQuestion[]>("/chat/questions");
  return data;
}

export async function askChat(patientId: number, questionId: string) {
  // [7/9] CHAT_PROVIDER=real이면 이 호출이 실제 OpenAI 응답을 기다리는 동기 호출이라
  // monitoringClient의 기본 10초 타임아웃을 넘기기 쉬움 — 이 요청만 넉넉하게 늘림
  // (10초 초과 시 백엔드는 끝까지 처리해서 200을 돌려줘도 프론트가 먼저 포기하고
  // "답변을 가져오지 못했어요" 에러로 보여서, 실제로는 "챗봇이 응답을 못한다"처럼 보임).
  const { data } = await monitoringClient.post<ChatAnswer>(
    "/chat/ask",
    { patient_id: patientId, question_id: questionId },
    { timeout: 30000 },
  );
  return data;
}
