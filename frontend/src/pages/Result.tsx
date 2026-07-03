import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  getMedicalRecord,
  getGuide,
  type MedicalRecordDetail,
  type GuideResult,
} from "../api/medicalRecords";

export default function Result() {
  const navigate = useNavigate();
  const location = useLocation();
  const recordId = (location.state as { recordId?: number } | null)?.recordId;

  const [record, setRecord] = useState<MedicalRecordDetail | null>(null);
  const [guide, setGuide] = useState<GuideResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!recordId) {
      navigate("/upload");
      return;
    }

    const load = async () => {
      try {
        const [recordData, guideData] = await Promise.all([
          getMedicalRecord(recordId),
          getGuide(recordId),
        ]);
        setRecord(recordData);
        setGuide(guideData);
      } catch (err: unknown) {
        const message =
          (err as { response?: { data?: { message?: string } } })?.response
            ?.data?.message ??
          "결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [recordId, navigate]);

  if (loading) {
    return (
      <div style={styles.page}>
        <nav style={styles.nav}>
          <span style={styles.logo}>💊 건강동행</span>
        </nav>
        <main style={{ ...styles.main, textAlign: "center" as const, padding: "120px 24px" }}>
          <p style={{ fontSize: 15, color: "#888888" }}>결과를 불러오는 중이에요...</p>
        </main>
      </div>
    );
  }

  if (error || !record || !guide) {
    return (
      <div style={styles.page}>
        <nav style={styles.nav}>
          <span style={styles.logo}>💊 건강동행</span>
        </nav>
        <main style={{ ...styles.main, textAlign: "center" as const, padding: "120px 24px" }}>
          <p style={{ fontSize: 15, color: "#D94F4F", marginBottom: 20 }}>
            {error || "결과를 찾을 수 없어요."}
          </p>
          <button style={styles.chatBtn} onClick={() => navigate("/upload")}>
            다시 업로드하기
          </button>
        </main>
      </div>
    );
  }

  const generatedDate = new Date(guide.generated_at).toLocaleDateString("ko-KR");

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
          <p style={styles.subtitle}>{generatedDate} 생성됨</p>
        </div>

        {/* 면책 고지 */}
        <div style={styles.disclaimer}>
          <p style={styles.disclaimerText}>⚠️ {guide.disclaimer}</p>
        </div>

        {/* 저신뢰 OCR 확인 필요 안내 */}
        {record.status === "review_required" && (
          <div style={{ ...styles.disclaimer, background: "#FFF3E0", border: "1px solid #FFD8A8" }}>
            <p style={{ ...styles.disclaimerText, color: "#B8621B" }}>
              ⚠️ 일부 약품 정보의 인식 정확도가 낮아요. 아래 내용을 확인해 주세요.
            </p>
          </div>
        )}

        {/* 2단 레이아웃 */}
        <div style={styles.grid}>
          {/* 좌측: OCR 결과 */}
          <div style={styles.colLeft}>
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>📄 OCR 인식 결과</h2>
              {record.extracted_medications.map((med) => (
                <div key={med.medication_id} style={styles.medItem}>
                  <div style={styles.medInfo}>
                    <p style={styles.medName}>{med.drug_name}</p>
                    <p style={styles.medDosage}>{med.dosage} · {med.frequency}</p>
                    {med.confidence < 0.8 && (
                      <p style={{ fontSize: 11, color: "#D98A2B", marginTop: 2 }}>
                        확인 필요 (인식 정확도 {Math.round(med.confidence * 100)}%)
                      </p>
                    )}
                  </div>
                  <span style={styles.medBadge}>{med.drug_class}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 우측: 예측된 환자상태 + 가이드 */}
          <div style={styles.colRight}>
            {/* 예측된 환자 상태 (진단명 기반) */}
            <div style={{ ...styles.card, ...styles.statusCard }}>
              <h2 style={styles.cardTitle}>🔍 진단 기반 안내</h2>
              <p style={styles.statusText}>{guide.lifestyle_guide.diagnosis}</p>
              <p style={styles.statusNote}>진단명 + 처방 약물 기반 분석 결과입니다.</p>
            </div>

            {/* 맞춤 복약 지도 */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>💊 맞춤 복약 지도</h2>
              {guide.medication_guide.drugs.map((drug, i) => (
                <div key={i} style={styles.guideItem}>
                  <p style={styles.guideLabel}>💊 {drug.drug_name}</p>
                  <p style={styles.guideText}>{drug.dosage_text}</p>
                  {drug.caution && (
                    <p style={{ ...styles.guideText, color: "#C16A45", marginTop: 4 }}>
                      ⚠️ {drug.caution}
                    </p>
                  )}
                  {drug.guardian_check_required && (
                    <p style={{ fontSize: 12, color: "#8A7A6A", marginTop: 4 }}>
                      🧑‍🤝‍🧑 보호자 확인이 권장되는 약물이에요.
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* 생활습관 개선 가이드 */}
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>🌿 생활습관 개선 가이드</h2>
              {guide.lifestyle_guide.situational_guidance.map((g, i) => (
                <div key={i} style={styles.guideItem}>
                  <p style={styles.guideLabel}>🚶 {g.situation}</p>
                  <p style={styles.guideText}>{g.action}</p>
                </div>
              ))}
              <div style={styles.guideItem}>
                <p style={styles.guideLabel}>🥗 식이</p>
                <p style={styles.guideText}>
                  피해야 할 음식: {guide.lifestyle_guide.diet.avoid.join(", ") || "없음"}
                </p>
                {guide.lifestyle_guide.diet.drug_specific.length > 0 && (
                  <p style={styles.guideText}>
                    {guide.lifestyle_guide.diet.drug_specific.join(" ")}
                  </p>
                )}
              </div>
              <div style={styles.guideItem}>
                <p style={styles.guideLabel}>🏃 운동</p>
                <p style={styles.guideText}>
                  {guide.lifestyle_guide.exercise.type} · {guide.lifestyle_guide.exercise.duration} · {guide.lifestyle_guide.exercise.intensity}
                </p>
              </div>
              {guide.lifestyle_guide.caution.length > 0 && (
                <div style={styles.guideItem}>
                  <p style={styles.guideLabel}>⚠️ 주의사항</p>
                  {guide.lifestyle_guide.caution.map((c, i) => (
                    <p key={i} style={styles.guideText}>{c}</p>
                  ))}
                </div>
              )}
              {guide.source_refs.length > 0 && (
                <div style={styles.sources}>
                  <p style={styles.sourcesText}>
                    출처: {guide.source_refs.map((s) => s.title).join(", ")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 챗봇 이동 버튼 */}
        <button
          style={styles.chatBtn}
          onClick={() => navigate("/chat", { state: { guideResultId: guide.guide_result_id } })}
        >
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
