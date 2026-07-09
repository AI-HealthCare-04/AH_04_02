import { useNavigate } from "react-router-dom";

const FOOTER_COLUMNS: { title: string; items: { label: string; to: string }[] }[] = [
  {
    title: "복약 안내",
    items: [
      { label: "오늘의 복약", to: "/schedule" },
      { label: "복용 기록", to: "/monitoring" },
      { label: "약품 정보", to: "/records" },
      { label: "복약 알림", to: "/notification" },
    ],
  },
  {
    title: "생활 습관",
    items: [
      { label: "운동 가이드", to: "/records" },
      { label: "식단 관리", to: "/records" },
      { label: "수면 개선", to: "/records" },
      { label: "정신 건강", to: "/records" },
    ],
  },
  {
    title: "알림 설정",
    items: [
      { label: "알림 관리", to: "/notification" },
      { label: "알림 내역", to: "/notification" },
      { label: "시간 설정", to: "/schedule" },
    ],
  },
];

function FooterColumn({ title, items }: { title: string; items: { label: string; to: string }[] }) {
  const navigate = useNavigate();
  return (
    <div>
      <h4 style={styles.footerColTitle}>{title}</h4>
      {items.map((item) => (
        <p
          key={item.label}
          style={{ ...styles.footerColItem, cursor: "pointer" }}
          onClick={() => navigate(item.to)}
        >
          {item.label}
        </p>
      ))}
    </div>
  );
}

export default function Footer() {
  return (
    <footer style={styles.footer}>
      <div style={styles.footerGrid}>
        <div style={styles.footerBrand}>
          <div style={styles.footerLogo}>
            <span style={styles.logoIconSmall}>♥</span>
            <span style={styles.footerLogoText}>건강동행</span>
          </div>
          <p style={styles.footerDesc}>
            수도권 독거노인과 거동 불편자를 위한 맞춤형 건강 관리 플랫폼입니다.
            진료 기록 기반 복약 안내와 생활 습관 개선 가이드를 제공하여 건강한 일상을 함께합니다.
          </p>
        </div>
        {FOOTER_COLUMNS.map((col) => (
          <FooterColumn key={col.title} title={col.title} items={col.items} />
        ))}
      </div>
      <div style={styles.footerBottom}>
        <span>© 2026 건강동행 | 개인정보처리방침 | 이용약관</span>
        <div style={styles.footerIcons}>
          <span>✉</span>
          <span>♥</span>
        </div>
      </div>
    </footer>
  );
}

const styles: Record<string, React.CSSProperties> = {
  footer: { background: "#2A211B", padding: "60px 40px 24px", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  footerGrid: { display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 40, maxWidth: 1200, margin: "0 auto 40px" },
  footerBrand: { maxWidth: 320 },
  footerLogo: { display: "flex", alignItems: "center", gap: 8, marginBottom: 16 },
  logoIconSmall: { width: 28, height: 28, borderRadius: "50%", background: "#C16A45", color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 },
  footerLogoText: { color: "#FFFFFF", fontWeight: 700, fontSize: 18 },
  footerDesc: { color: "#8A7A6A", fontSize: 13, lineHeight: 1.7, wordBreak: "keep-all" as const },
  footerColTitle: { color: "#FFFFFF", fontSize: 15, fontWeight: 700, marginBottom: 16 },
  footerColItem: { color: "#8A7A6A", fontSize: 13, marginBottom: 12 },
  footerBottom: { display: "flex", justifyContent: "space-between", maxWidth: 1200, margin: "0 auto", paddingTop: 24, borderTop: "1px solid #4A3B2E", color: "#8A7A6A", fontSize: 12 },
  footerIcons: { display: "flex", gap: 12 },
};
