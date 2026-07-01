import { useNavigate } from "react-router-dom";

// TODO: 실제 API 응답 데이터로 대체
const MOCK = {
  uploadedBy: "보호자 김영희님",
  record: { hospital: "서울내과의원", date: "2026.06.30", days: 7 },
  medications: [
    { name: "아목시실린 500mg", dosage: "1일 3회 · 식후 30분", drugClass: "항생제" },
    { name: "타이레놀 650mg", dosage: "1일 3회 · 필요시", drugClass: "해열진통" },
    { name: "판토프라졸 40mg", dosage: "1일 1회 · 식전", drugClass: "위장약" },
  ],
  patientStatus: "당뇨 관리 단계 · 혈당 변동 주의군",
  medicationGuide: [
    { label: "복용 시간", icon: "⏰", text: "아목시실린과 판토프라졸은 식사와 함께, 타이레놀은 통증이 있을 때만 복용하세요." },
    { label: "주의사항", icon: "⚠️", text: "항생제는 증상이 나아도 처방 기간 동안 꾸준히 복용해야 합니다. 임의로 중단하지 마세요." },
    { label: "약물 상호작용", icon: "💊", text: "타이레놀과 아목시실린은 함께 복용해도 안전합니다." },
  ],
  lifestyleGuide: [
    { label: "식이", icon: "🥗", text: "짠 음식과 단 음식을 줄이고, 채소와 통곡물 위주로 드세요. 칼륨 보충을 위해 바나나, 시금치를 권장합니다." },
    { label: "운동", icon: "🚶", text: "하루 30분 가벼운 걷기를 권장합니다. 격렬한 운동은 혈당 변동을 유발할 수 있으니 주의하세요." },
    { label: "수면", icon: "😴", text: "규칙적인 수면 시간을 유지하세요. 수면 부족은 혈당 조절을 어렵게 합니다." },
  ],
  sources: ["식약처 e약은요", "HIRA 질환별 통계"],
};

