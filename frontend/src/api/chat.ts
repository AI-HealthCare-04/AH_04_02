import { monitoringClient } from "./monitoringClient";

export interface ChatQuestion {
  id: string;
  text: string;
}

export interface ChatAnswer {
  question: string;
  answer: string;
  created_at: string;
  answer_source?: string; // "llm" | "preset" | "unsupported" | "*_fallback (...)" 등 — 화면 하단에 작게 표시
}

export async function getChatQuestions() {
  const { data } = await monitoringClient.get<ChatQuestion[]>("/chat/questions");
  return data;
}

export async function askChat(patientId: number, questionId: string) {
  const { data } = await monitoringClient.post<ChatAnswer>("/chat/ask", {
    patient_id: patientId,
    question_id: questionId,
  });
  return data;
}

/** [7/10 추가] 고정 질문 3개 외의 자유 텍스트 질문 — LLM 호출이라 기본 10초보다 넉넉하게 잡음. */
export async function askChatFreeform(patientId: number, question: string) {
  const { data } = await monitoringClient.post<ChatAnswer>(
    "/chat/ask",
    { patient_id: patientId, question },
    { timeout: 60000 }
  );
  return data;
}
