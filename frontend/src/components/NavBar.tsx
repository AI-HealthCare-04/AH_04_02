import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Menu, X } from "lucide-react";
import { C } from "../theme";

interface NavBarProps {
  isLoggedIn?: boolean;
  userName?: string;
  variant?: "light" | "dark";
}

const NAV_ITEMS = [
  { label: "처방전 등록", to: "/upload" },
  { label: "복약 일정", to: "/schedule" },
  { label: "등록내역", to: "/records" },
  { label: "복약기록", to: "/monitoring" },
];

// [7/14] 풋터에 있던 3개 카테고리를 그대로 옮겨온 것 — 매 페이지 하단까지 스크롤해야
// 보이던 메뉴를 상단 드롭다운에서 바로 접근하게 함. 항목·중복 여부는 풋터와 동일하게 유지.
const MENU_GROUPS: { title: string; items: { label: string; to: string }[] }[] = [
  {
    title: "복약 안내",
    items: [
      { label: "오늘의 복약", to: "/dashboard" },
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

/**
 * [7/8 업그레이드] 기존엔 로고만 있고 메뉴 링크는 실제로 동작하지 않았음.
 * Figma 원본 Navbar 디자인 + react-router 실제 이동으로 교체.
 * [이후] 색상을 theme.ts(C)로 통일 — 인라인 hex 제거.
 * [7/13] lg 미만 구간용 햄버거 드로어 추가 — ESC/바깥클릭 닫기, 스크롤 잠금.
 */
export default function NavBar({ isLoggedIn = false, userName = "", variant = "light" }: NavBarProps) {
  const navigate = useNavigate();
  const dark = variant === "dark";
  const textColor = dark ? C.white : C.dark;
  const [isOpen, setIsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setMenuOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) setIsOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // 드롭다운 바깥 클릭 시 닫기
  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [menuOpen]);

  return (
    <>
      <header
        className={dark ? "sticky top-0 z-40 bg-transparent" : "sticky top-0 z-40 backdrop-blur-sm border-b"}
        style={dark ? undefined : { background: "rgba(255,255,255,0.95)", borderColor: "rgba(30,26,23,0.10)" }}
      >
        <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: C.terracotta }}>
              <span className="text-white text-sm">💊</span>
            </div>
            <span className="text-xl font-black whitespace-nowrap" style={{ color: textColor }}>건강동행</span>
          </Link>

          {isLoggedIn && (
            <nav className="hidden lg:flex items-center gap-6 min-w-0">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                  style={{ color: textColor }}
                >
                  {item.label}
                </Link>
              ))}

              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen((v) => !v)}
                  aria-expanded={menuOpen}
                  className="flex items-center gap-1 text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                  style={{ color: textColor }}
                >
                  전체메뉴
                  <ChevronDown className={`w-4 h-4 transition-transform ${menuOpen ? "rotate-180" : ""}`} />
                </button>

                {menuOpen && (
                  <div
                    className="absolute top-full left-1/2 -translate-x-1/2 mt-3 rounded-2xl p-6 flex gap-10 shadow-lg"
                    style={{ background: C.white, border: "1px solid rgba(30,26,23,0.10)" }}
                  >
                    {MENU_GROUPS.map((group) => (
                      <div key={group.title} className="min-w-[120px]">
                        <p className="text-[12px] font-bold mb-3 whitespace-nowrap" style={{ color: C.muted }}>
                          {group.title}
                        </p>
                        <div className="flex flex-col gap-2.5">
                          {group.items.map((item) => (
                            <Link
                              key={item.label}
                              to={item.to}
                              onClick={() => setMenuOpen(false)}
                              className="text-[14px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                              style={{ color: C.dark }}
                            >
                              {item.label}
                            </Link>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </nav>
          )}

          <div className="flex items-center gap-3 shrink-0">
            {isLoggedIn ? (
              <>
                <button
                  onClick={() => navigate("/mypage")}
                  className="flex items-center gap-2.5 transition-opacity hover:opacity-75"
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0"
                    style={{ background: C.terracotta }}
                  >
                    {userName ? userName[0] : "?"}
                  </div>
                  <span className="hidden md:inline text-[15px] font-semibold whitespace-nowrap" style={{ color: textColor }}>
                    {userName} 님
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 hidden md:inline" style={{ color: C.muted }} />
                </button>

                <button
                  className="lg:hidden flex items-center justify-center w-8 h-8 transition-opacity hover:opacity-60"
                  onClick={() => setIsOpen((v) => !v)}
                  aria-expanded={isOpen}
                  aria-label="메뉴"
                  style={{ color: textColor }}
                >
                  {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
              </>
            ) : (
              !dark && (
                <button
                  onClick={() => navigate("/login")}
                  className="px-5 py-2 rounded-full border-2 text-[14px] font-bold whitespace-nowrap transition-colors"
                  style={{ borderColor: C.terracotta, color: C.terracotta }}
                >
                  로그인
                </button>
              )
            )}
          </div>
        </div>
      </header>

      {isLoggedIn && isOpen && (
        <>
          {/* 바깥 클릭으로 닫기 */}
          <div
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={() => setIsOpen(false)}
          />
          {/* 드로어 패널 — 헤더(h-16) 바로 아래, 데스크톱에선 숨김 */}
          <nav
            className="fixed top-16 left-0 right-0 z-40 lg:hidden border-b backdrop-blur-sm px-6 py-2 flex flex-col max-h-[calc(100vh-4rem)] overflow-y-auto"
            style={{ background: "rgba(255,255,255,0.97)", borderColor: "rgba(30,26,23,0.10)" }}
          >
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60 py-3 border-b last:border-0"
                style={{ color: C.dark, borderColor: "rgba(30,26,23,0.08)" }}
                onClick={() => setIsOpen(false)}
              >
                {item.label}
              </Link>
            ))}

            {MENU_GROUPS.map((group) => (
              <div key={group.title} className="py-3 border-b" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <p className="text-[12px] font-bold mb-2" style={{ color: C.muted }}>{group.title}</p>
                <div className="flex flex-col gap-2">
                  {group.items.map((item) => (
                    <Link
                      key={item.label}
                      to={item.to}
                      className="text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                      style={{ color: C.dark }}
                      onClick={() => setIsOpen(false)}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </>
      )}
    </>
  );
}