import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { C } from "../theme";

export default function Select() {
  const navigate = useNavigate();
  return (
    <div style={styles.page}>
      <NavBar />
      <main style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>어떤 방식으로 이용하시나요?</h1>
          <p style={styles.subtitle}>선택에 따라 화면 글씨 크기와 입력 방식이 달라집니다.</p>
        </div>
        <div style={styles.cards}>
          <div style={styles.card} onClick={() => navigate("/upload")}>
            <div style={styles.cardIcon}>👴</div>
            <h2 style={styles.cardTitle}>어르신 본인이 직접 이용</h2>
            <p style={styles.cardTag}>큰 글씨 모드</p>
            <p style={styles.cardDesc}>버튼과 글씨를 크게 보여드리고, 핵심 중심으로 안내해요.</p>
            <div style={styles.cardMeta}>
              <span style={styles.metaTag}>대화형 목록</span>
              <span style={styles.metaTag}>자동경력채우기</span>
            </div>
          </div>
          <div style={styles.card} onClick={() => navigate("/connect")}>
            <div style={styles.cardIcon}>👨‍👩‍👧</div>
            <h2 style={styles.cardTitle}>보호자·요양보호사가 대신 이용</h2>
            <p style={styles.cardTag}>일반 모드 + 대리 입력</p>
            <p style={styles.cardDesc}>업로드/입력은 보호자/요양보호사가 진행하고 어르신이 확인하기 쉽게 정리해요.</p>
            <div style={styles.cardMeta}>
              <span style={styles.metaTag}>대리입력 표시</span>
              <span style={styles.metaTag}>어르신 연결 등록</span>
            </div>
          </div>
        </div>
        <div style={styles.actions}>
          <button style={styles.backBtn} onClick={() => navigate("/")}>이전</button>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 900, margin: "0 auto", padding: "60px 24px" },
  header: { marginBottom: 48, textAlign: "center" as const },
  title: { fontSize: 28, fontWeight: 700, color: C.dark, marginBottom: 12 },
  subtitle: { fontSize: 15, color: C.muted },
  cards: { display: "flex", gap: 24, marginBottom: 48 },
  card: { flex: 1, background: C.white, border: "2px solid rgba(30,26,23,0.12)", borderRadius: 16, padding: "36px 28px", cursor: "pointer", transition: "border-color 0.15s, box-shadow 0.15s" },
  cardIcon: { fontSize: 40, marginBottom: 16 },
  cardTitle: { fontSize: 18, fontWeight: 700, color: C.dark, marginBottom: 8 },
  cardTag: { fontSize: 13, color: C.terracotta, fontWeight: 600, marginBottom: 12 },
  cardDesc: { fontSize: 14, color: C.muted, lineHeight: 1.6, marginBottom: 16 },
  cardMeta: { display: "flex", gap: 8, flexWrap: "wrap" as const },
  metaTag: { fontSize: 12, background: C.bubbleBg, color: C.terracotta, padding: "3px 10px", borderRadius: 99 },
  actions: { display: "flex", justifyContent: "center" },
  backBtn: { padding: "12px 32px", fontSize: 15, background: C.white, border: "1.5px solid rgba(30,26,23,0.12)", borderRadius: 10, color: C.muted, cursor: "pointer" },
};
