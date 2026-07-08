import { monitoringClient } from "./monitoringClient";

export interface ChatQuestion {
  id: string;
  text: string;
}

export interface ChatAnswer {
  question: string;
  answer: string;
  created_at: string;
  source?: string; // RAG 연동 전까지는 항상 undefined — 화면에서 있을 때만 표시
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
