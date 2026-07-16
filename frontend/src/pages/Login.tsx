import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { login } from "../api/auth";
import { getCaregiverPatients, type Caregiver, type Patient } from "../api/monitoring";
import { C } from "../theme";

export default function Login() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const proceedWithPatient = (caregiverId: number, patient: Patient) => {
    localStorage.setItem("caregiver_id", String(caregiverId));
    localStorage.setItem("patient_id", String(patient.id));
    navigate("/dashboard");
  };

  const handleLogin = async () => {
    if (!identifier.trim() || !password) return;
    setError("");
    setLoading(true);
    try {
      const { access_token, caregiver_id, name, role } = await login(identifier.trim(), password);
      localStorage.setItem("access_token", access_token);

      // 환자 본인 로그인은 "케어하는 환자 목록"이 없어서 보호자 흐름을 못 탄다 —
      // 자기 자신을 바로 대시보드로 보낸다 (SignUp.tsx의 환자 본인 가입 흐름과 동일).
      if (role === "patient") {
        localStorage.setItem("patient_id", String(caregiver_id));
        localStorage.removeItem("caregiver_id");
        navigate("/dashboard");
        return;
      }

      localStorage.setItem("caregiver_id", String(caregiver_id));
      setSelectedCaregiver({ id: caregiver_id, name } as Caregiver);

      const list = await getCaregiverPatients(caregiver_id);
      if (list.length === 0) {
        // [2026-07-15] 케어하는 환자가 없으면 여기서 막다른 길이었음 — SignUp.tsx의
        // 보호자 가입 직후 흐름과 동일하게 환자 등록 화면으로 바로 보낸다.
        navigate("/patients");
        return;
      } else if (list.length === 1) {
        proceedWithPatient(caregiver_id, list[0]);
        return;
      } else {
        setPatients(list);
      }
    } catch {
      setError("이메일/전화번호 또는 비밀번호가 올바르지 않아요.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setSelectedCaregiver(null);
    setPatients([]);
    setError("");
  };

  return (
    <div style={styles.page}>
      <NavBar />

      <main style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>안녕하세요</h1>
          <p style={styles.subtitle}>
            {patients.length > 0 ? "케어하실 환자를 선택해 주세요" : "이메일(또는 전화번호)과 비밀번호를 입력해 주세요"}
          </p>
        </div>

        <div style={styles.card}>
          {!selectedCaregiver && (
            <form
              style={styles.optionList}
              onSubmit={(e) => {
                e.preventDefault();
                handleLogin();
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
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호"
                style={styles.input}
                autoComplete="current-password"
              />
              {error && <p style={{ ...styles.stateText, color: C.danger }}>{error}</p>}
              <button type="submit" disabled={loading} style={styles.submitBtn}>
                {loading ? "로그인 중..." : "로그인"}
              </button>
              <button
                type="button"
                onClick={() => navigate("/reset-password")}
                style={{ ...styles.backBtn, textAlign: "center" as const, alignSelf: "center" }}
              >
                비밀번호를 잊으셨나요?
              </button>
            </form>
          )}

          {selectedCaregiver && (
            <div style={styles.optionList}>
              {error && <p style={{ ...styles.stateText, color: C.danger }}>{error}</p>}
              {patients.map((p) => (
                <button
                  key={p.id}
                  style={styles.optionBtn}
                  onClick={() => proceedWithPatient(selectedCaregiver.id, p)}
                >
                  <span style={styles.optionName}>{p.name}</span>
                  {p.note && <span style={styles.optionTag}>{p.note}</span>}
                </button>
              ))}
              <button style={styles.backBtn} onClick={handleBack}>
                ← 다시 로그인
              </button>
            </div>
          )}
        </div>

        <p style={{ ...styles.trust, marginTop: 12 }}>
          처음이신가요?{" "}
          <button
            onClick={() => navigate("/register")}
            style={{ color: C.terracotta, fontWeight: 700, background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
          >
            회원가입
          </button>
        </p>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: C.ivory,
    fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif",
  },
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
  stateText: { fontSize: 14, color: C.muted, textAlign: "center" as const, padding: "12px 0" },
  optionList: { display: "flex", flexDirection: "column" as const, gap: 10 },
  optionBtn: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    padding: "16px 18px",
    fontSize: 15,
    fontWeight: 600,
    color: C.dark,
    background: C.ivory,
    border: "1.5px solid rgba(30,26,23,0.12)",
    borderRadius: 10,
    cursor: "pointer",
    textAlign: "left" as const,
  },
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
  optionName: { fontSize: 15, fontWeight: 700, color: C.dark },
  optionTag: { fontSize: 12, fontWeight: 600, color: C.terracotta, background: C.bubbleBg, borderRadius: 12, padding: "4px 10px" },
  backBtn: {
    marginTop: 4,
    padding: "10px",
    fontSize: 13,
    color: C.muted,
    background: "transparent",
    border: "none",
    cursor: "pointer",
    textAlign: "left" as const,
  },
  trust: { marginTop: 28, fontSize: 13, color: C.muted, textAlign: "center" },
};
