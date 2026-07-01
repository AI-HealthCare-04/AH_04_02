import { useNavigate } from "react-router-dom";

export default function Connect() {
  const navigate = useNavigate();
  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>
      <main style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>보호자 계정 선택 시 추가 설정</h1>
          <p style={styles.subtitle}>본인 계정으로 로그인 후, 어르신 정보 연결(신뢰관계)을 등록할 수 있어요.</p>
        </div>
        <div style={styles.card}>
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>어르신 연결 옵션</h2>
            <p style={styles.sectionDesc}>
              어르신 정보 보안(신뢰관계 등록) 필요함<br />
              등록하지 않으면 90일 후 자동으로 연결이 해제됩니다.
            </p>
          </div>
          <div style={styles.trustNote}>
            <p style={styles.trustText}>
              💡 보호자가 대신 등록할 경우 "OO님이 대신 올려드렸어요"라고 어르신에게 투명하게 표시됩니다.
            </p>
          </div>
        </div>
        <div style={styles.actions}>
          <button style={styles.backBtn} onClick={() => navigate("/select")}>이전</button>
          <button style={styles.connectBtn} onClick={() => navigate("/upload")}>
            연결 등록
          </button>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  nav: { padding: "16px 40px", background: "#FFFFFF", borderBottom: "1px solid #EEE6DC", display: "flex", alignItems: "center" },
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45" },
  main: { maxWidth: 640, margin: "0 auto", padding: "60px 24px" },
  header: { marginBottom: 36 },
  title: { fontSize: 26, fontWeight: 700, color: "#2A2A2A", marginBottom: 10 },
  subtitle: { fontSize: 15, color: "#888888", lineHeight: 1.6 },
  card: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 16, padding: "32px", marginBottom: 32 },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: 700, color: "#2A2A2A", marginBottom: 8 },
  sectionDesc: { fontSize: 14, color: "#666666", lineHeight: 1.7 },
  trustNote: { background: "#FFF8F4", border: "1px solid #F0E5D8", borderRadius: 10, padding: "14px 16px" },
  trustText: { fontSize: 13, color: "#C16A45", lineHeight: 1.6 },
  actions: { display: "flex", gap: 12, justifyContent: "center" },
  backBtn: { padding: "12px 32px", fontSize: 15, background: "#FFFFFF", border: "1.5px solid #D9C8B8", borderRadius: 10, color: "#666666", cursor: "pointer" },
  connectBtn: { padding: "12px 48px", fontSize: 15, fontWeight: 700, background: "#C16A45", border: "none", borderRadius: 10, color: "#FFFFFF", cursor: "pointer" },
};
