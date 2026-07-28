import { Heart, Mail, Pill } from "lucide-react";

// [7/14] 기존에 여기 있던 "복약 안내/생활 습관/알림 설정" 3개 카테고리 메뉴는
// 상단 NavBar의 "전체메뉴" 드롭다운으로 옮겼다 — 매 페이지 하단까지 스크롤해야
// 닿던 메뉴를 상단에서 바로 쓰게 하기 위함. 풋터는 브랜드 소개 + 저작권 표시만 남긴다.
export default function Footer() {
  return (
    <footer style={styles.footer}>
      <div style={styles.footerBrand}>
        <div style={styles.footerLogo}>
          <span style={styles.logoIconSmall}><Pill className="w-3.5 h-3.5" strokeWidth={2.4} /></span>
          <span style={styles.footerLogoText}>건강동행</span>
        </div>
        <p style={styles.footerDesc}>
          수도권 독거노인과 거동 불편자를 위한 맞춤형 건강 관리 플랫폼입니다.
          진료 기록 기반 복약 안내와 생활 습관 개선 가이드를 제공하여 건강한 일상을 함께합니다.
        </p>
      </div>
      <div style={styles.footerBottom}>
        <span>© 2026 건강동행 | 개인정보처리방침 | 이용약관</span>
        <div style={styles.footerIcons}>
          <Mail className="w-4 h-4" />
          <Heart className="w-4 h-4" />
        </div>
      </div>
    </footer>
  );
}

const styles: Record<string, React.CSSProperties> = {
  footer: { background: "#2A211B", padding: "40px 40px 24px", fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" },
  footerBrand: { maxWidth: 480, margin: "0 auto 24px" },
  footerLogo: { display: "flex", alignItems: "center", gap: 8, marginBottom: 16 },
  logoIconSmall: { width: 28, height: 28, borderRadius: "50%", background: "#C16A45", color: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 },
  footerLogoText: { color: "#FFFFFF", fontWeight: 700, fontSize: 18 },
  footerDesc: { color: "#8A7A6A", fontSize: 13, lineHeight: 1.7, wordBreak: "keep-all" as const },
  footerBottom: { display: "flex", justifyContent: "space-between", maxWidth: 1200, margin: "0 auto", paddingTop: 24, borderTop: "1px solid #4A3B2E", color: "#8A7A6A", fontSize: 12 },
  footerIcons: { display: "flex", gap: 12 },
};
