import { useState } from "react";
import { useNavigate } from "react-router-dom";

const questions = [
  "글씨를 읽고 이해하기가 어렵지 않나요?",
  "처방전이나 약봉투를 직접 보관·관리하시나요?",
  "약을 혼자 정해진 시간에 챙겨 드시나요?",
  "복용법(몇 알/하루 몇 번)을 확인할 수 있나요?",
];

export default function Check() {
  const navigate = useNavigate();
  const [answers, setAnswers] = useState<(boolean | null)[]>(Array(questions.length).fill(null));
  const [showResult, setShowResult] = useState(false);

  const allAnswered = answers.every((a) => a !== null);
  const canSelf = answers.filter(Boolean).length >= 3;

  const handleAnswer = (i: number, val: boolean) => {
    const next = [...answers];
    next[i] = val;
    setAnswers(next);
  };

  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>
      <main style={styles.main}>
        {!showResult ? (
          <>
            <div style={styles.header}>
              <h1 style={styles.title}>복약 정보를 스스로 확인하고<br />이해하실 수 있나요?</h1>
              <p style={styles.subtitle}>어르신이 직접 응답하거나, 보호자/요양보호사가 대신 응답해도 괜찮아요.</p>
            </div>
            <div style={styles.questions}>
              {questions.map((q, i) => (
                <div key={i} style={styles.qCard}>
                  <p style={styles.qText}>질문 {i + 1}. {q}</p>
                  <div style={styles.qButtons}>
                    <button
                      style={{ ...styles.qBtn, ...(answers[i] === true ? styles.qBtnActive : {}) }}
                      onClick={() => handleAnswer(i, true)}
                    >예</button>
                    <button
                      style={{ ...styles.qBtn, ...(answers[i] === false ? styles.qBtnInactive : {}) }}
                      onClick={() => handleAnswer(i, false)}
                    >아니오</button>
                  </div>
                </div>
              ))}
            </div>
            <div style={styles.actions}>
              <button style={styles.backBtn} onClick={() => navigate("/login")}>이전</button>
              <button
                style={{ ...styles.nextBtn, ...(!allAnswered ? styles.nextBtnDisabled : {}) }}
                disabled={!allAnswered}
                onClick={() => setShowResult(true)}
              >다음</button>
            </div>
          </>
        ) : (
          <>
            <div style={styles.header}>
              <h1 style={styles.title}>검사 결과</h1>
              <p style={styles.subtitle}>결과와 무관하게 다음 단계로 진행할 수 있어요.</p>
            </div>
            <div style={styles.resultCards}>
              <div
                style={{ ...styles.resultCard, ...(canSelf ? styles.resultCardActive : {}), cursor: "pointer" }}
                onClick={() => navigate("/select")}
              >
                <div style={styles.resultIcon}>✅</div>
                <h3 style={styles.resultTitle}>본인 이용 가능</h3>
                <p style={styles.resultDesc}>큰 글씨 모드로 진행</p>
                <p style={styles.resultSub}>본인이 직접 복약·가이드 확인</p>
                <p style={styles.resultHint}>→ 클릭하면 이용 방식 선택으로</p>
              </div>
              <div
                style={{ ...styles.resultCard, ...(!canSelf ? styles.resultCardActive : {}), cursor: "pointer" }}
                onClick={() => navigate("/select")}
              >
                <div style={styles.resultIcon}>🧩</div>
                <h3 style={styles.resultTitle}>보호자·요양보호사 도움 필요</h3>
                <p style={styles.resultDesc}>일반 모드 + 대리 입력 안내</p>
                <p style={styles.resultSub}>보호자/요양보호사가 등록·확인</p>
                <p style={styles.resultHint}>→ 클릭하면 이용 방식 선택으로</p>
              </div>
            </div>
            <p style={styles.resultNote}>💡 결과와 무관하게 원하는 방식을 선택할 수 있어요.</p>
            <div style={styles.actions}>
              <button style={styles.backBtn} onClick={() => setShowResult(false)}>이전</button>
              <button style={styles.nextBtn} onClick={() => navigate("/select")}>다음</button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  nav: { padding: "16px 20px", background: "#FFFFFF", borderBottom: "1px solid #EEE6DC", display: "flex", alignItems: "center" },
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45" },
  main: { maxWidth: 900, margin: "0 auto", padding: "40px 20px 60px" },
  header: { marginBottom: 32 },
  title: { fontSize: "clamp(20px, 4vw, 28px)" as unknown as number, fontWeight: 700, color: "#2A2A2A", lineHeight: 1.4, marginBottom: 12, wordBreak: "keep-all" as const },
  subtitle: { fontSize: 14, color: "#888888", wordBreak: "keep-all" as const },
  questions: { display: "flex", flexDirection: "column" as const, gap: 12, marginBottom: 32 },
  qCard: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 12, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" as const },
  qText: { fontSize: 14, color: "#2A2A2A", flex: 1, wordBreak: "keep-all" as const, minWidth: 180 },
  qButtons: { display: "flex", gap: 8, flexShrink: 0 },
  qBtn: { padding: "8px 18px", fontSize: 14, border: "1.5px solid #D9C8B8", borderRadius: 8, background: "#FAFAFA", color: "#666666", cursor: "pointer" },
  qBtnActive: { background: "#C16A45", borderColor: "#C16A45", color: "#FFFFFF", fontWeight: 600 },
  qBtnInactive: { background: "#F0E5D8", borderColor: "#C16A45", color: "#C16A45", fontWeight: 600 },
  resultCards: { display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" as const },
  resultCard: { flex: 1, minWidth: 200, background: "#FFFFFF", border: "2px solid #EEE6DC", borderRadius: 16, padding: "28px 20px", textAlign: "center" as const },
  resultCardActive: { borderColor: "#C16A45", background: "#FFF8F4" },
  resultIcon: { fontSize: 36, marginBottom: 12 },
  resultTitle: { fontSize: 15, fontWeight: 700, color: "#2A2A2A", marginBottom: 8, wordBreak: "keep-all" as const },
  resultDesc: { fontSize: 13, color: "#888888", marginBottom: 8 },
  resultSub: { fontSize: 13, fontWeight: 600, color: "#C16A45", marginBottom: 6 },
  resultHint: { fontSize: 12, color: "#AAAAAA" },
  resultNote: { textAlign: "center" as const, fontSize: 13, color: "#888888", marginBottom: 24 },
  actions: { display: "flex", gap: 12, justifyContent: "center" },
  backBtn: { padding: "12px 28px", fontSize: 15, background: "#FFFFFF", border: "1.5px solid #D9C8B8", borderRadius: 10, color: "#666666", cursor: "pointer" },
  nextBtn: { padding: "12px 40px", fontSize: 15, fontWeight: 700, background: "#C16A45", border: "none", borderRadius: 10, color: "#FFFFFF", cursor: "pointer" },
  nextBtnDisabled: { background: "#D9C8B8", cursor: "not-allowed" },
};
