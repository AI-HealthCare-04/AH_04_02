import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { confirmPasswordReset, requestPasswordReset, verifyPasswordReset } from "../api/auth";
import { C } from "../theme";

type Step = "identifier" | "code" | "password" | "done";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("identifier");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const handleRequestCode = async () => {
    if (!identifier.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { message } = await requestPasswordReset(identifier.trim());
      setNotice(message);
      setStep("code");
    } catch {
      setError("요청에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { reset_token } = await verifyPasswordReset(identifier.trim(), code.trim());
      setResetToken(reset_token);
      setNotice("");
      setStep("password");
    } catch {
      setError("인증코드가 올바르지 않거나 만료되었어요.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPassword = async () => {
    if (!newPassword || newPassword !== newPasswordConfirm) return;
    setLoading(true);
    setError("");
    try {
      await confirmPasswordReset(resetToken, newPassword);
      setStep("done");
    } catch {
      setError("재설정에 실패했어요. 처음부터 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <NavBar />
      <main style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>비밀번호 찾기</h1>
          <p style={styles.subtitle}>
            {step === "identifier" && "가입하신 이메일 또는 전화번호를 입력해 주세요"}
            {step === "code" && "가입 이메일로 보낸 6자리 인증코드를 입력해 주세요"}
            {step === "password" && "새 비밀번호를 설정해 주세요"}
            {step === "done" && "비밀번호가 재설정됐어요"}
          </p>
        </div>

        <div style={styles.card}>
          {step === "identifier" && (
            <form
              style={styles.form}
              onSubmit={(e) => {
                e.preventDefault();
                handleRequestCode();
              }}
            >
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="이메일 또는 전화번호"
                style={styles.input}
                autoComplete="username"
              />
              {error && <p style={styles.errorText}>{error}</p>}
              <button type="submit" disabled={loading || !identifier.trim()} style={styles.submitBtn}>
                {loading ? "요청 중..." : "인증코드 받기"}
              </button>
            </form>
          )}

          {step === "code" && (
            <form
              style={styles.form}
              onSubmit={(e) => {
                e.preventDefault();
                handleVerifyCode();
              }}
            >
              {notice && <p style={styles.noticeText}>{notice}</p>}
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6자리 인증코드"
                maxLength={6}
                style={styles.input}
                autoComplete="one-time-code"
              />
              {error && <p style={styles.errorText}>{error}</p>}
              <button type="submit" disabled={loading || !code.trim()} style={styles.submitBtn}>
                {loading ? "확인 중..." : "확인"}
              </button>
              <button
                type="button"
                style={styles.linkBtn}
                onClick={() => {
                  setStep("identifier");
                  setCode("");
                  setError("");
                }}
              >
                이메일/전화번호 다시 입력
              </button>
            </form>
          )}

          {step === "password" && (
            <form
              style={styles.form}
              onSubmit={(e) => {
                e.preventDefault();
                handleConfirmPassword();
              }}
            >
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="새 비밀번호"
                style={styles.input}
                autoComplete="new-password"
              />
              <input
                type="password"
                value={newPasswordConfirm}
                onChange={(e) => setNewPasswordConfirm(e.target.value)}
                placeholder="새 비밀번호 확인"
                style={styles.input}
                autoComplete="new-password"
              />
              {newPassword && newPasswordConfirm && newPassword !== newPasswordConfirm && (
                <p style={styles.errorText}>비밀번호가 일치하지 않아요.</p>
              )}
              {error && <p style={styles.errorText}>{error}</p>}
              <button
                type="submit"
                disabled={loading || !newPassword || newPassword !== newPasswordConfirm}
                style={styles.submitBtn}
              >
                {loading ? "저장 중..." : "비밀번호 재설정"}
              </button>
            </form>
          )}

          {step === "done" && (
            <div style={styles.form}>
              <p style={styles.doneText}>새 비밀번호로 로그인해 주세요.</p>
              <button style={styles.submitBtn} onClick={() => navigate("/login")}>
                로그인하러 가기
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: {
    maxWidth: 480,
    margin: "0 auto",
    padding: "60px 24px 80px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  header: { textAlign: "center", marginBottom: 36 },
  title: { fontSize: 32, fontWeight: 700, color: C.dark, marginBottom: 8, letterSpacing: "-0.5px" },
  subtitle: { fontSize: 16, color: C.muted },
  card: {
    width: "100%",
    background: C.white,
    borderRadius: 16,
    padding: "28px 24px",
    boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
    border: "1px solid rgba(30,26,23,0.12)",
  },
  form: { display: "flex", flexDirection: "column" as const, gap: 10 },
  input: {
    width: "100%",
    padding: "14px 16px",
    fontSize: 15,
    color: C.dark,
    background: C.ivory,
    border: "1.5px solid rgba(30,26,23,0.12)",
    borderRadius: 10,
    outline: "none",
    boxSizing: "border-box" as const,
  },
  submitBtn: {
    width: "100%",
    padding: "14px",
    fontSize: 15,
    fontWeight: 700,
    color: C.white,
    background: C.terracotta,
    border: "none",
    borderRadius: 10,
    cursor: "pointer",
  },
  linkBtn: {
    marginTop: 4,
    padding: "8px",
    fontSize: 13,
    color: C.muted,
    background: "transparent",
    border: "none",
    cursor: "pointer",
    textDecoration: "underline",
  },
  errorText: { fontSize: 13, color: C.danger, padding: "4px 0" },
  noticeText: { fontSize: 13, color: C.muted, padding: "4px 0", lineHeight: 1.5 },
  doneText: { fontSize: 14, color: C.muted, textAlign: "center" as const, marginBottom: 8 },
};
