import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { createRecord } from "../api/records";

const steps = [
  { id: 1, label: "OCR 인식 중", desc: "처방전에서 약품 정보를 읽고 있어요" },
  { id: 2, label: "상태 예측 중", desc: "진단명과 약물을 바탕으로 환자 상태를 분석해요" },
  { id: 3, label: "맞춤 가이드 생성 중", desc: "복약 안내와 생활습관 가이드를 만들고 있어요" },
];

export default function Processing() {
  const navigate = useNavigate();
  const location = useLocation();
  const { file, patientId, caregiverId } =
    (location.state as { file?: File; patientId?: number; caregiverId?: number }) ?? {};

  const [current, setCurrent] = useState(0);
  const visualRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const runUpload = async () => {
    if (!file || !patientId) {
      navigate("/upload");
      return;
    }

    setCurrent(0);

    // 실제 단계와 무관한 시각 효과 — 응답 올 때까지 기대감만 주는 용도
    visualRef.current = setInterval(() => {
      setCurrent((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 1200);

    try {
      const result = await createRecord(patientId, file, caregiverId);
      if (visualRef.current) clearInterval(visualRef.current);
      setCurrent(steps.length - 1);
      // [7/9 변경] OCR 신뢰도와 무관하게 항상 확인 화면을 거치므로 /result 인터스티셜 없이 바로 이동
      setTimeout(() => navigate(`/records/${result.record_id}/review`), 400);
    } catch (err: unknown) {
      if (visualRef.current) clearInterval(visualRef.current);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      navigate("/ocr-error", { state: { reason: detail } });
    }
  };

  useEffect(() => {
    runUpload();
    return () => {
      if (visualRef.current) clearInterval(visualRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={styles.page}>
      <NavBar isLoggedIn userName="김건강" />
      <main style={styles.main}>
        <div style={styles.card}>
          <div style={styles.spinner}>⏳</div>
          <h1 style={styles.title}>분석을 시작할게요</h1>
          <p style={styles.subtitle}>잠시만 기다려 주세요. 보통 10초 이내에 완료돼요.</p>

          <div style={styles.steps}>
            {steps.map((step, i) => (
              <div key={step.id} style={styles.stepRow}>
                <div style={{
                  ...styles.stepDot,
                  ...(i < current ? styles.stepDone : {}),
                  ...(i === current ? styles.stepActive : {}),
                }}>
                  {i < current ? "✓" : step.id}
                </div>
                <div style={styles.stepContent}>
                  <p style={{
                    ...styles.stepLabel,
                    ...(i === current ? styles.stepLabelActive : {}),
                  }}>{step.label}</p>
                  {i === current && (
                    <p style={styles.stepDesc}>{step.desc}</p>
                  )}
                </div>
                <div style={styles.stepStatus}>
                  {i < current && <span style={styles.statusDone}>완료</span>}
                  {i === current && <span style={styles.statusActive}>진행 중</span>}
                  {i > current && <span style={styles.statusWait}>대기 중</span>}
                </div>
              </div>
            ))}
          </div>

          <div style={styles.disclaimer}>
            <p style={styles.disclaimerText}>
              ⚠️ 이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 600, margin: "0 auto", padding: "80px 24px", display: "flex", flexDirection: "column" as const, alignItems: "center" },
  card: { width: "100%", background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 20, padding: "48px 40px", textAlign: "center" as const },
  spinner: { fontSize: 48, marginBottom: 20 },
  title: { fontSize: 26, fontWeight: 700, color: "#2A2A2A", marginBottom: 10 },
  subtitle: { fontSize: 15, color: "#888888", marginBottom: 40 },
  steps: { display: "flex", flexDirection: "column" as const, gap: 16, textAlign: "left" as const, marginBottom: 36 },
  stepRow: { display: "flex", alignItems: "flex-start", gap: 16, padding: "14px 16px", background: "#FAF6F1", borderRadius: 12 },
  stepDot: { width: 32, height: 32, borderRadius: "50%", background: "#EEE6DC", color: "#AAAAAA", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 700, flexShrink: 0 },
  stepDone: { background: "#4CAF50", color: "#FFFFFF" },
  stepActive: { background: "#C16A45", color: "#FFFFFF" },
  stepContent: { flex: 1 },
  stepLabel: { fontSize: 15, fontWeight: 600, color: "#888888", marginBottom: 2 },
  stepLabelActive: { color: "#2A2A2A" },
  stepDesc: { fontSize: 13, color: "#888888", marginTop: 4 },
  stepStatus: { flexShrink: 0 },
  statusDone: { fontSize: 12, color: "#4CAF50", fontWeight: 600 },
  statusActive: { fontSize: 12, color: "#C16A45", fontWeight: 600 },
  statusWait: { fontSize: 12, color: "#CCCCCC" },
  disclaimer: { background: "#FFF8F4", border: "1px solid #F0E5D8", borderRadius: 10, padding: "12px 16px" },
  disclaimerText: { fontSize: 13, color: "#C16A45", lineHeight: 1.6 },
};
