import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getMedicalRecordStatus, retryMedicalRecord } from "../api/medicalRecords";

const steps = [
  { id: 1, label: "OCR 인식 중", desc: "처방전에서 약품 정보를 읽고 있어요" },
  { id: 2, label: "상태 예측 중", desc: "진단명과 약물을 바탕으로 환자 상태를 분석해요" },
  { id: 3, label: "맞춤 가이드 생성 중", desc: "복약 안내와 생활습관 가이드를 만들고 있어요" },
];

const POLL_INTERVAL_MS = 2000;

export default function Processing() {
  const navigate = useNavigate();
  const location = useLocation();
  const recordId = (location.state as { recordId?: number } | null)?.recordId;

  const [current, setCurrent] = useState(0);
  const [failed, setFailed] = useState(false);
  const [failureReason, setFailureReason] = useState("");
  const [retrying, setRetrying] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const visualRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // recordId 없이 직접 이 화면으로 들어온 경우 업로드부터 다시
    if (!recordId) {
      navigate("/upload");
      return;
    }

    // 시각적 진행 애니메이션 (실제 단계와 무관하게 기대감을 주는 용도)
    visualRef.current = setInterval(() => {
      setCurrent((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 1800);

    // 실제 상태 polling — 완료/실패 여부는 이 결과로만 판단
    const poll = async () => {
      try {
        const data = await getMedicalRecordStatus(recordId);

        if (data.status === "completed" || data.status === "review_required") {
          if (pollRef.current) clearInterval(pollRef.current);
          if (visualRef.current) clearInterval(visualRef.current);
          setCurrent(steps.length - 1);
          setTimeout(() => navigate("/result", { state: { recordId } }), 600);
        } else if (data.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          if (visualRef.current) clearInterval(visualRef.current);
          setFailed(true);
          setFailureReason(data.failure_reason ?? "처리 중 문제가 발생했어요.");
        }
        // "processing"이면 계속 polling
      } catch {
        // 네트워크 일시 오류는 다음 polling에서 재시도 (여기서 바로 실패 처리하지 않음)
      }
    };

    poll();
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (visualRef.current) clearInterval(visualRef.current);
    };
  }, [recordId, navigate]);

  const handleRetry = async () => {
    if (!recordId || retrying) return;
    setRetrying(true);
    try {
      await retryMedicalRecord(recordId);
      setFailed(false);
      setCurrent(0);
      // useEffect가 다시 polling을 태우도록 페이지 자체를 재진입시킴
      navigate("/processing", { state: { recordId }, replace: true });
    } catch {
      setRetrying(false);
    }
  };

  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>💊 건강동행</span>
      </nav>
      <main style={styles.main}>
        <div style={styles.card}>
          {failed ? (
            <>
              <div style={styles.spinner}>⚠️</div>
              <h1 style={styles.title}>처리 중 문제가 발생했어요</h1>
              <p style={styles.subtitle}>{failureReason}</p>
              <button
                style={styles.retryBtn}
                onClick={handleRetry}
                disabled={retrying}
              >
                {retrying ? "다시 시도 중..." : "다시 시도하기"}
              </button>
            </>
          ) : (
            <>
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
            </>
          )}

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
  nav: { padding: "16px 40px", background: "#FFFFFF", borderBottom: "1px solid #EEE6DC", display: "flex", alignItems: "center" },
  logo: { fontSize: 20, fontWeight: 700, color: "#C16A45" },
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
  retryBtn: { padding: "14px 36px", fontSize: 15, fontWeight: 700, background: "#C16A45", color: "#FFFFFF", border: "none", borderRadius: 10, cursor: "pointer", marginBottom: 32 },
};
