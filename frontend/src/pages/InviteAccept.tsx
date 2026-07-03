import { useNavigate, useParams } from "react-router-dom";
import NavBar from "../components/NavBar";

export default function InviteAccept() {
  const navigate = useNavigate();
  const { token } = useParams();

  // TODO: token으로 GET 초대 정보 조회 후 아래 mock 데이터 대체
  const invite = {
    inviterName: "김건강",
    relation: "보호자",
    expiresAt: "2025.07.09 오전 10:00",
  };

  const handleAccept = () => {
    // TODO: POST /trust/invitations/{token}/accept
    navigate("/dashboard");
  };

  const handleReject = () => {
    // TODO: POST /trust/invitations/{token}/reject
    navigate("/");
  };

  return (
    <div style={styles.page}>
      <NavBar />
      <main style={styles.main}>
        <div style={styles.card}>
          <div style={styles.iconWrap}>♥</div>
          <p style={styles.label}>보호자 초대</p>
          <h1 style={styles.title}>{invite.inviterName}님이<br />{invite.relation}로 초대했어요</h1>

          <div style={styles.infoBox}>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>초대한 사람</span>
              <span style={styles.infoValue}>{invite.inviterName}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>관계</span>
              <span style={styles.infoValue}>{invite.relation}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>초대 만료</span>
              <span style={styles.infoValue}>{invite.expiresAt}</span>
            </div>
          </div>

          <div style={styles.actions}>
            <button style={styles.rejectBtn} onClick={handleReject}>거절</button>
            <button style={styles.acceptBtn} onClick={handleAccept}>수락</button>
          </div>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", background: "#FAF6F1", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  main: { display: "flex", justifyContent: "center", alignItems: "center", minHeight: "calc(100vh - 70px)", padding: 20 },
  card: { background: "#FFFFFF", borderRadius: 20, padding: "40px 36px", maxWidth: 420, width: "100%", textAlign: "center" as const, boxShadow: "0 4px 24px rgba(0,0,0,0.06)" },
  iconWrap: { width: 56, height: 56, borderRadius: 16, background: "#F5EDE4", color: "#C16A45", fontSize: 24, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" },
  label: { fontSize: 13, color: "#888888", marginBottom: 8 },
  title: { fontSize: 22, fontWeight: 800, color: "#2A2A2A", lineHeight: 1.4, marginBottom: 28 },
  infoBox: { background: "#F5EDE4", borderRadius: 14, padding: "18px 20px", marginBottom: 28, textAlign: "left" as const },
  infoRow: { display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13 },
  infoLabel: { color: "#8A7A6A" },
  infoValue: { fontWeight: 700, color: "#2A2A2A" },
  actions: { display: "flex", gap: 12 },
  rejectBtn: { flex: 1, padding: "14px 0", borderRadius: 12, border: "1.5px solid #D9C8B8", background: "#FFFFFF", color: "#666666", fontWeight: 700, fontSize: 15, cursor: "pointer" },
  acceptBtn: { flex: 1, padding: "14px 0", borderRadius: 12, border: "none", background: "#C16A45", color: "#FFFFFF", fontWeight: 700, fontSize: 15, cursor: "pointer" },
};
