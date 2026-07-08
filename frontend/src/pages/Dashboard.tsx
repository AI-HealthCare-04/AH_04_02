import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import {
  getTodayMedications,
  checkIntake,
  clearIntake,
  type Medication,
  type IntakeStatus,
} from "../api/monitoring";
import { listRecords, type RecordSummary } from "../api/records";

// 로그인이 아직 없어서 patient_id를 localStorage에서 관리
// (환자가 여러 명이 되면 "환자 선택" 화면에서 이 값을 설정하도록 확장)
function getCurrentPatientId(): number {
  return Number(localStorage.getItem("patient_id") ?? 1);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [meds, setMeds] = useState<Medication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showBanner, setShowBanner] = useState(true);
  const [recentRecords, setRecentRecords] = useState<RecordSummary[]>([]);

  useEffect(() => {
    const patientId = getCurrentPatientId();
    getTodayMedications(patientId)
      .then(setMeds)
      .catch(() => setError("복약 목록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
    listRecords(patientId)
      .then((list) => setRecentRecords(list.filter((r) => r.status === "completed").slice(0, 2)))
      .catch(() => {});
  }, []);

  const updateStatus = async (id: string, status: IntakeStatus) => {
    // 먼저 화면부터 낙관적으로 바꾸고, 실패하면 되돌림 (버튼 반응성 위해)
    const prev = meds;
    setMeds((cur) => cur.map((m) => (m.id === id ? { ...m, status } : m)));

    try {
      if (status === "pending") {
        await clearIntake(id);
      } else {
        await checkIntake(id, status);
      }
    } catch {
      setMeds(prev); // 실패 시 원래 상태로 롤백
    }
  };

  const today = new Date();
  const dateLabel = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일 (${"일월화수목금토"[today.getDay()]})`;

  return (
    <div style={styles.page}>
      <NavBar isLoggedIn userName="김건강" />
      <main style={styles.main}>
        <div style={styles.headerRow}>
          <div>
            <p style={styles.todayLabel}>오늘</p>
            <h1 style={styles.dateTitle}>{dateLabel}</h1>
          </div>
          <span style={styles.careBadge}>제3자 도움 필요</span>
        </div>

        {showBanner && (
          <div style={styles.banner}>
            <div>
              <p style={styles.bannerTitle}>보호자를 연결해보세요</p>
              <p style={styles.bannerDesc}>복약 관리를 도울 분을 연결하면 더 안전해요</p>
            </div>
            <div style={styles.bannerActions}>
              <button style={styles.bannerBtn} onMouseDown={(e) => e.preventDefault()} onClick={() => navigate("/connect")}>연결하러 가기</button>
              <button style={styles.closeBtn} onMouseDown={(e) => e.preventDefault()} onClick={() => setShowBanner(false)}>×</button>
            </div>
          </div>
        )}

        <h2 style={styles.sectionTitle}>오늘의 복약</h2>

        {loading && <p style={styles.stateText}>불러오는 중이에요...</p>}
        {!loading && error && <p style={{ ...styles.stateText, color: "#D94F4F" }}>{error}</p>}
        {!loading && !error && meds.length === 0 && (
          <p style={styles.stateText}>등록된 복약 일정이 없어요.</p>
        )}

        <div style={styles.medList}>
          {meds.map((med) => (
            <div key={med.id} style={styles.medCard}>
              <div style={styles.medHeader}>
                <div>
                  <p style={styles.medName}>{med.name}</p>
                  <p style={styles.medMeta}>{med.time}{med.note ? ` · ${med.note}` : ""}</p>
                </div>
                <span style={{
                  ...styles.statusBadge,
                  ...(med.status === "taken" ? { background: "#E8EFE2", color: "#5C7A4A" } :
                      med.status === "skipped" ? { background: "#F0EBE3", color: "#8A7A6A" } : {})
                }}>
                  {med.status === "taken" ? "복용완료" : med.status === "skipped" ? "건너뜀" : "미복용"}
                </span>
              </div>
              <div style={styles.medActions}>
                {(["taken", "pending", "skipped"] as IntakeStatus[]).map((s) => {
                  const isActive = med.status === s;
                  const labels = { taken: "복용했어요", pending: "아직이요", skipped: "건너뛸게요" };
                  return (
                    <button
                      key={s}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => updateStatus(med.id, s)}
                      style={{
                        flex: 1,
                        padding: "12px 0",
                        borderRadius: 24,
                        borderWidth: 1.5,
                        borderStyle: "solid",
                        borderColor: isActive ? "#C16A45" : "#E0D3C4",
                        background: isActive && s === "pending" ? "#C16A45" : isActive ? "#F5EDE4" : "#FFFFFF",
                        color: isActive && s === "pending" ? "#FFFFFF" : isActive ? "#C16A45" : "#666666",
                        fontWeight: 600,
                        cursor: "pointer",
                        fontSize: 14,
                        outline: "none",
                        boxShadow: "none",
                        fontFamily: "inherit",
                      }}
                    >
                      {labels[s]}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div style={styles.uploadCta} onClick={() => navigate("/upload")}>
          <span style={styles.uploadIcon}>+</span>
          <div>
            <p style={styles.uploadTitle}>처방전으로 새 가이드 만들기</p>
            <p style={styles.uploadDesc}>처방전 사진을 찍거나 파일을 올려주세요</p>
          </div>
          <span style={styles.chevron}>›</span>
        </div>

        <h2 style={styles.sectionTitle}>최근 받은 가이드</h2>
        {recentRecords.length === 0 ? (
          <p style={{ ...styles.stateText, marginBottom: 32 }}>아직 받은 복약 가이드가 없어요.</p>
        ) : (
          <div style={styles.guideGrid}>
            {recentRecords.map((r) => (
              <div key={r.record_id} style={styles.guideCard}>
                <div style={styles.guideIcon}>📄</div>
                <p style={styles.guideTitle}>{r.diagnosis || "복약 가이드"}</p>
                <div style={styles.guideFooter}>
                  <span style={styles.guideDate}>생성일 {new Date(r.created_at).toLocaleDateString("ko-KR")}</span>
                  <button
                    style={styles.guideBtn}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => navigate(`/records/${r.record_id}`)}
                  >
                    자세히 보기 ›
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <p style={styles.disclaimer}>본 정보는 의료진의 진단·처방을 대체하지 않습니다</p>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 700, margin: "0 auto", padding: "32px 20px 60px" },
  headerRow: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
  todayLabel: { fontSize: 13, color: "#888888", marginBottom: 4 },
  dateTitle: { fontSize: 28, fontWeight: 800, color: "#2A2A2A" },
  careBadge: { fontSize: 13, fontWeight: 700, color: "#C16A45", background: "#F5EDE4", border: "1px solid #E8CDB8", borderRadius: 20, padding: "8px 16px" },
  banner: { background: "#F3E3D2", borderRadius: 16, padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32, flexWrap: "wrap" as const, gap: 12 },
  bannerTitle: { fontSize: 15, fontWeight: 700, color: "#2A2A2A", marginBottom: 4 },
  bannerDesc: { fontSize: 13, color: "#8A7A6A" },
  bannerActions: { display: "flex", alignItems: "center", gap: 8 },
  bannerBtn: { padding: "10px 20px", background: "#C16A45", color: "#FFFFFF", border: "none", borderRadius: 24, fontWeight: 700, cursor: "pointer", fontSize: 13, outline: "none" },
  closeBtn: { width: 32, height: 32, borderRadius: "50%", border: "none", background: "#E5D5C4", cursor: "pointer", fontSize: 16, color: "#8A7A6A", outline: "none" },
  sectionTitle: { fontSize: 18, fontWeight: 800, color: "#2A2A2A", marginBottom: 16 },
  stateText: { fontSize: 14, color: "#888888", marginBottom: 16 },
  medList: { display: "flex", flexDirection: "column" as const, gap: 16, marginBottom: 32 },
  medCard: { background: "#FFFFFF", borderRadius: 16, padding: "20px 24px", border: "1px solid #EEE6DC" },
  medHeader: { display: "flex", justifyContent: "space-between", marginBottom: 16 },
  medName: { fontSize: 17, fontWeight: 700, color: "#2A2A2A", marginBottom: 4 },
  medMeta: { fontSize: 13, color: "#888888" },
  statusBadge: { fontSize: 12, fontWeight: 700, color: "#C16A45", background: "#F5EDE4", borderRadius: 12, padding: "4px 10px", height: "fit-content" },
  medActions: { display: "flex", gap: 8 },
  uploadCta: { background: "#2A211B", borderRadius: 16, padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, cursor: "pointer", marginBottom: 32 },
  uploadIcon: { width: 40, height: 40, borderRadius: 12, background: "#3D3128", color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 },
  uploadTitle: { color: "#FFFFFF", fontWeight: 700, fontSize: 15, marginBottom: 4 },
  uploadDesc: { color: "#A99C8D", fontSize: 13 },
  chevron: { marginLeft: "auto", color: "#A99C8D", fontSize: 20 },
  guideGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 32 },
  guideCard: { background: "#FFFFFF", borderRadius: 16, padding: 20, border: "1px solid #EEE6DC" },
  guideIcon: { fontSize: 20, marginBottom: 12 },
  guideTitle: { fontSize: 14, fontWeight: 700, color: "#2A2A2A", marginBottom: 20, minHeight: 40 },
  guideFooter: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  guideDate: { fontSize: 12, color: "#888888" },
  guideBtn: { fontSize: 12, fontWeight: 700, color: "#C16A45", background: "#F5EDE4", border: "none", borderRadius: 14, padding: "6px 12px", cursor: "pointer", outline: "none" },
  disclaimer: { textAlign: "center" as const, fontSize: 12, color: "#AAAAAA" },
};
