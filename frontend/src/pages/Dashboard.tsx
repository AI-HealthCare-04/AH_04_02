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
import { getCurrentCaregiverId, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

export default function Dashboard() {
  const navigate = useNavigate();
  const patientId = useGuardedPatientId();
  const [meds, setMeds] = useState<Medication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // [수정] "보호자를 연결해보세요" 배너는 환자 본인이 아직 아무 보호자와도 연결 안 됐을 때
  // 초대를 유도하려는 것 — 이미 보호자로 로그인해서 이 환자를 보고 있는 사람에게는
  // (본인이 이미 연결된 보호자이므로) 의미가 없고, 눌러도 환자용 초대 화면(Connect.tsx)이
  // 떠서 혼란만 준다. 환자 본인 로그인(caregiver_id 없음)일 때만 보여준다.
  const [showBanner, setShowBanner] = useState(!getCurrentCaregiverId());
  const [recentRecords, setRecentRecords] = useState<RecordSummary[]>([]);

  useEffect(() => {
    if (patientId == null) return;
    getTodayMedications(patientId)
      .then(setMeds)
      .catch(() => setError("복약 목록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
    listRecords(patientId)
      .then((list) => setRecentRecords(list.filter((r) => r.status === "completed").slice(0, 2)))
      .catch(() => {});
  }, [patientId]);

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
        {!loading && error && <p style={{ ...styles.stateText, color: C.danger }}>{error}</p>}
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
                  ...(med.status === "taken" ? { background: `${C.success}30`, color: C.successText } :
                      med.status === "skipped" ? { background: C.bubbleBg, color: C.muted } : {})
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
                        borderColor: isActive ? C.terracotta : "rgba(30,26,23,0.12)",
                        background: isActive && s === "pending" ? C.terracotta : isActive ? C.bubbleBg : C.white,
                        color: isActive && s === "pending" ? C.white : isActive ? C.terracotta : C.muted,
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
  page: { minHeight: "100vh", background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 700, margin: "0 auto", padding: "32px 20px 60px" },
  headerRow: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 },
  todayLabel: { fontSize: 13, color: C.muted, marginBottom: 4 },
  dateTitle: { fontSize: 28, fontWeight: 800, color: C.dark },
  careBadge: { fontSize: 13, fontWeight: 700, color: C.terracotta, background: C.bubbleBg, border: `1px solid ${C.terracotta}40`, borderRadius: 20, padding: "8px 16px" },
  banner: { background: `${C.terracotta}18`, borderRadius: 16, padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32, flexWrap: "wrap" as const, gap: 12 },
  bannerTitle: { fontSize: 15, fontWeight: 700, color: C.dark, marginBottom: 4 },
  bannerDesc: { fontSize: 13, color: C.muted },
  bannerActions: { display: "flex", alignItems: "center", gap: 8 },
  bannerBtn: { padding: "10px 20px", background: C.terracotta, color: C.white, border: "none", borderRadius: 24, fontWeight: 700, cursor: "pointer", fontSize: 13, outline: "none" },
  closeBtn: { width: 32, height: 32, borderRadius: "50%", border: "none", background: `${C.terracotta}30`, cursor: "pointer", fontSize: 16, color: C.muted, outline: "none" },
  sectionTitle: { fontSize: 18, fontWeight: 800, color: C.dark, marginBottom: 16 },
  stateText: { fontSize: 14, color: C.muted, marginBottom: 16 },
  medList: { display: "flex", flexDirection: "column" as const, gap: 16, marginBottom: 32 },
  medCard: { background: C.white, borderRadius: 16, padding: "20px 24px", border: "1px solid rgba(30,26,23,0.12)" },
  medHeader: { display: "flex", justifyContent: "space-between", marginBottom: 16 },
  medName: { fontSize: 17, fontWeight: 700, color: C.dark, marginBottom: 4 },
  medMeta: { fontSize: 13, color: C.muted },
  statusBadge: { fontSize: 12, fontWeight: 700, color: C.terracotta, background: C.bubbleBg, borderRadius: 12, padding: "4px 10px", height: "fit-content" },
  medActions: { display: "flex", gap: 8 },
  uploadCta: { background: C.dark, borderRadius: 16, padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, cursor: "pointer", marginBottom: 32 },
  uploadIcon: { width: 40, height: 40, borderRadius: 12, background: "rgba(255,255,255,0.12)", color: C.white, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 },
  uploadTitle: { color: C.white, fontWeight: 700, fontSize: 15, marginBottom: 4 },
  uploadDesc: { color: "rgba(255,255,255,0.65)", fontSize: 13 },
  chevron: { marginLeft: "auto", color: "rgba(255,255,255,0.65)", fontSize: 20 },
  guideGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 32 },
  guideCard: { background: C.white, borderRadius: 16, padding: 20, border: "1px solid rgba(30,26,23,0.12)" },
  guideIcon: { fontSize: 20, marginBottom: 12 },
  guideTitle: { fontSize: 14, fontWeight: 700, color: C.dark, marginBottom: 20, minHeight: 40 },
  guideFooter: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  guideDate: { fontSize: 12, color: C.muted },
  guideBtn: { fontSize: 12, fontWeight: 700, color: C.terracotta, background: C.bubbleBg, border: "none", borderRadius: 14, padding: "6px 12px", cursor: "pointer", outline: "none" },
  disclaimer: { textAlign: "center" as const, fontSize: 12, color: C.muted },
};
