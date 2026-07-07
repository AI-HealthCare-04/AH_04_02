import { Link, useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";

interface NavBarProps {
  isLoggedIn?: boolean;
  userName?: string;
  variant?: "light" | "dark";
}

const NAV_ITEMS = [
  { label: "복약 일정", to: "/schedule" },
  { label: "알림 설정", to: "/notification" },
  { label: "대시보드", to: "/dashboard" },
];

/**
 * [7/8 업그레이드] 기존엔 로고만 있고 메뉴 링크는 실제로 동작하지 않았음.
 * Figma 원본 Navbar 디자인 + react-router 실제 이동으로 교체.
 */
export default function NavBar({ isLoggedIn = false, userName = "", variant = "light" }: NavBarProps) {
  const navigate = useNavigate();
  const dark = variant === "dark";

  return (
    <header
      className={
        dark
          ? "sticky top-0 z-40 bg-transparent"
          : "sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-black/10"
      }
    >
      <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-[#C1653D]">
            <span className="text-white text-sm">💊</span>
          </div>
          <span className={`text-xl font-black ${dark ? "text-white" : "text-[#1E1A17]"}`}>
            건강동행
          </span>
        </Link>

        {isLoggedIn && (
          <nav className="hidden sm:flex items-center gap-8">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={`text-[15px] font-medium transition-opacity hover:opacity-60 ${
                  dark ? "text-white" : "text-[#1E1A17]"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {isLoggedIn ? (
            <button
              onClick={() => navigate("/mypage")}
              className="flex items-center gap-2.5 transition-opacity hover:opacity-75"
            >
              <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold bg-[#C1653D]">
                {userName ? userName[0] : "?"}
              </div>
              <span className={`text-[15px] font-semibold ${dark ? "text-white" : "text-[#1E1A17]"}`}>
                {userName} 님
              </span>
              <ChevronRight className="w-3.5 h-3.5 text-[#8A7E75]" />
            </button>
          ) : (
            !dark && (
              <button
                onClick={() => navigate("/login")}
                className="px-5 py-2 rounded-full border-2 text-[14px] font-bold border-[#C1653D] text-[#C1653D] transition-colors hover:bg-[#C1653D]/5"
              >
                로그인
              </button>
            )
          )}
        </div>
      </div>
    </header>
  );
}
