import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
        <div style={styles.navRight}>
          <button style={styles.navLogin} onClick={() => navigate("/login")}>로그인</button>
          <button style={styles.navStart} onClick={() => navigate("/login")}>시작하기</button>
        </div>
      </nav>

      <main style={styles.main}>
        <p style={styles.tag}>수도권 독거노인 맞춤 건강 관리</p>
        <h1 style={styles.title}>
          효율적인 복약 관리<br />
          <span style={styles.accent}>맞춤 생활 습관 개선</span><br />
          스마트 알림 서비스
        </h1>
        <p style={styles.desc}>
          진료 기록을 기반으로 한 맞춤형 복약 안내와 생활 습관 개선 가이드를
          자동으로 생성하여, 건강한 일상을 함께 만들어갑니다.
        </p>
        <div style={styles.buttons}>
          <button style={styles.startBtn} onClick={() => navigate("/login")}>
            무료로 시작하기
          </button>
          <button style={styles.loginBtn} onClick={() => navigate("/login")}>
            로그인
          </button>
        </div>
        <div style={styles.heroImage}>
          <p style={styles.heroImageText}>서비스 이미지</p>
        </div>
        <p style={styles.trustText}>
          🔒 독거노인 및 거동 불편 사용자를 위한 안전한 서비스
        </p>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#FAF6F1",
    fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif",
  },
  nav: {
    padding: "14px 20px",
    background: "#FFFFFF",
    borderBottom: "1px solid #EEE6DC",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  logo: { fontSize: 18, fontWeight: 700, color: "#C16A45" },
  navRight: { display: "flex", gap: 8 },
  navLogin: {
    padding: "8px 16px",
    fontSize: 13,
    background: "transparent",
    border: "1.5px solid #C16A45",
    borderRadius: 8,
    color: "#C16A45",
    cursor: "pointer",
    whiteSpace: "nowrap" as const,
  },
  navStart: {
    padding: "8px 16px",
    fontSize: 13,
    background: "#C16A45",
    border: "none",
    borderRadius: 8,
    color: "#FFFFFF",
    cursor: "pointer",
    fontWeight: 600,
    whiteSpace: "nowrap" as const,
  },
  main: {
    maxWidth: 600,
    margin: "0 auto",
    padding: "48px 20px 60px",
    textAlign: "center" as const,
  },
  tag: {
    fontSize: 13,
    color: "#C16A45",
    background: "#FFF3EE",
    padding: "4px 14px",
    borderRadius: 99,
    display: "inline-block",
    marginBottom: 20,
  },
  title: {
    fontSize: "clamp(28px, 6vw, 42px)",
    fontWeight: 700,
    color: "#2A2A2A",
    lineHeight: 1.35,
    marginBottom: 20,
    letterSpacing: "-0.5px",
    wordBreak: "keep-all" as const,
  },
  accent: { color: "#C16A45" },
  desc: {
    fontSize: "clamp(14px, 3.5vw, 16px)",
    color: "#666666",
    lineHeight: 1.7,
    marginBottom: 32,
    wordBreak: "keep-all" as const,
  },
  buttons: {
    display: "flex",
    gap: 12,
    justifyContent: "center",
    flexWrap: "wrap" as const,
    marginBottom: 40,
  },
  startBtn: {
    padding: "14px 28px",
    fontSize: 15,
    fontWeight: 700,
    background: "#C16A45",
    color: "#FFFFFF",
    border: "none",
    borderRadius: 10,
    cursor: "pointer",
    minWidth: 140,
  },
  loginBtn: {
    padding: "14px 28px",
    fontSize: 15,
    background: "transparent",
    color: "#2A2A2A",
    border: "1.5px solid #D9C8B8",
    borderRadius: 10,
    cursor: "pointer",
    minWidth: 100,
  },
  heroImage: {
    background: "#EEE6DC",
    borderRadius: 16,
    height: 200,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 32,
  },
  heroImageText: { color: "#AAAAAA", fontSize: 14 },
  trustText: { fontSize: 13, color: "#AAAAAA" },
};