export default function Result() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>

      <main style={styles.main}>
        {/* 헤더 */}
        <div style={styles.header}>
          <div style={styles.headerTop}>
            <h1 style={styles.title}>복약 안내 결과</h1>
            <span style={styles.badge}>✓ 분석 완료</span>
          </div>
          <p style={styles.subtitle}>
            2026.06.30 · {MOCK.uploadedBy}이 등록하였습니다
          </p>
        </div>

        {/* 면책 고지 */}
        <div style={styles.disclaimer}>
          <p style={styles.disclaimerText}>
            ⚠️ 이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
          </p>
        </div>

        {/* 2단 레이아웃 */}
        <div style={styles.grid}>
          {/* 좌측: OCR 결과 */}
          <div style={styles.colLeft}>
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>📄 OCR 인식 결과</h2>
              <div style={styles.infoBox}>
                <div style={styles.infoRow}><span style={styles.infoKey}>병원</span><span style={styles.infoVal}>{MOCK.record.hospital}</span></div>
                <div style={styles.infoRow}><span style={styles.infoKey}>처방일</span><span style={styles.infoVal}>{MOCK.record.date}</span></div>
                <div style={styles.infoRow}><span style={styles.infoKey}>조제일수</span><span style={styles.infoVal}>{MOCK.record.days}일</span></div>
              </div>
              {MOCK.medications.map((med, i) => (
                <div key={i} style={styles.medItem}>
                  <div style={styles.medInfo}>
                    <p style={styles.medName}>{med.name}</p>
                    <p style={styles.medDosage}>{med.dosage}</p>
                  </div>
                  <span style={styles.medBadge}>{med.drugClass}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 우측: 예측된 환자상태 + 가이드 */}
          <div style={styles.colRight}>
            {/* 예측된 환자 상태 */}
            <div style={{ ...styles.card, ...styles.statusCard }}>
              <h2 style={styles.cardTitle}>🔍 예측된 환자 상태</h2>
              <p style={styles.statusText}>{MOCK.patientStatus}</p>
              <p style={styles.statusNote}>진단명 + 처방 약물 기반 분석 결과입니다.</p>
            </div>

            {/* 맞춤 복약 지도 */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>💊 맞춤 복약 지도</h2>
              {MOCK.medicationGuide.map((g, i) => (
                <div key={i} style={styles.guideItem}>
                  <p style={styles.guideLabel}>{g.icon} {g.label}</p>
                  <p style={styles.guideText}>{g.text}</p>
                </div>
              ))}
            </div>

            {/* 생활습관 개선 가이드 */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>🌿 생활습관 개선 가이드</h2>
              {MOCK.lifestyleGuide.map((g, i) => (
                <div key={i} style={styles.guideItem}>
                  <p style={styles.guideLabel}>{g.icon} {g.label}</p>
                  <p style={styles.guideText}>{g.text}</p>
                </div>
              ))}
              <div style={styles.sources}>
                <p style={styles.sourcesText}>출처: {MOCK.sources.join(", ")}</p>
              </div>
            </div>
          </div>
        </div>

        {/* 챗봇 이동 버튼 */}
        <button style={styles.chatBtn} onClick={() => navigate("/chat")}>
          💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  nav: { padding: "16px 40px", background: "#FFFFFF", borderBottom: "1px solid #EEE6DC", display: "flex", alignItems: "center" },
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45" },
  main: { maxWidth: 1100, margin: "0 auto", padding: "40px 24px 80px" },
  header: { marginBottom: 20 },
  headerTop: { display: "flex", alignItems: "center", gap: 12, marginBottom: 6 },
  title: { fontSize: 24, fontWeight: 700, color: "#2A2A2A" },
  badge: { background: "#E8F5E9", color: "#388E3C", fontSize: 13, fontWeight: 600, padding: "4px 12px", borderRadius: 99 },
  subtitle: { fontSize: 13, color: "#888888" },
  disclaimer: { background: "#FFF8F4", border: "1px solid #F0E5D8", borderRadius: 10, padding: "12px 16px", marginBottom: 24 },
  disclaimerText: { fontSize: 13, color: "#C16A45", lineHeight: 1.6 },
  grid: { display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 20, marginBottom: 24 },
  colLeft: { display: "flex", flexDirection: "column" as const, gap: 16 },
  colRight: { display: "flex", flexDirection: "column" as const, gap: 16 },
  card: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 14, padding: "20px" },
  statusCard: { background: "#FFF8F4", border: "1px solid #F0E5D8" },
  cardTitle: { fontSize: 15, fontWeight: 700, color: "#2A2A2A", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 },
  infoBox: { background: "#FAF6F1", borderRadius: 8, padding: "12px 14px", marginBottom: 14 },
  infoRow: { display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13 },
  infoKey: { color: "#888888" },
  infoVal: { fontWeight: 600, color: "#2A2A2A" },
  medItem: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "10px 0", borderTop: "1px solid #F5F0EB" },
  medInfo: {},
  medName: { fontSize: 14, fontWeight: 600, color: "#2A2A2A", marginBottom: 3 },
  medDosage: { fontSize: 12, color: "#888888" },
  medBadge: { fontSize: 11, background: "#F0E5D8", color: "#C16A45", padding: "3px 8px", borderRadius: 99, whiteSpace: "nowrap" as const },
  statusText: { fontSize: 16, fontWeight: 700, color: "#C16A45", marginBottom: 6 },
  statusNote: { fontSize: 12, color: "#AAAAAA" },
  guideItem: { padding: "10px 0", borderTop: "1px solid #F5F0EB" },
  guideLabel: { fontSize: 13, fontWeight: 600, color: "#4A4A4A", marginBottom: 4 },
  guideText: { fontSize: 13, color: "#555555", lineHeight: 1.6 },
  sources: { marginTop: 12, paddingTop: 10, borderTop: "1px solid #F5F0EB" },
  sourcesText: { fontSize: 12, color: "#AAAAAA" },
  chatBtn: { width: "100%", padding: "16px", fontSize: 15, fontWeight: 600, background: "#C16A45", color: "#FFFFFF", border: "none", borderRadius: 12, cursor: "pointer" },
};
