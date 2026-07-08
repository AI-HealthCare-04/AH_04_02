import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getCaregivers,
  getCaregiverPatients,
  type Caregiver,
  type Patient,
} from "../api/monitoring";

/**
 * [7/6] 원래 이메일/비밀번호 로그인이었는데, 실제 JWT 로그인(auth_router.py)은
 * schedule_v6에서 스코프 밖으로 보류돼서 main.py에 아직 안 붙어있음.
 *
 * 대신 이미 동작하는 보호자/환자 조회 API로 "본인 선택" 방식으로 대체함.
 * 나중에 실제 로그인이 켜지면 이 화면을 이메일/비밀번호 폼으로 다시 바꾸고,
 * 로그인 성공 후 caregiver.id로 아래와 동일하게 환자 목록을 불러오면 됨.
 */
const relationLabel: Record<string, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

export default function Login() {
  const navigate = useNavigate();
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getCaregivers()
      .then(setCaregivers)
      .catch(() => setError("목록을 불러오지 못했어요. 백엔드 서버가 켜져 있는지 확인해 주세요."))
      .finally(() => setLoading(false));
  }, []);

  const proceedWithPatient = (caregiver: Caregiver, patient: Patient) => {
    localStorage.setItem("caregiver_id", String(caregiver.id));
    localStorage.setItem("patient_id", String(patient.id));
    navigate("/dashboard");
  };

  const handleSelectCaregiver = async (caregiver: Caregiver) => {
    setError("");
    setLoading(true);
    setSelectedCaregiver(caregiver);
    try {
      const list = await getCaregiverPatients(caregiver.id);
      if (list.length === 0) {
        setError("이 보호자가 케어하는 환자가 아직 없어요.");
      } else if (list.length === 1) {
        proceedWithPatient(caregiver, list[0]);
        return;
      } else {
        setPatients(list);
      }
    } catch {
      setError("환자 목록을 불러오지 못했어요.");
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
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>

      <main style={styles.main}>
        <div style={styles.header}>
          <h1 style={styles.title}>안녕하세요</h1>
          <p style={styles.subtitle}>
            {patients.length > 0 ? "케어하실 환자를 선택해 주세요" : "본인을 선택해 주세요"}
          </p>
        </div>

        <div style={styles.card}>
          {loading && <p style={styles.stateText}>불러오는 중이에요...</p>}
          {!loading && error && <p style={{ ...styles.stateText, color: "#D94F4F" }}>{error}</p>}

          {!loading && patients.length === 0 && !error && (
            <div style={styles.optionList}>
              {caregivers.map((c) => (
                <button key={c.id} style={styles.optionBtn} onClick={() => handleSelectCaregiver(c)}>
                  <span style={styles.optionName}>{c.name}</span>
                  <span style={styles.optionTag}>{relationLabel[c.relation_type] ?? c.relation_type}</span>
                </button>
              ))}
            </div>
          )}

          {!loading && patients.length > 0 && selectedCaregiver && (
            <div style={styles.optionList}>
              {patients.map((p) => (
                <button
                  key={p.id}
                  style={styles.optionBtn}
                  onClick={() => proceedWithPatient(selectedCaregiver, p)}
                >
                  <span style={styles.optionName}>{p.name}</span>
                  {p.note && <span style={styles.optionTag}>{p.note}</span>}
                </button>
              ))}
              <button style={styles.backBtn} onClick={handleBack}>
                ← 다른 보호자로
              </button>
            </div>
          )}
        </div>

        <p style={styles.trust}>
          🔒 비밀번호 로그인은 아직 준비 중이에요 — 임시로 이름을 선택하는 방식이에요
        </p>
        <p style={{ ...styles.trust, marginTop: 12 }}>
          처음이신가요?{" "}
          <button
            onClick={() => navigate("/register")}
            style={{ color: "#C16A45", fontWeight: 700, background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
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
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45", letterSpacing: "-0.3px" },
  main: {
    maxWidth: 480,
    margin: "0 auto",
    padding: "60px 24px 80px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  header: { textAlign: "center", marginBottom: 36 },
  title: { fontSize: 32, fontWeight: 700, color: "#2A2A2A", marginBottom: 8, letterSpacing: "-0.5px" },
  subtitle: { fontSize: 16, color: "#888888" },
  card: {
    width: "100%",
    background: "#FFFFFF",
    borderRadius: 16,
    padding: "28px 24px",
    boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
    border: "1px solid #EEE6DC",
  },
  stateText: { fontSize: 14, color: "#888888", textAlign: "center" as const, padding: "12px 0" },
  optionList: { display: "flex", flexDirection: "column" as const, gap: 10 },
  optionBtn: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    padding: "16px 18px",
    fontSize: 15,
    fontWeight: 600,
    color: "#2A2A2A",
    background: "#FAFAFA",
    border: "1.5px solid #EEE6DC",
    borderRadius: 10,
    cursor: "pointer",
    textAlign: "left" as const,
  },
  optionName: { fontSize: 15, fontWeight: 700, color: "#2A2A2A" },
  optionTag: { fontSize: 12, fontWeight: 600, color: "#C16A45", background: "#F5EDE4", borderRadius: 12, padding: "4px 10px" },
  backBtn: {
    marginTop: 4,
    padding: "10px",
    fontSize: 13,
    color: "#AAAAAA",
    background: "transparent",
    border: "none",
    cursor: "pointer",
    textAlign: "left" as const,
  },
  trust: { marginTop: 28, fontSize: 13, color: "#AAAAAA", textAlign: "center" },
};
