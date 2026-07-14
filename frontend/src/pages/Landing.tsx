import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Bell, Bookmark, Check, ChevronRight, Heart, Pill } from "lucide-react";
import NavBar from "../components/NavBar";
import { checkIntake, getLogs, getTodayMedications, type Medication, type MedicationLogEntry } from "../api/monitoring";
import { getNotificationSettings, type NotificationSettings } from "../api/care";
import { getCurrentPatientId } from "../lib/session";

const unsplash = (id: string, w: number, h: number) =>
  `https://images.unsplash.com/${id}?w=${w}&h=${h}&fit=crop&auto=format`;

// [7/14] Figma 원본(App.figma-export.tsx.bak)의 랜딩 페이지 5개 섹션 중 3개
// (최신 안내/자동 생성 시스템/대시보드 요약)가 이관 과정에서 빠졌던 것을 복원.
const FEATURE_TABS = [
  { Icon: Pill, label: "복약 안내" },
  { Icon: Heart, label: "생활 습관" },
  { Icon: Bell, label: "알림 설정" },
];

const VALUE_ITEMS = [
  "진료 기록 기반 복약 및 복약 스케쥴 분석",
  "개인 건강 상태에 맞는 생활 습관 가이드",
  "복약 시간 맞춤 알림 서비스",
];

// 대시보드 요약 카드의 도넛 차트(50% 고정) — Figma 원본과 동일한 SVG 원 둘레 계산
const DONUT_R = 36;
const DONUT_CX = 40;
const DONUT_CY = 40;
const DONUT_CIRC = 2 * Math.PI * DONUT_R;

