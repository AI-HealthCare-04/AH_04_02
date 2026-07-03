import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";

export default function Landing() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  return (
    <div style={styles.page}>
      <div style={styles.heroSection}>
        <NavBar variant="dark" />
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

      <footer style={styles.footer}>
        <div style={styles.footerGrid}>
          <div style={styles.footerBrand}>
            <div style={styles.footerLogo}>
              <span style={{ ...styles.logoIconSmall }}>♥</span>
              <span style={styles.footerLogoText}>건강동행</span>
            </div>
            <p style={styles.footerDesc}>
              수도권 독거노인과 거동 불편자를 위한 맞춤형 건강 관리 플랫폼입니다.
              진료 기록 기반 복약 안내와 생활 습관 개선 가이드를 제공하여 건강한 일상을 함께합니다.
            </p>
          </div>
          <FooterColumn title="복약 안내" items={["오늘의 복약", "복용 기록", "약품 정보", "복약 알림"]} />
          <FooterColumn title="생활 습관" items={["운동 가이드", "식단 관리", "수면 개선", "정신 건강"]} />
          <FooterColumn title="알림 설정" items={["알림 관리", "알림 내역", "시간 설정"]} />
        </div>
        <div style={styles.footerBottom}>
          <span>© 2026 건강동행 | 개인정보처리방침 | 이용약관</span>
          <div style={styles.footerIcons}>
            <span>✉</span>
            <span>♥</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FooterColumn({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 style={styles.footerColTitle}>{title}</h4>
      {items.map((item) => (
        <p key={item} style={styles.footerColItem}>{item}</p>
      ))}
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
  footer: { background: "#2A211B", padding: "60px 40px 24px" },
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
