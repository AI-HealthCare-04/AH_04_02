import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import NavBar from "../components/NavBar";
import { dedupeSourceRefs, formatSourceRef, type RecordResult } from "../api/records";
import { C } from "../theme";

const STATIC_DISCLAIMER =
  "이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.";

export default function Result() {
  const navigate = useNavigate();
  const location = useLocation();
  const result = (location.state as { result?: RecordResult } | null)?.result;

  useEffect(() => {
    // Processing.tsx를 거치지 않고 직접 들어온 경우 (새로고침 등) — 다시 시작
    if (!result) navigate("/upload", { replace: true });
  }, [result, navigate]);

  if (!result) {
    return null;
  }

  if (result.status === "review_required") {
    return (
      <div style={styles.page}>
        <NavBar isLoggedIn userName="김건강" />
        <main style={{ ...styles.main, textAlign: "center" as const, padding: "120px 24px" }}>
          <p style={{ fontSize: 15, color: C.warningText, marginBottom: 20 }}>
            일부 항목의 인식 정확도가 낮아 확인이 필요해요.
          </p>
          <button style={styles.chatBtn} onClick={() => navigate(`/records/${result.record_id}/review`)}>
            처방전 확인하러 가기
          </button>
        </main>
      </div>
    );
  }

  if (result.status === "failed" || !result.guide) {
    return (
      <div style={styles.page}>
        <NavBar isLoggedIn userName="김건강" />
        <main style={{ ...styles.main, textAlign: "center" as const, padding: "120px 24px" }}>
          <p style={{ fontSize: 15, color: C.danger, marginBottom: 20 }}>
            {result.failure_reason || "결과를 생성하지 못했어요."}
          </p>
          <button style={styles.chatBtn} onClick={() => navigate("/upload")}>
            다시 업로드하기
          </button>
        </main>
      </div>
    );
  }

  const { guide, medications } = result;

  return (
    <div style={styles.page}>
      <NavBar isLoggedIn userName="김건강" />

      <main style={styles.main}>
        {/* 헤더 */}
        <div style={styles.header}>
          <div style={styles.headerTop}>
            <h1 style={styles.title}>복약 안내 결과</h1>
            <span style={styles.badge}>✓ 분석 완료</span>
          </div>
        </div>

        {/* 면책 고지 */}
        <div style={styles.disclaimer}>
          <p style={styles.disclaimerText}>⚠️ {STATIC_DISCLAIMER}</p>
        </div>

        {/* 2단 레이아웃 */}
        <div style={styles.grid}>
          {/* 좌측: OCR 결과 */}
          <div style={styles.colLeft}>
            <div style={styles.card}>
              <h2 style={styles.cardTitle}>📄 OCR 인식 결과</h2>
              {medications.map((med, i) => (
                <div key={i} style={styles.medItem}>
                  <div style={styles.medInfo}>
                    <p style={styles.medName}>{med.drug_name}</p>
                    <p style={styles.medDosage}>{med.dosage} · {med.frequency}</p>
                    {med.review_required && (
                      <p style={{ fontSize: 11, color: C.warningText, marginTop: 2 }}>
                        확인 필요 (인식 정확도 {Math.round(med.confidence * 100)}%)
                      </p>
                    )}
                  </div>
                  <span style={styles.medBadge}>{med.drug_class}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 우측: 진단 기반 안내 + 가이드 */}
          <div style={styles.colRight}>
            <div style={{ ...styles.card, ...styles.statusCard }}>
              <h2 style={styles.cardTitle}>🔍 진단 기반 안내</h2>
              <p style={styles.statusText}>{guide.lifestyle_guide.diagnosis}</p>
              <p style={styles.statusNote}>진단명 + 처방 약물 기반 분석 결과입니다.</p>
            </div>

            <div style={styles.card}>
              <h2 style={styles.cardTitle}>💊 맞춤 복약 지도</h2>
              {guide.medication_guide.drugs.map((drug, i) => {
                // [7/9] dosage_text(stub) / medication_guide(실제) 중 있는 걸 씀
                const guideText = drug.medication_guide ?? drug.dosage_text ?? "";
                // caution(stub, 단일 문자열) / precautions(실제, 배열) 중 있는 걸 씀
                const cautionText = drug.precautions?.length ? drug.precautions.join(" ") : drug.caution;
                return (
                  <div key={i} style={styles.guideItem}>
                    <p style={styles.guideLabel}>💊 {drug.drug_name}</p>
                    <p style={styles.guideText}>{guideText}</p>
                    {cautionText && (
                      <p style={{ ...styles.guideText, color: C.terracotta, marginTop: 4 }}>
                        ⚠️ {cautionText}
                      </p>
                    )}
                    {drug.review_required && (
                      <p style={{ fontSize: 11, color: C.warningText, marginTop: 4 }}>
                        AI 검토 필요 — 참고자료 인용이 부족하거나 OCR 인식 신뢰도가 낮아요.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            <div style={styles.card}>
              <h2 style={styles.cardTitle}>🌿 생활습관 개선 가이드</h2>
              {guide.lifestyle_guide.guides?.length ? (
                // [7/9] 실제 파이프라인 모양 — 약별 생활습관 안내 전문
                guide.lifestyle_guide.guides.map((text, i) => (
                  <div key={i} style={styles.guideItem}>
                    <p style={styles.guideLabel}>🌿 안내 {i + 1}</p>
                    <p style={styles.guideText}>{text}</p>
                  </div>
                ))
              ) : (
                // stub 모양 — 구조화된 diet/exercise
                <>
                  <div style={styles.guideItem}>
                    <p style={styles.guideLabel}>🥗 식이</p>
                    <p style={styles.guideText}>
                      피해야 할 음식: {guide.lifestyle_guide.diet?.avoid.join(", ") || "없음"}
                    </p>
                    {!!guide.lifestyle_guide.diet?.drug_specific.length && (
                      <p style={styles.guideText}>
                        {guide.lifestyle_guide.diet.drug_specific.join(" ")}
                      </p>
                    )}
                  </div>
                  <div style={styles.guideItem}>
                    <p style={styles.guideLabel}>🏃 운동</p>
                    <p style={styles.guideText}>
                      {guide.lifestyle_guide.exercise?.type} · {guide.lifestyle_guide.exercise?.duration} ·{" "}
                      {guide.lifestyle_guide.exercise?.intensity}
                    </p>
                  </div>
                </>
              )}
              {guide.source_refs.length > 0 && (
                <div style={styles.sources}>
                  <p style={styles.sourcesText}>
                    출처: {dedupeSourceRefs(guide.source_refs).map(formatSourceRef).join(", ")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 복약·생활 가이드(탭 화면) 이동 버튼 */}
        <button style={styles.guideCtaBtn} onClick={() => navigate(`/records/${result.record_id}/guide`)}>
          📋 가이드 생성하기
        </button>

        {/* 챗봇 이동 버튼 */}
        <button style={styles.chatBtn} onClick={() => navigate("/chat", { state: { diagnosis: guide.lifestyle_guide.diagnosis } })}>
          💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 1100, margin: "0 auto", padding: "40px 24px 80px" },
  header: { marginBottom: 20 },
  headerTop: { display: "flex", alignItems: "center", gap: 12, marginBottom: 6 },
  title: { fontSize: 24, fontWeight: 700, color: C.dark },
  badge: { background: `${C.success}25`, color: C.successText, fontSize: 13, fontWeight: 600, padding: "4px 12px", borderRadius: 99 },
  disclaimer: { background: `${C.terracotta}10`, border: `1px solid ${C.terracotta}25`, borderRadius: 10, padding: "12px 16px", marginBottom: 24 },
  disclaimerText: { fontSize: 13, color: C.terracotta, lineHeight: 1.6 },
  grid: { display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 20, marginBottom: 24 },
  colLeft: { display: "flex", flexDirection: "column" as const, gap: 16 },
  colRight: { display: "flex", flexDirection: "column" as const, gap: 16 },
  card: { background: C.white, border: "1px solid rgba(30,26,23,0.12)", borderRadius: 14, padding: "20px" },
  statusCard: { background: `${C.terracotta}10`, border: `1px solid ${C.terracotta}25` },
  cardTitle: { fontSize: 15, fontWeight: 700, color: C.dark, marginBottom: 16, display: "flex", alignItems: "center", gap: 6 },
  medItem: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "10px 0", borderTop: "1px solid " + C.bubbleBg },
  medInfo: {},
  medName: { fontSize: 14, fontWeight: 600, color: C.dark, marginBottom: 3 },
  medDosage: { fontSize: 12, color: C.muted },
  medBadge: { fontSize: 11, background: C.bubbleBg, color: C.terracotta, padding: "3px 8px", borderRadius: 99, whiteSpace: "nowrap" as const },
  statusText: { fontSize: 16, fontWeight: 700, color: C.terracotta, marginBottom: 6 },
  statusNote: { fontSize: 12, color: C.muted },
  guideItem: { padding: "10px 0", borderTop: "1px solid " + C.bubbleBg },
  guideLabel: { fontSize: 13, fontWeight: 600, color: C.dark, marginBottom: 4 },
  guideText: { fontSize: 13, color: C.dark, lineHeight: 1.6 },
  sources: { marginTop: 12, paddingTop: 10, borderTop: "1px solid " + C.bubbleBg },
  sourcesText: { fontSize: 12, color: C.muted },
  guideCtaBtn: { width: "100%", padding: "16px", fontSize: 15, fontWeight: 700, background: C.dark, color: C.white, border: "none", borderRadius: 12, cursor: "pointer", marginBottom: 12 },
  chatBtn: { width: "100%", padding: "16px", fontSize: 15, fontWeight: 600, background: C.terracotta, color: C.white, border: "none", borderRadius: 12, cursor: "pointer" },
};