export default function Landing() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [tab, setTab] = useState(0);
  const [meds, setMeds] = useState<Medication[]>([]);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [notifSettings, setNotifSettings] = useState<NotificationSettings | null>(null);

  // [7/14] "최신 안내" 섹션을 처방전 등록으로 실제 등록된 약품·알림 일정(오늘자)과 연결 —
  // 더 이상 Figma의 예시 텍스트가 아니라 로그인한 환자의 실제 /monitoring/today 데이터.
  useEffect(() => {
    getTodayMedications(getCurrentPatientId())
      .then(setMeds)
      .catch(() => {});
  }, []);

  // [7/14] "대시보드 요약"의 생활 습관·알림 설정 카드도 모니터링 페이지와 같은 실제
  // 데이터로 연결 — 최근 7일 복약 순응률(getLogs, MonitoringDashboard.tsx와 동일 계산식)과
  // 실제 알림 켜짐/꺼짐 상태(getNotificationSettings). "건강 점수"·"다음 병원 방문"은
  // 앱에 그런 데이터 자체가 없어서 실제로 존재하는 이 두 값으로 대체한다.
  useEffect(() => {
    const patientId = getCurrentPatientId();
    getLogs(patientId, 7)
      .then(setLogs)
      .catch(() => {});
    getNotificationSettings(patientId)
      .then(setNotifSettings)
      .catch(() => {});
  }, []);

  const takenCount = meds.filter((m) => m.status === "taken").length;
  const medsDonutPct = meds.length > 0 ? takenCount / meds.length : 0;
  const medsDonutDash = medsDonutPct * DONUT_CIRC;

  const last7Logs = logs.filter(
    (l) => Date.now() - new Date(l.checked_at).getTime() <= 7 * 24 * 60 * 60 * 1000
  );
  const adherence =
    last7Logs.length > 0
      ? Math.round((last7Logs.filter((l) => l.status === "taken").length / last7Logs.length) * 100)
      : null;
  // [7/14] 두 번째·세 번째 카드를 임의의 약 2개가 아니라 오전/오후로 나눠 보여준다.
  const morningMeds = meds.filter((m) => Number(m.time.slice(0, 2)) < 12);
  const afternoonMeds = meds.filter((m) => Number(m.time.slice(0, 2)) >= 12);

  const handleTake = async (id: string) => {
    try {
      await checkIntake(id, "taken");
      setMeds((prev) => prev.map((m) => (m.id === id ? { ...m, status: "taken" } : m)));
    } catch {
      // 랜딩 페이지 미리보기 카드라 실패해도 조용히 무시 — 실제 체크는 대시보드에서 다시 가능
    }
  };

  const renderPeriodCard = (title: string, list: Medication[]) => {
    const takenInPeriod = list.filter((m) => m.status === "taken").length;
    return (
      <div style={styles.drugCard}>
        <div style={styles.drugCardTop}>
          <div style={styles.drugCardIconBox}><Bookmark className="w-3.5 h-3.5" style={{ color: "#E08A5B" }} /></div>
          <span style={styles.drugCardPeriodTitle}>{title}</span>
        </div>
        {list.length === 0 ? (
          <p style={styles.drugCardNote}>등록된 {title} 일정이 없어요.</p>
        ) : (
          <>
            <p style={styles.periodBig}>{takenInPeriod}/{list.length}건 복용</p>
            <div style={styles.periodMedList}>
              {list.map((m, i) => {
                const done = m.status === "taken";
                return (
                  <div key={m.id} style={{ ...styles.periodMedRow, ...(i === 0 ? { borderTop: "none", paddingTop: 0 } : {}) }}>
                    <span style={{ ...styles.periodMedName, ...(done ? styles.periodMedNameDone : {}) }}>
                      {m.name} <span style={styles.periodMedTime}>{m.time}</span>
                    </span>
                    <button
                      style={{ ...styles.periodMedBtn, ...(done ? styles.periodMedBtnDone : {}) }}
                      disabled={done}
                      onClick={() => handleTake(m.id)}
                    >
                      {done ? "완료" : "체크"}
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div style={styles.page}>
      <div style={styles.heroSection}>
        <NavBar isLoggedIn userName="김건강" variant="dark" />
        <div style={styles.heroBadges}>
          <span style={styles.badge}>수도권 독거노인 맞춤 건강 관리</span>
          <span style={styles.badge}>독거노인 및 거동 불편 사용자를 위한 안전한 서비스</span>
        </div>
        <div style={styles.heroContent}>
          <h1 style={styles.heroTitle}>
            효율적인 복약 관리<br />
            <span style={{ color: "#D98552" }}>맞춤 생활 습관 개선</span><br />
            스마트 알림 서비스
          </h1>
          <p style={styles.heroDesc}>
            진료 기록을 기반으로 한 맞춤형 복약 안내와 생활 습관 개선 가이드로 건강한 일상을 함께합니다.
          </p>
          <div style={styles.heroActions}>
            <button style={styles.primaryBtn} onClick={() => navigate("/register")}>무료로 시작하기</button>
            <button style={styles.secondaryBtn} onClick={() => navigate("/login")}>로그인</button>
          </div>
        </div>
        <p style={styles.scrollHint}>스크롤하여 더 알아보기</p>
      </div>

      {/* 최신 안내 */}
      <div style={styles.featuresSection}>
        <div style={styles.featuresHeader}>
          <div>
            <p style={styles.featuresEyebrow}>최신 안내</p>
            <h2 style={styles.featuresTitle}>최신 복약 안내 및<br />생활 습관 개선 팁</h2>
          </div>
          <p style={styles.featuresDesc}>오늘의 복약 일정과 맞춤 생활 습관 가이드를 한눈에 확인하세요.</p>
        </div>

        <div style={styles.featureTabs}>
          {FEATURE_TABS.map(({ Icon, label }, i) => (
            <button
              key={label}
              onClick={() => setTab(i)}
              style={{ ...styles.featureTab, ...(tab === i ? styles.featureTabActive : {}) }}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        {meds.length === 0 ? (
          <div style={styles.emptyFeature}>
            <p style={styles.emptyFeatureText}>
              아직 등록된 복약 일정이 없어요. 처방전을 등록하면 오늘의 복약과 알림이 여기에 표시돼요.
            </p>
            <button style={styles.emptyFeatureBtn} onClick={() => navigate("/upload")}>처방전 등록하러 가기</button>
          </div>
        ) : (
          <div style={styles.featureCards}>
            <div style={styles.medCard}>
              <p style={styles.medCardEyebrow}>오늘의 복약</p>
              <p style={styles.medCardBig}>{takenCount}/{meds.length}건 복용 완료</p>
              <p style={styles.medCardDesc}>오늘 예정된 복약을 시간에 맞춰 복용하세요.</p>
              <div style={styles.medList}>
                {meds.map((m) => {
                  const done = m.status === "taken";
                  return (
                    <div key={m.id} style={styles.medRow}>
                      <div style={styles.medRowLeft}>
                        {done ? (
                          <div style={styles.medDotDone}><Check className="w-3.5 h-3.5 text-white" /></div>
                        ) : (
                          <div style={styles.medDotWait}>{m.time.slice(0, 2)}</div>
                        )}
                        <div>
                          <p style={{ ...styles.medRowName, ...(done ? styles.medRowNameDone : {}) }}>{m.name}</p>
                          <p style={styles.medRowNote}>{m.time}{m.note ? ` · ${m.note}` : ""}</p>
                        </div>
                      </div>
                      <span style={styles.medRowStatus}>
                        {m.status === "taken" ? "복용 완료" : m.status === "skipped" ? "건너뜀" : "미복용"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {renderPeriodCard("오전 복약", morningMeds)}
            {renderPeriodCard("오후 복약", afternoonMeds)}
          </div>
        )}
      </div>

      {/* 자동 생성 시스템 */}
      <div style={styles.valueSection}>
        <div style={styles.valueImageCol}>
          <img
            src={unsplash("photo-1516574187841-cb9cc2ca948b", 700, 560)}
            alt="태블릿을 사용하는 어르신"
            style={styles.valueImage}
          />
          <div style={styles.valueImageOverlay} />
          <div style={styles.valueImageCaption}>
            <span style={styles.valueImageBadge}>맞춤형 가이드</span>
            <h3 style={styles.valueImageTitle}>맞춤 진료 기록 기반<br />복약 및 생활 습관 가이드</h3>
          </div>
        </div>
        <div style={styles.valueTextCol}>
          <h2 style={styles.valueTitle}>자동 생성 시스템</h2>
          <p style={styles.valueDesc}>
            병원 진료 기록을 기반으로 개인별 맞춤 복약 안내와 생활 습관 개선 가이드를 자동으로 생성합니다.
          </p>
          {VALUE_ITEMS.map((item) => (
            <div key={item} style={styles.valueItem}>
              <div style={styles.valueCheck}><Check className="w-3.5 h-3.5 text-white" /></div>
              <span style={styles.valueItemText}>{item}</span>
            </div>
          ))}
          <button style={styles.valueBtn} onClick={() => navigate("/upload")}>
            가이드 생성하기 <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 대시보드 요약 */}
      <div style={styles.dashPreviewSection}>
        <h2 style={styles.dashPreviewTitle}>대시보드 요약</h2>
        <p style={styles.dashPreviewDesc}>건강 상태를 한눈에 확인하고 필요한 관리를 시작하세요.</p>
        <div style={styles.dashPreviewGrid}>
          <div style={styles.dashCard}>
            <img src={unsplash("photo-1584308666744-24d5c474f2ae", 400, 200)} alt="약통" style={styles.dashCardPhoto} />
            <div style={styles.dashCardBody}>
              <p style={styles.dashCardTag}>복약 관리</p>
              <div style={styles.dashDonutRow}>
                <div>
                  <p style={styles.dashDonutLabel}>오늘 복용 완료</p>
                  <p style={styles.dashDonutValue}>{takenCount} / {meds.length}</p>
                </div>
                <svg width="72" height="72" viewBox="0 0 80 80">
                  <circle cx={DONUT_CX} cy={DONUT_CY} r={DONUT_R} fill="none" stroke="#EDE8DF" strokeWidth="8" />
                  <circle
                    cx={DONUT_CX} cy={DONUT_CY} r={DONUT_R} fill="none" stroke="#C16A45" strokeWidth="8"
                    strokeDasharray={`${medsDonutDash} ${DONUT_CIRC - medsDonutDash}`} strokeLinecap="round"
                    transform="rotate(-90 40 40)"
                  />
                  <text x="40" y="45" textAnchor="middle" fontSize="13" fontWeight="700" fill="#2A2A2A">{Math.round(medsDonutPct * 100)}%</text>
                </svg>
              </div>
              <div style={styles.dashProgressTrack}>
                <div style={{ ...styles.dashProgressFill, width: `${Math.round(medsDonutPct * 100)}%` }} />
              </div>
            </div>
          </div>

          <div style={styles.dashCard}>
            <img src={unsplash("photo-1544367567-0f2fcb009e0b", 400, 200)} alt="스트레칭" style={styles.dashCardPhoto} />
            <div style={styles.dashCardBody}>
              <p style={styles.dashCardTag}>생활 습관</p>
              <div style={styles.dashScoreRow}>
                <span style={styles.dashScoreValue}>{adherence ?? "-"}{adherence != null && "%"}</span>
              </div>
              <p style={styles.dashScoreLabel}>최근 7일 복약 순응률</p>
              <div style={styles.dashStreakRow}>
                <Activity className="w-4 h-4" style={{ color: "#8FAE8B" }} />
                <span style={styles.dashStreakText}>
                  {last7Logs.length > 0 ? `최근 7일 기록 ${last7Logs.length}건` : "최근 기록 없음"}
                </span>
              </div>
            </div>
          </div>

          <div style={styles.dashCard}>
            <img src={unsplash("photo-1512941937669-90a1b58e7e9c", 400, 200)} alt="스마트폰" style={styles.dashCardPhoto} />
            <div style={styles.dashCardBody}>
              <p style={styles.dashCardTag}>알림 설정</p>
              <p style={styles.dashVisitLabel}>복약 알림</p>
              <p style={styles.dashVisitName}>{notifSettings?.medication_reminder_enabled ? "켜짐" : "꺼짐"}</p>
              <p style={styles.dashVisitMeta}>
                전체 푸시 수신 {notifSettings?.all_push_enabled ? "켜짐" : "꺼짐"}
              </p>
              <button style={styles.dashVisitBtn} onClick={() => navigate("/notification")}>알림 관리하기</button>
            </div>
          </div>
        </div>
      </div>

      <div style={styles.trustSection}>
        <span style={styles.trustBadge}>지역사회 보건 서비스 지원</span>
        <h2 style={styles.trustTitle}>믿을 수 있는 건강 관리<br />파트너와 함께합니다</h2>
      </div>

      <div style={styles.newsletterSection}>
        <div style={styles.mailIcon}>✉</div>
        <h3 style={styles.newsletterTitle}>건강 정보 뉴스레터 구독</h3>
        <p style={styles.newsletterDesc}>
          매주 새로운 건강 팁과 복약 관리 정보를 이메일로 받아보세요.<br />
          언제든지 구독을 취소할 수 있습니다.
        </p>
        <div style={styles.newsletterForm}>
          <input
            style={styles.emailInput}
            placeholder="이메일 주소를 입력하세요"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button style={styles.subscribeBtn}>구독하기</button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  heroSection: { minHeight: "100vh", background: "radial-gradient(ellipse at center, #3A2A1E 0%, #1C1410 70%)", display: "flex", flexDirection: "column" as const },
  heroBadges: { display: "flex", justifyContent: "space-between", padding: "40px 40px 0" },
  badge: { fontSize: 13, color: "#D9C8B8", border: "1px solid #4A3B2E", borderRadius: 20, padding: "8px 16px" },
  heroContent: { flex: 1, display: "flex", flexDirection: "column" as const, justifyContent: "center", padding: "0 40px", maxWidth: 900 },
  heroTitle: { fontSize: 56, fontWeight: 800, color: "#FFFFFF", lineHeight: 1.3, marginBottom: 24, wordBreak: "keep-all" as const },
  heroDesc: { fontSize: 17, color: "#C9BCAE", marginBottom: 36, lineHeight: 1.6, wordBreak: "keep-all" as const },
  heroActions: { display: "flex", gap: 12 },
  primaryBtn: { padding: "16px 36px", fontSize: 16, fontWeight: 700, background: "#C16A45", border: "none", borderRadius: 30, color: "#FFFFFF", cursor: "pointer" },
  secondaryBtn: { padding: "16px 36px", fontSize: 16, fontWeight: 700, background: "transparent", border: "1.5px solid #6B5B4C", borderRadius: 30, color: "#FFFFFF", cursor: "pointer" },
  scrollHint: { textAlign: "center" as const, color: "#8A7A6A", fontSize: 13, paddingBottom: 24 },

  featuresSection: { background: "#FAF6F1", padding: "80px 40px", maxWidth: 1200, margin: "0 auto" },
  featuresHeader: { display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 40, flexWrap: "wrap" as const, gap: 20 },
  featuresEyebrow: { fontSize: 13, fontWeight: 700, color: "#E08A5B", marginBottom: 8 },
  featuresTitle: { fontSize: 36, fontWeight: 800, color: "#2A2A2A", lineHeight: 1.3 },
  featuresDesc: { fontSize: 15, color: "#8A7A6A", maxWidth: 300, textAlign: "right" as const },
  featureTabs: { display: "flex", gap: 8, marginBottom: 32, flexWrap: "wrap" as const },
  featureTab: { display: "flex", alignItems: "center", gap: 8, padding: "10px 20px", borderRadius: 999, fontSize: 14, fontWeight: 700, transition: "all 0.15s", background: "transparent", color: "#2A2A2A", border: "1.5px solid rgba(30,26,23,0.10)", cursor: "pointer" },
  featureTabActive: { background: "#2A2A2A", color: "#FFFFFF", border: "none" },
  emptyFeature: { borderRadius: 16, padding: "48px 24px", textAlign: "center" as const, background: "#FFFFFF", boxShadow: "0 2px 24px rgba(30,26,23,0.07)" },
  emptyFeatureText: { fontSize: 15, color: "#8A7A6A", marginBottom: 20 },
  emptyFeatureBtn: { padding: "12px 28px", borderRadius: 999, fontSize: 14, fontWeight: 700, color: "#FFFFFF", background: "#C16A45", border: "none", cursor: "pointer" },
  featureCards: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 },
  medCard: { borderRadius: 16, padding: 24, background: "#7A3728" },
  medCardEyebrow: { fontSize: 11, fontWeight: 700, marginBottom: 12, opacity: 0.6, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: "#FAF6F1" },
  medCardBig: { fontSize: 32, fontWeight: 800, marginBottom: 4, color: "#FFFFFF" },
  medCardDesc: { fontSize: 13, marginBottom: 24, opacity: 0.55, color: "#FAF6F1" },
  medList: { display: "flex", flexDirection: "column" as const, gap: 14 },
  medRow: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  medRowLeft: { display: "flex", alignItems: "center", gap: 12 },
  medDotDone: { width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#8FAE8B" },
  medDotWait: { width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 11, fontWeight: 700, background: "rgba(255,255,255,0.12)", color: "#FAF6F1" },
  medRowName: { fontSize: 13, fontWeight: 600, color: "#FFFFFF" },
  medRowNameDone: { color: "rgba(255,255,255,0.45)" },
  medRowNote: { fontSize: 11, opacity: 0.45, color: "#FAF6F1" },
  medRowStatus: { fontSize: 12, flexShrink: 0, color: "rgba(255,255,255,0.6)" },
  drugCard: { borderRadius: 16, padding: 24, display: "flex", flexDirection: "column" as const, background: "#FFFFFF", boxShadow: "0 2px 24px rgba(30,26,23,0.07)" },
  drugCardTop: { display: "flex", alignItems: "center", gap: 8, marginBottom: 20 },
  drugCardIconBox: { width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(224,138,91,0.10)" },
  drugCardPeriodTitle: { fontSize: 15, fontWeight: 800, color: "#2A2A2A" },
  drugCardNote: { fontSize: 14, color: "#8A7A6A" },
  periodBig: { fontSize: 22, fontWeight: 800, color: "#2A2A2A", marginBottom: 16 },
  periodMedList: { display: "flex", flexDirection: "column" as const, gap: 10 },
  periodMedRow: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, paddingTop: 10, borderTop: "1px solid #F0EBE3" },
  periodMedName: { fontSize: 14, fontWeight: 700, color: "#2A2A2A" },
  periodMedNameDone: { color: "#8A7A6A", textDecoration: "line-through" as const },
  periodMedTime: { fontSize: 12, fontWeight: 400, color: "#8A7A6A" },
  periodMedBtn: { flexShrink: 0, padding: "6px 14px", borderRadius: 999, fontSize: 12, fontWeight: 700, color: "#FFFFFF", background: "#8FAE8B", border: "none", cursor: "pointer" },
  periodMedBtnDone: { background: "rgba(30,26,23,0.10)", color: "#8A7A6A", cursor: "default" },

  valueSection: { display: "grid", gridTemplateColumns: "1fr 1fr", minHeight: 500 },
  valueImageCol: { position: "relative" as const },
  valueImage: { width: "100%", height: "100%", objectFit: "cover" as const, display: "block" },
  valueImageOverlay: { position: "absolute" as const, inset: 0, background: "linear-gradient(to top, rgba(30,26,23,0.88) 0%, rgba(30,26,23,0.15) 65%)" },
  valueImageCaption: { position: "absolute" as const, bottom: 0, left: 0, padding: 40 },
  valueImageBadge: { display: "inline-block", padding: "6px 12px", borderRadius: 999, fontSize: 11, fontWeight: 600, marginBottom: 16, background: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.85)" },
  valueImageTitle: { fontSize: 28, fontWeight: 800, lineHeight: 1.4, color: "#FFFFFF" },
  valueTextCol: { display: "flex", flexDirection: "column" as const, justifyContent: "center", padding: "56px 64px", background: "#EDE8DF" },
  valueTitle: { fontSize: 28, fontWeight: 800, color: "#2A2A2A", marginBottom: 16 },
  valueDesc: { fontSize: 15, lineHeight: 1.6, color: "#8A7A6A", marginBottom: 32 },
  valueItem: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 },
  valueCheck: { width: 24, height: 24, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, background: "#8FAE8B" },
  valueItemText: { fontSize: 14, color: "#2A2A2A" },
  valueBtn: { display: "flex", alignItems: "center", gap: 8, padding: "14px 28px", borderRadius: 999, color: "#FFFFFF", fontWeight: 700, fontSize: 15, background: "#C16A45", border: "none", cursor: "pointer", marginTop: 16, width: "fit-content" },

  dashPreviewSection: { padding: "80px 40px", maxWidth: 1200, margin: "0 auto", background: "#FAF6F1" },
  dashPreviewTitle: { fontSize: 32, fontWeight: 800, color: "#2A2A2A", marginBottom: 12 },
  dashPreviewDesc: { fontSize: 15, color: "#8A7A6A", marginBottom: 40 },
  dashPreviewGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 },
  dashCard: { borderRadius: 16, overflow: "hidden", background: "#FFFFFF", boxShadow: "0 4px 28px rgba(30,26,23,0.09)" },
  dashCardPhoto: { width: "100%", height: 176, objectFit: "cover" as const, display: "block" },
  dashCardBody: { padding: 20 },
  dashCardTag: { fontSize: 12, fontWeight: 700, color: "#8A7A6A", marginBottom: 12 },
  dashDonutRow: { display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 8 },
  dashDonutLabel: { fontSize: 11, color: "#8A7A6A" },
  dashDonutValue: { fontSize: 24, fontWeight: 800, color: "#2A2A2A" },
  dashProgressTrack: { height: 8, borderRadius: 999, overflow: "hidden", background: "#EDE8DF" },
  dashProgressFill: { height: "100%", width: "50%", borderRadius: 999, background: "#C16A45" },
  dashScoreRow: { display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 },
  dashScoreValue: { fontSize: 32, fontWeight: 800, color: "#2A2A2A" },
  dashScoreLabel: { fontSize: 12, color: "#8A7A6A", marginBottom: 12 },
  dashStreakRow: { display: "flex", alignItems: "center", gap: 6 },
  dashStreakText: { fontSize: 13, color: "#2A2A2A" },
  dashVisitLabel: { fontSize: 12, color: "#8A7A6A", marginBottom: 4 },
  dashVisitName: { fontSize: 17, fontWeight: 800, color: "#2A2A2A", marginBottom: 2 },
  dashVisitMeta: { fontSize: 13, color: "#8A7A6A", marginBottom: 16 },
  dashVisitBtn: { width: "100%", padding: "10px 0", borderRadius: 999, fontSize: 13, fontWeight: 700, color: "#FFFFFF", background: "#C16A45", border: "none", cursor: "pointer" },

  trustSection: { background: "#1C1410", padding: "100px 40px", textAlign: "center" as const },
  trustBadge: { display: "inline-block", fontSize: 13, color: "#D9C8B8", border: "1px solid #4A3B2E", borderRadius: 20, padding: "8px 16px", marginBottom: 24 },
  trustTitle: { fontSize: 36, fontWeight: 800, color: "#FFFFFF", lineHeight: 1.4 },
  newsletterSection: { background: "#F5EDE4", padding: "100px 40px", textAlign: "center" as const },
  mailIcon: { width: 64, height: 64, borderRadius: 16, background: "#F0DDCB", color: "#C16A45", fontSize: 26, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" },
  newsletterTitle: { fontSize: 28, fontWeight: 800, color: "#2A2A2A", marginBottom: 16 },
  newsletterDesc: { fontSize: 14, color: "#8A7A6A", marginBottom: 32, lineHeight: 1.6 },
  newsletterForm: { display: "flex", justifyContent: "center", gap: 8, maxWidth: 500, margin: "0 auto" },
  emailInput: { flex: 1, padding: "14px 20px", borderRadius: 30, border: "1px solid #E0D3C4", fontSize: 14, outline: "none" },
  subscribeBtn: { padding: "14px 28px", borderRadius: 30, background: "#2A211B", color: "#FFFFFF", border: "none", fontWeight: 700, cursor: "pointer" },
};
