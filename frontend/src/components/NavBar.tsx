import { useNavigate } from "react-router-dom";

interface NavBarProps {
  isLoggedIn?: boolean;
  userName?: string;
  variant?: "light" | "dark";
}

export default function NavBar({ isLoggedIn = false, userName, variant = "light" }: NavBarProps) {
  const navigate = useNavigate();
  const isDark = variant === "dark";

  return (
    <nav style={{
      padding: "16px 40px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      position: "relative" as const,
      zIndex: 10,
      background: isDark ? "transparent" : "#FFFFFF",
      borderBottom: isDark ? "none" : "1px solid #EEE6DC",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }} onClick={() => navigate("/")}>
        <span style={{
          width: 32, height: 32, borderRadius: "50%",
          background: "#C16A45", color: "#FFFFFF",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
        }}>♥</span>
        <span style={{ fontSize: 20, fontWeight: 700, color: isDark ? "#FFFFFF" : "#2A2A2A" }}>건강동행</span>
      </div>

      <div style={{ display: "flex", gap: 32 }}>
        {["복약 안내", "생활 습관", "알림 설정", "대시보드"].map((item) => (
          <span key={item} style={{ fontSize: 15, fontWeight: 500, cursor: "pointer", color: isDark ? "#EDE6DE" : "#2A2A2A" }}>
            {item}
          </span>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {isLoggedIn ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              width: 32, height: 32, borderRadius: "50%",
              background: "#C16A45", color: "#FFFFFF",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14, fontWeight: 700,
            }}>
              {userName?.[0] ?? "?"}
            </span>
            <span style={{ color: isDark ? "#FFFFFF" : "#2A2A2A", fontWeight: 600 }}>{userName} 님</span>
          </div>
        ) : (
          <>
            <button onClick={() => navigate("/login")} style={{
              padding: "10px 20px", fontSize: 14, fontWeight: 600,
              background: "transparent",
              border: `1.5px solid ${isDark ? "#FFFFFF" : "#C16A45"}`,
              borderRadius: 24, cursor: "pointer",
              color: isDark ? "#FFFFFF" : "#C16A45",
            }}>로그인</button>
            <button onClick={() => navigate("/login")} style={{
              padding: "10px 20px", fontSize: 14, fontWeight: 600,
              background: "#C16A45", border: "none",
              borderRadius: 24, color: "#FFFFFF", cursor: "pointer",
            }}>회원가입</button>
          </>
        )}
      </div>
    </nav>
  );
}
