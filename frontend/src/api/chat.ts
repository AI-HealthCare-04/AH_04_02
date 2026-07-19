import { monitoringClient } from "./monitoringClient";

export interface ChatQuestion {
  id: string;
  text: string;
}

export async function getChatQuestions(patientId: number) {
  const { data } = await monitoringClient.get<ChatQuestion[]>("/chat/questions", {
    params: { patient_id: patientId },
  });
  return data;
}

// [2026-07-20 추가, REQ-021] POST /chat/ask/stream(SSE)을 씀 — monitoringClient(axios)는
// 브라우저에서 스트리밍 응답 바디를 토큰 단위로 읽기 어려워서(XHR 기반), 이 호출만 axios
// 대신 fetch + ReadableStream을 직접 쓴다. baseURL/토큰 첨부/401 처리는 monitoringClient.ts와
// 최대한 동일하게 맞췄다(그 인터셉터는 axios 인스턴스 전용이라 fetch엔 자동 적용 안 됨).
const CHAT_STREAM_BASE_URL = import.meta.env.VITE_MONITORING_API_URL || "http://localhost:8000";

export interface ChatStreamDoneEvent {
  answer_source: string;
  created_at: string;
  partial: boolean;
}

export interface ChatStreamCallbacks {
  onDelta: (deltaText: string) => void;
  onDone: (event: ChatStreamDoneEvent) => void;
  onError: (error: unknown) => void;
}

async function streamChatAsk(
  body: { patient_id: number; question_id?: string; question?: string },
  { onDelta, onDone, onError }: ChatStreamCallbacks
): Promise<void> {
  const token = localStorage.getItem("access_token");
  let response: Response;
  try {
    response = await fetch(`${CHAT_STREAM_BASE_URL}/chat/ask/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    onError(err);
    return;
  }

  if (response.status === 401) {
    // monitoringClient.ts의 401 인터셉터와 동일한 처리 — fetch는 이 인터셉터를 안 타므로 직접 반복.
    localStorage.removeItem("access_token");
    localStorage.removeItem("caregiver_id");
    if (window.location.pathname !== "/login") window.location.href = "/login";
    return;
  }
  if (!response.ok || !response.body) {
    onError(new Error(`chat stream 요청 실패: ${response.status}`));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? ""; // 마지막 조각은 아직 끝나지 않은 이벤트일 수 있으니 버퍼에 남김
      for (const raw of events) {
        const line = raw.trim();
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice("data: ".length));
        if (payload.done) {
          onDone(payload as ChatStreamDoneEvent);
        } else if (typeof payload.delta === "string") {
          onDelta(payload.delta);
        }
      }
    }
  } catch (err) {
    onError(err);
  }
}

export function askChatStream(patientId: number, questionId: string, callbacks: ChatStreamCallbacks) {
  return streamChatAsk({ patient_id: patientId, question_id: questionId }, callbacks);
}

/** [7/10 추가, 2026-07-20 스트리밍 전환] 고정 질문 3개 외의 자유 텍스트 질문. */
export function askChatFreeformStream(patientId: number, question: string, callbacks: ChatStreamCallbacks) {
  return streamChatAsk({ patient_id: patientId, question }, callbacks);
}
