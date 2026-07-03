import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";

type Level = "normal" | "mild" | "severe";
type YesNo = "yes" | "no";

export default function Check() {
  const navigate = useNavigate();
  const [cognitive, setCognitive] = useState<Level>("normal");
  const [mobility, setMobility] = useState<Level>("normal");
  const [vision, setVision] = useState<Level>("normal");
  const [awareness, setAwareness] = useState<YesNo>("yes");
  const [willingness, setWillingness] = useState<YesNo>("yes");

  const handleSubmit = () => {
    navigate("/select");
  };

  const levelOptions: { key: Level; label: string }[] = [
    { key: "normal", label: "정상" },
    { key: "mild", label: "경미" },
    { key: "severe", label: "심각" },
  ];

  const yesNoOptions: { key: YesNo; label: string }[] = [
    { key: "yes", label: "예" },
    { key: "no", label: "아니오" },
  ];

  return (
    <div style={styles.page}>
      <NavBar isLoggedIn userName="김건강" />
      <main style={styles.main}>
        <h1 style={styles.title}>자가진단 체크리스트</h1>
        <p style={styles.subtitle}>대상자의 현재 상태를 입력하면 적합한 도움 수준을 판정합니다.</p>

        <div style={styles.card}>
          <p style={styles.groupLabel}>기능 수준 평가</p>
          <SegmentRow label="인지 수준" value={cognitive} onChange={setCognitive} options={levelOptions} />
          <SegmentRow label="거동 수준" value={mobility} onChange={setMobility} options={levelOptions} />
          <SegmentRow label="시력 수준" value={vision} onChange={setVision} options={levelOptions} last />
        </div>

        <div style={styles.card}>
          <p style={styles.groupLabel}>복약 인식 및 의지</p>
          <SegmentRow label="복용해야 함을 인지하는가" value={awareness} onChange={setAwareness} options={yesNoOptions} />
          <SegmentRow label="복용 의지가 있는가" value={willingness} onChange={setWillingness} options={yesNoOptions} last />
        </div>

        <button style={styles.submitBtn} onMouseDown={(e) => e.preventDefault()} onClick={handleSubmit}>
          저장 및 평가하기
        </button>
      </main>
    </div>
  );
}

interface SegmentRowProps<T extends string> {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { key: T; label: string }[];
  last?: boolean;
}

function SegmentRow<T extends string>({ label, value, onChange, options, last }: SegmentRowProps<T>) {
  return (
    <div style={{ ...styles.row, ...(last ? { borderBottom: "none" } : {}) }}>
      <span style={styles.rowLabel}>{label}</span>
      <div style={styles.segmentGroup}>
        {options.map((opt) => {
          const isActive = value === opt.key;
          return (
            <button
              key={opt.key}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onChange(opt.key)}
              style={{
                padding: "10px 20px",
                borderRadius: 20,
                borderWidth: 1,
                borderStyle: "solid",
                borderColor: isActive ? "#7C8B5D" : "#D9CFC7",
                background: isActive ? "#7C8B5D" : "#F5F0EA",
                color: isActive ? "#FFFFFF" : "#888888",
                fontWeight: 600,
                fontSize: 13,
                cursor: "pointer",
                outline: "none",
                boxShadow: "none",
                fontFamily: "inherit",
              }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 700, margin: "0 auto", padding: "32px 20px 60px" },
  title: { fontSize: 26, fontWeight: 800, color: "#2A2A2A", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#888888", marginBottom: 28, wordBreak: "keep-all" as const },
  card: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 16, padding: "24px 28px", marginBottom: 20 },
  groupLabel: { fontSize: 13, color: "#888888", fontWeight: 600, marginBottom: 16 },
  row: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 0", borderBottom: "1px solid #F5F0EA", flexWrap: "wrap" as const, gap: 10 },
  rowLabel: { fontSize: 15, color: "#2A2A2A", fontWeight: 500 },
  segmentGroup: { display: "flex", gap: 8 },
  submitBtn: { width: "100%", padding: "16px 0", borderRadius: 12, background: "#C16A45", color: "#FFFFFF", border: "none", fontWeight: 700, fontSize: 16, cursor: "pointer", outline: "none" },
};
