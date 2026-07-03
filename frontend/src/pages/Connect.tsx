import { useState } from "react";
import NavBar from "../components/NavBar";

type RelationType = "guardian" | "caregiver" | "life_support_worker" | "social_worker";

interface Connection {
  id: string;
  name: string;
  relation: string;
  status: "approved" | "pending";
}

const relationLabels: Record<RelationType, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

const initialConnections: Connection[] = [
  { id: "1", name: "김철수", relation: "보호자", status: "approved" },
  { id: "2", name: "이영희", relation: "요양보호사", status: "pending" },
];

export default function Connect() {
  const [phone, setPhone] = useState("");
  const [relationType, setRelationType] = useState<RelationType>("guardian");
  const [connections, setConnections] = useState(initialConnections);

  const handleInvite = () => {
    if (!phone) return;
    alert(`${phone}로 ${relationLabels[relationType]} 초대를 전송합니다.`);
    setPhone("");
  };

  const handleRevoke = (id: string) => {
    setConnections((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div style={styles.page}>
      <NavBar isLoggedIn userName="김건강" />
      <main style={styles.main}>
        <h1 style={styles.title}>보호자·요양보호사 연결 관리</h1>
        <p style={styles.subtitle}>복약 관리를 함께할 사람을 초대하고 관리하세요.</p>

        <div style={styles.card}>
          <h2 style={styles.cardTitle}>초대하기</h2>
          <input
            style={styles.input}
            placeholder="전화번호 (010-0000-0000)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <div style={styles.roleRow}>
            {(Object.keys(relationLabels) as RelationType[]).map((key) => {
              const isActive = relationType === key;
              return (
                <button
                  key={key}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setRelationType(key)}
                  style={{
                    flex: 1,
                    minWidth: 100,
                    padding: "10px 0",
                    borderRadius: 10,
                    borderWidth: 1,
                    borderStyle: "solid",
                    borderColor: isActive ? "#C16A45" : "#E0D3C4",
                    background: isActive ? "#C16A45" : "#F5F0EA",
                    color: isActive ? "#FFFFFF" : "#888888",
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: "pointer",
                    outline: "none",
                    boxShadow: "none",
                    fontFamily: "inherit",
                  }}
                >
                  {relationLabels[key]}
                </button>
              );
            })}
          </div>
          <button style={styles.submitBtn} onMouseDown={(e) => e.preventDefault()} onClick={handleInvite}>
            초대 전송하기
          </button>
        </div>

        <div style={styles.card}>
          <h2 style={styles.cardTitle}>연결된 사람 ({connections.length}명)</h2>
          <div style={styles.tableHeader}>
            <span style={styles.colName}>이름</span>
            <span style={styles.colRelation}>관계</span>
            <span style={styles.colStatus}>상태</span>
          </div>
          {connections.map((c) => (
            <div key={c.id} style={styles.tableRow}>
              <span style={styles.colName}>{c.name}</span>
              <span style={styles.colRelation}>{c.relation}</span>
              <span style={styles.colStatus}>
                <span style={{ ...styles.statusPill, ...(c.status === "approved" ? styles.statusApproved : styles.statusPending) }}>
                  {c.status === "approved" ? "승인됨" : "대기중"}
                </span>
              </span>
              <button style={styles.revokeBtn} onMouseDown={(e) => e.preventDefault()} onClick={() => handleRevoke(c.id)}>
                연결 해제
              </button>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { maxWidth: 700, margin: "0 auto", padding: "32px 20px 60px" },
  title: { fontSize: 26, fontWeight: 800, color: "#2A2A2A", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#888888", marginBottom: 28 },
  card: { background: "#FFFFFF", border: "1px solid #EEE6DC", borderRadius: 16, padding: 24, marginBottom: 24 },
  cardTitle: { fontSize: 16, fontWeight: 700, color: "#2A2A2A", marginBottom: 16 },
  input: { width: "100%", padding: "14px 16px", borderRadius: 10, border: "1px solid #E0D3C4", fontSize: 14, marginBottom: 14, outline: "none", boxSizing: "border-box" as const },
  roleRow: { display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" as const },
  submitBtn: { width: "100%", padding: "14px 0", borderRadius: 10, background: "#C16A45", color: "#FFFFFF", border: "none", fontWeight: 700, fontSize: 15, cursor: "pointer", outline: "none" },
  tableHeader: { display: "flex", padding: "8px 4px", borderBottom: "1px solid #EEE6DC", fontSize: 13, color: "#888888", fontWeight: 600 },
  tableRow: { display: "flex", alignItems: "center", padding: "16px 4px", borderBottom: "1px solid #F5F0EA" },
  colName: { flex: 1, fontSize: 14, fontWeight: 600, color: "#2A2A2A" },
  colRelation: { flex: 1, fontSize: 14, color: "#666666" },
  colStatus: { flex: 1 },
  statusPill: { fontSize: 12, fontWeight: 700, borderRadius: 12, padding: "4px 10px" },
  statusApproved: { background: "#E8EFE2", color: "#5C7A4A" },
  statusPending: { background: "#F0EBE3", color: "#8A7A6A" },
  revokeBtn: { padding: "8px 14px", borderRadius: 8, border: "1.5px solid #C16A45", background: "#FFFFFF", color: "#C16A45", fontWeight: 600, fontSize: 12, cursor: "pointer", outline: "none" },
};
