import { useEffect, useRef, useState } from "react";
import NavBar from "../components/NavBar";
import { askChat, getChatQuestions, type ChatQuestion } from "../api/chat";
import { getCurrentPatientId } from "../lib/session";

type Message = { role: "user" | "bot"; text: string };

const INITIAL: Message[] = [
  { role: "bot", text: "안녕하세요 😊 아래 질문 중 하나를 눌러 물어보세요." },
];

export default function Chat() {
  const patientId = getCurrentPatientId();
  const [questions, setQuestions] = useState<ChatQuestion[]>([]);
  const [messages, setMessages] = useState<Message[]>(INITIAL);
  const [loading, setLoading] = useState(false);
  const [askedIds, setAskedIds] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatQuestions().then(setQuestions).catch(() => setQuestions([]));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleAsk = async (q: ChatQuestion) => {
    if (loading) return;
    setMessages((prev) => [...prev, { role: "user", text: q.text }]);
    setLoading(true);
    try {
      const res = await askChat(patientId, q.id);
      setMessages((prev) => [...prev, { role: "bot", text: res.answer }]);
      setAskedIds((prev) => new Set([...prev, q.id]));
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
    <div className="min-h-screen flex flex-col bg-[#FAF6F1]">
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto w-full px-4 py-6 flex flex-col flex-1">
        <div className="mb-5">
          <p className="text-[13px] font-bold text-[#C1653D] mb-1">복약 상담 챗봇</p>
          <h1 className="text-[22px] font-black text-[#2A2A2A]">궁금한 걸 눌러서 물어보세요</h1>
        </div>

        <div className="bg-white rounded-3xl flex flex-col overflow-hidden shadow-sm flex-1">
          <div className="flex-1 overflow-y-auto space-y-5 p-5" style={{ minHeight: 280, maxHeight: 420 }}>
            {messages.map((m, i) => (
              <div key={i} className={`flex items-end gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                {m.role === "bot" && (
                  <div className="w-9 h-9 rounded-full shrink-0 flex items-center justify-center text-[16px] bg-[#C1653D]/10">
                    💊
                  </div>
                )}
                <div
                  className="max-w-[80%] px-4 py-3.5 text-[15px] leading-relaxed"
                  style={{
                    background: m.role === "user" ? "#C1653D" : "#F4F0EA",
                    color: m.role === "user" ? "#FFFFFF" : "#2A2A2A",
                    borderRadius: m.role === "user" ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
                  }}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {loading && <p className="text-[13px] text-[#888888] pl-12">답변을 준비하고 있어요...</p>}
            <div ref={bottomRef} />
          </div>

          <div className="p-4 border-t border-black/6 space-y-2">
            <p className="text-[12px] font-bold text-[#888888] mb-1">질문 선택</p>
            {questions.map((q) => (
              <button
                key={q.id}
                onClick={() => handleAsk(q)}
                disabled={loading}
                className="w-full text-left px-4 py-3 rounded-xl text-[14px] font-medium border transition-all disabled:opacity-50"
                style={{
                  borderColor: askedIds.has(q.id) ? "#8FAE8B60" : "#C1653D40",
                  background: askedIds.has(q.id) ? "#8FAE8B10" : "#C1653D06",
                  color: "#2A2A2A",
                }}
              >
                {q.text} {askedIds.has(q.id) && <span className="text-[#8FAE8B]">✓</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-2xl px-5 py-4 mt-4 flex items-start gap-2.5 bg-[#E08A5B]/10 border border-[#E08A5B]/25">
          <span className="text-[15px] shrink-0">⚠️</span>
          <span className="text-[13px] leading-relaxed text-[#7A4B28]">
            챗봇 답변은 미리 준비된 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
          </span>
        </div>
      </main>
    </div>
  );
}
