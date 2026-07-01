import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      setError("이메일과 비밀번호를 모두 입력해 주세요.");
      return;
    }
    // TODO: POST /api/v1/auth/login 연동
    navigate("/check");
  };

  return (
    <div style={styles.page}>
      {/* 네비게이션 */}
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>

      <main style={styles.main}>
        {/* 헤더 */}
        <div style={styles.header}>
          <h1 style={styles.title}>안녕하세요</h1>
          <p style={styles.subtitle}>건강동행에 로그인해 주세요</p>
        </div>

        {/* 로그인 카드 */}
        <div style={styles.card}>
          <form onSubmit={handleSubmit}>
            <div style={styles.field}>
              <label style={styles.label} htmlFor="email">
                이메일 또는 전화번호
              </label>
              <input
                id="email"
                name="email"
                type="text"
                placeholder="예: hong@email.com"
                value={form.email}
                onChange={handleChange}
                style={styles.input}
                autoComplete="username"
              />
            </div>

            <div style={styles.field}>
              <label style={styles.label} htmlFor="password">
                비밀번호
              </label>
              <input
                id="password"
                name="password"
                type="password"
                placeholder="비밀번호를 입력해 주세요"
                value={form.password}
                onChange={handleChange}
                style={styles.input}
                autoComplete="current-password"
              />
            </div>

            {error && <p style={styles.error}>{error}</p>}

            <button type="submit" style={styles.loginBtn}>
              로그인
            </button>
          </form>

          <div style={styles.divider}>
            <span style={styles.dividerText}>또는</span>
          </div>

          <button
            style={styles.registerBtn}
            onClick={() => navigate("/check")}
          >
            처음 오셨나요? 회원가입
          </button>

          <button style={styles.resetBtn}>비밀번호를 잊으셨나요?</button>
        </div>

        {/* 신뢰 고지 */}
        <p style={styles.trust}>
          🔒 회원님의 진료 정보는 안전하게 보호됩니다
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
    padding: "16px 40px",
    background: "#FFFFFF",
    borderBottom: "1px solid #EEE6DC",
    display: "flex",
    alignItems: "center",
  },
  logo: {
    fontSize: 20,
    fontWeight: 700,
    color: "#C16A45",
    letterSpacing: "-0.3px",
  },
  main: {
    maxWidth: 480,
    margin: "0 auto",
    padding: "60px 24px 80px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  header: {
    textAlign: "center",
    marginBottom: 36,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: "#2A2A2A",
    marginBottom: 8,
    letterSpacing: "-0.5px",
  },
  subtitle: {
    fontSize: 16,
    color: "#888888",
  },
  card: {
    width: "100%",
    background: "#FFFFFF",
    borderRadius: 16,
    padding: "36px 32px",
    boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
    border: "1px solid #EEE6DC",
  },
  field: {
    marginBottom: 20,
  },
  label: {
    display: "block",
    fontSize: 14,
    fontWeight: 600,
    color: "#4A4A4A",
    marginBottom: 8,
  },
  input: {
    width: "100%",
    padding: "14px 16px",
    fontSize: 15,
    border: "1.5px solid #D9C8B8",
    borderRadius: 10,
    background: "#FAFAFA",
    color: "#2A2A2A",
    outline: "none",
    boxSizing: "border-box",
    transition: "border-color 0.15s",
  },
  error: {
    fontSize: 13,
    color: "#D94F4F",
    marginBottom: 12,
    marginTop: -8,
  },
  loginBtn: {
    width: "100%",
    padding: "15px",
    fontSize: 16,
    fontWeight: 700,
    color: "#FFFFFF",
    background: "#C16A45",
    border: "none",
    borderRadius: 10,
    cursor: "pointer",
    marginTop: 4,
    letterSpacing: "0.2px",
  },
  divider: {
    display: "flex",
    alignItems: "center",
    margin: "20px 0",
    gap: 12,
  },
  dividerText: {
    fontSize: 13,
    color: "#BBBBBB",
    background: "#FFFFFF",
    padding: "0 8px",
    flexShrink: 0,
    width: "100%",
    textAlign: "center",
  },
  registerBtn: {
    width: "100%",
    padding: "14px",
    fontSize: 15,
    fontWeight: 600,
    color: "#C16A45",
    background: "#FFF3EE",
    border: "1.5px solid #C16A45",
    borderRadius: 10,
    cursor: "pointer",
    marginBottom: 12,
  },
  resetBtn: {
    width: "100%",
    padding: "10px",
    fontSize: 14,
    color: "#AAAAAA",
    background: "transparent",
    border: "none",
    cursor: "pointer",
    textDecoration: "underline",
  },
  trust: {
    marginTop: 28,
    fontSize: 13,
    color: "#AAAAAA",
    textAlign: "center",
  },
};
