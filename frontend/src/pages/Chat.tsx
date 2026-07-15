import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import NavBar from "../components/NavBar";
import { askChat, askChatFreeform, getChatQuestions, type ChatQuestion } from "../api/chat";
import { getNotificationSettings } from "../api/care";
import { getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

type Message = { role: "user" | "bot"; text: string; source?: string };
type ChatContext = { drugName?: string; diagnosis?: string };

const DEFAULT_CHATBOT_NAME = "약콩이";
const DEFAULT_GREETING = "안녕하세요 😊 복약 안내 결과에 대해 궁금한 점을 물어보세요.";

// 한글 받침 유무에 따라 "을"/"를" 조사를 골라줍니다 (예: 아스피린 → 을, 로자탄 → 을, 노바스크 → 를).
function withObjectParticle(word: string): string {
  const lastChar = word.charCodeAt(word.length - 1);
  if (lastChar >= 0xac00 && lastChar <= 0xd7a3) {
    const hasBatchim = (lastChar - 0xac00) % 28 !== 0;
    return `${word}${hasBatchim ? "을" : "를"}`;
  }
  return `${word}를`;
}

// 백엔드가 내려주는 answer_source는 개발용 원문 그대로임("llm"/"preset"/"unsupported"/
// "preset_fallback (TimeoutError)" 등) — 사용자에게는 "출처: ..." 형태의 한글 안내로 바꿔 보여준다.
function formatAnswerSource(source: string): string {
  // 백엔드가 "llm (gpt-4o-mini)"처럼 모델명을 괄호로 붙여 보낸다 — 그대로 옮겨 붙인다.
  if (source.startsWith("llm")) return `출처: AI 실시간 답변${source.slice(3)}`;
  if (source === "preset") return "출처: 자주 묻는 질문 답변";
  if (source.includes("fallback")) return "출처: 사전 등록된 답변";
  return "출처: 일반 안내";
}

function buildGreeting(context: ChatContext | null): string {
  if (context?.drugName) {
    return `${withObjectParticle(context.drugName)} 드시고 계시군요. 관련해서 무엇을 도와드릴까요?`;
  }
  if (context?.diagnosis) {
    return `${context.diagnosis} 관련 복약 가이드를 보고 계시군요. 무엇을 도와드릴까요?`;
  }
  return DEFAULT_GREETING;
}

// [7/10] 입력한 문장이 고정 질문과 정확히 같으면 그 질문(캐시된 프리셋 답변 폴백 포함)으로
// 묻고, 아니면 자유 텍스트 그대로 /chat/ask에 보내 GPT가 환자 컨텍스트 기반으로 답한다.
export default function Chat() {
  const patientId = getCurrentPatientId();
  const location = useLocation();
  const context = (location.state as ChatContext | null) ?? null;
  const [questions, setQuestions] = useState<ChatQuestion[]>([]);
  const [chatbotName, setChatbotName] = useState(DEFAULT_CHATBOT_NAME);
  const [messages, setMessages] = useState<Message[]>(() => [
    { role: "bot", text: buildGreeting(context) },
  ]);
  const [loading, setLoading] = useState(false);
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatQuestions().then(setQuestions).catch(() => setQuestions([]));
    getNotificationSettings(patientId)
      .then((s) => setChatbotName(s.chatbot_name || DEFAULT_CHATBOT_NAME))
      .catch(() => setChatbotName(DEFAULT_CHATBOT_NAME));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // scrollIntoView는 페이지 전체 스크롤 위치까지 건드릴 수 있어서, 메시지 목록 div의
  // scrollTop만 직접 조작해 채팅창 내부만 스크롤되게 합니다.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const askPreset = async (q: ChatQuestion) => {
    if (loading) return;
    setMessages((prev) => [...prev, { role: "user", text: q.text }]);
    setLoading(true);
    try {
      const res = await askChat(patientId, q.id);
      setMessages((prev) => [...prev, { role: "bot", text: res.answer, source: res.answer_source }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "죄송해요, 답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const match = questions.find((q) => q.text === text);
    if (match) {
      askPreset(match);
      return;
    }
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    try {
      const res = await askChatFreeform(patientId, text);
      setMessages((prev) => [...prev, { role: "bot", text: res.answer, source: res.answer_source }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "죄송해요, 답변을 가져오지 못했어요. 잠시 후 다시 시도해 주세요." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl lg:max-w-4xl mx-auto w-full px-4 py-6 flex flex-col flex-1 min-h-0">
        <div className="mb-5 shrink-0">
          <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>AI 복약 상담</p>
          <h1 className="text-[24px] font-black" style={{ color: C.dark }}>{chatbotName}</h1>
          <p className="text-[14px]" style={{ color: C.muted }}>복약 안내 결과에 대해 궁금한 점을 물어보세요</p>
        </div>

        <div className="rounded-3xl mb-4 flex flex-col overflow-hidden flex-1 min-h-0" style={{ background: C.white, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
          <div ref={listRef} className="flex-1 min-h-0 overflow-y-auto space-y-5 p-5">
            {messages.map((m, i) => (
              <div key={i} className={`flex items-end gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                {m.role === "bot" && (
                  <div className="flex flex-col items-center gap-0.5 shrink-0">
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-[18px]"
                      style={{ background: `${C.terracotta}12` }}
                    >
                      💊
                    </div>
                    <span className="text-[9px] font-bold" style={{ color: C.muted }}>{chatbotName}</span>
                  </div>
                )}
                <div className="max-w-[80%]">
                  <div
                    className="px-4 py-3.5 text-[15px] leading-relaxed"
                    style={{
                      background: m.role === "user" ? C.terracotta : C.bubbleBg,
                      color: m.role === "user" ? C.white : C.dark,
                      borderRadius: m.role === "user" ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
                    }}
                  >
                    {m.text}
                  </div>
                  {m.source && (
                    <p className="text-[11px] mt-1.5 px-1" style={{ color: C.muted }}>{formatAnswerSource(m.source)}</p>
                  )}
                </div>
              </div>
            ))}
            {loading && <p className="text-[13px] pl-12" style={{ color: C.muted }}>답변을 준비하고 있어요...</p>}
          </div>

          {questions.length > 0 && (
            <div className="shrink-0 flex gap-2 flex-wrap px-5 py-3 border-t" style={{ borderColor: "rgba(30,26,23,0.07)" }}>
              {questions.map((q) => (
                <button
                  key={q.id}
                  onClick={() => askPreset(q)}
                  disabled={loading}
                  className="px-3.5 py-2 rounded-full text-[13px] font-bold border transition-all hover:opacity-80 disabled:opacity-50"
                  style={{ borderColor: `${C.terracotta}50`, color: C.terracotta, background: `${C.terracotta}06` }}
                >
                  {q.text}
                </button>
              ))}
            </div>
          )}

          <div className="shrink-0 flex gap-2 px-4 py-4 border-t" style={{ borderColor: "rgba(30,26,23,0.07)" }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              disabled={loading}
              placeholder="궁금한 점을 입력해주세요"
              className="flex-1 px-5 py-3.5 rounded-full text-[15px] outline-none disabled:opacity-60"
              style={{ background: C.ivory, border: "1.5px solid rgba(30,26,23,0.10)", color: C.dark }}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="px-7 py-3.5 rounded-full text-white font-bold text-[15px] shrink-0 transition-all hover:opacity-88 disabled:opacity-50"
              style={{ background: C.terracotta }}
            >
              전송
            </button>
          </div>
        </div>

        <div className="shrink-0 rounded-2xl px-5 py-4 flex items-start gap-2.5" style={{ background: C.warningBg, border: `1px solid ${C.warningBorder}` }}>
          <span className="text-[15px] shrink-0">⚠️</span>
          <span className="text-[13px] leading-relaxed" style={{ color: C.warningText }}>
            챗봇 답변은 AI가 생성한 참고용 정보입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
          </span>
        </div>
      </main>
    </div>
  );
}
