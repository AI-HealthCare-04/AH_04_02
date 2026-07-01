import { useState, useRef, useEffect, type KeyboardEvent } from "react";

type Message = { role: "user" | "bot"; text: string };

const INITIAL: Message[] = [
  { role: "bot", text: "안녕하세요 😊 복약 안내 결과에 대해 궁금한 점을 물어보세요." },
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>(INITIAL);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    // TODO: POST /api/v1/chat SSE 스트리밍 연동
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "죄송합니다. 현재 챗봇 연동 준비 중입니다. 담당 의사나 약사에게 직접 문의해 주세요." },
      ]);
      setLoading(false);
    }, 800);
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
        <span style={styles.navTitle}>복약 상담 챗봇</span>
      </nav>

      <main style={styles.main}>
        {/* 대화 이력 */}
        <div style={styles.chatArea}>
          {messages.map((msg, i) => (
            <div key={i} style={{ ...styles.msgRow, ...(msg.role === "user" ? styles.msgRowUser : {}) }}>
              {msg.role === "bot" && <div style={styles.botAvatar}>💊</div>}
              <div style={{ ...styles.bubble, ...(msg.role === "user" ? styles.bubbleUser : styles.bubbleBot) }}>
                <p style={styles.bubbleText}>{msg.text}</p>
              </div>
            </div>
          ))}
          {loading && (
            <div style={styles.msgRow}>
              <div style={styles.botAvatar}>💊</div>
              <div style={styles.bubbleBot}>
                <p style={styles.bubbleText}>답변을 생성하고 있어요...</p>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* 추천 질문 */}
        <div style={styles.suggestions}>
          {["이 약 식사 전에 먹어도 되나요?", "혈압약과 함께 먹어도 되나요?", "부작용이 있으면 어떻게 하나요?"].map((q, i) => (
            <button key={i} style={styles.suggestBtn} onClick={() => { setInput(q); }}>
              {q}
            </button>
          ))}
        </div>

        {/* 입력창 */}
        <div style={styles.inputArea}>
          <input
            style={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="궁금한 점을 입력해 주세요..."
            disabled={loading}
          />
          <button style={{ ...styles.sendBtn, ...((!input.trim() || loading) ? styles.sendBtnDisabled : {}) }} onClick={send} disabled={!input.trim() || loading}>
            전송
          </button>
        </div>

        {/* 하단 면책 고지 고정 */}
        <div style={styles.disclaimer}>
          <p style={styles.disclaimerText}>
            ⚠️ 챗봇 답변은 AI가 생성한 참고용 정보입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
          </p>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { height: "100vh", display: "flex", flexDirection: "column" as const, background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  nav: { padding: "16px 40px", background: "#FFFFFF", borderBottom: "1px solid #EEE6DC", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 },
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45" },
  navTitle: { fontSize: 15, color: "#666666" },
  main: { flex: 1, maxWidth: 800, width: "100%", margin: "0 auto", padding: "20px 24px", display: "flex", flexDirection: "column" as const, overflow: "hidden" },
  chatArea: { flex: 1, overflowY: "auto" as const, display: "flex", flexDirection: "column" as const, gap: 16, paddingBottom: 16 },
  msgRow: { display: "flex", alignItems: "flex-start", gap: 10 },
  msgRowUser: { flexDirection: "row-reverse" as const },
  botAvatar: { width: 36, height: 36, borderRadius: "50%", background: "#F0E5D8", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 },
  bubble: { maxWidth: "70%", borderRadius: 14, padding: "12px 16px" },
  bubbleBot: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderTopLeftRadius: 4 },
  bubbleUser: { background: "#C16A45", borderTopRightRadius: 4 },
  bubbleText: { fontSize: 14, lineHeight: 1.6, color: "inherit", margin: 0 } as React.CSSProperties,
  suggestions: { display: "flex", gap: 8, flexWrap: "wrap" as const, marginBottom: 12 },
  suggestBtn: { fontSize: 12, padding: "6px 14px", background: "#FFFFFF", border: "1px solid #D9C8B8", borderRadius: 99, color: "#666666", cursor: "pointer" },
  inputArea: { display: "flex", gap: 10, marginBottom: 12 },
  input: { flex: 1, padding: "12px 16px", fontSize: 14, border: "1.5px solid #D9C8B8", borderRadius: 10, background: "#FFFFFF", outline: "none" },
  sendBtn: { padding: "12px 24px", fontSize: 14, fontWeight: 700, background: "#C16A45", color: "#FFFFFF", border: "none", borderRadius: 10, cursor: "pointer" },
  sendBtnDisabled: { background: "#D9C8B8", cursor: "not-allowed" },
  disclaimer: { background: "#FFF8F4", border: "1px solid #F0E5D8", borderRadius: 10, padding: "10px 14px" },
  disclaimerText: { fontSize: 12, color: "#C16A45", lineHeight: 1.5 },
};
