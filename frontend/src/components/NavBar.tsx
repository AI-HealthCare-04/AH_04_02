import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Menu, Pill, Search, X } from "lucide-react";
import { C } from "../theme";

interface NavBarProps {
  isLoggedIn?: boolean;
  userName?: string;
  variant?: "light" | "dark";
}

// [2026-07-20] 별도 "더 보기" 화살표 하나에 전부 몰아두던 방식 대신, 상단 메뉴 각각에
// 마우스를 올리면 그 메뉴 바로 아래로 관련 하위 항목이 드롭다운되도록 변경 — 알림류는
// 오늘의 복약 아래, 기록류는 등록내역 아래로 그룹 분리. 복약 가이드는 하위 항목에서
// 상단 메뉴로 승격, 처방 약 등록은 맨 왼쪽으로 이동.
const NAV_ITEMS: { label: string; to: string; children?: { label: string; to: string }[] }[] = [
  { label: "처방 약 등록", to: "/upload" },
  {
    label: "오늘의 복약",
    to: "/dashboard",
    children: [
      { label: "복약 알림", to: "/schedule" },
      { label: "알림 설정", to: "/notification" },
    ],
  },
  { label: "복약 가이드", to: "/guides" },
  {
    label: "등록내역",
    to: "/records",
    children: [{ label: "복약기록", to: "/monitoring" }],
  },
];

// [2026-07-20] 통합검색에서 "알림설정", "가이드"처럼 메뉴 이름 일부만 쳐도 해당 메뉴로
// 바로 이동할 수 있게 — 상단 메뉴+하위 항목을 한 겹으로 펼친 검색 대상 목록.
const ALL_MENU_ENTRIES: { label: string; to: string }[] = NAV_ITEMS.flatMap((item) => [
  { label: item.label, to: item.to },
  ...(item.children ?? []),
]);

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
  const [hoveredTo, setHoveredTo] = useState<string | null>(null);
  const [allOpen, setAllOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const allMenuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const trimmedQuery = searchQuery.trim();
  const menuMatches = trimmedQuery ? ALL_MENU_ENTRIES.filter((e) => e.label.includes(trimmedQuery)) : [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setHoveredTo(null);
        setAllOpen(false);
        setSearchFocused(false);
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

  // [2026-07-20] 항목별 호버 드롭다운과 달리 이건 클릭으로 열고 닫으므로, 바깥을
  // 클릭했을 때도 닫히게 해야 한다 (호버 드롭다운은 mouseleave로 이미 처리됨).
  useEffect(() => {
    if (!allOpen) return;
    const onClickOutside = (e: MouseEvent) => {
      if (allMenuRef.current && !allMenuRef.current.contains(e.target as Node)) {
        setAllOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [allOpen]);

  useEffect(() => {
    if (!searchFocused) return;
    const onClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchFocused(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [searchFocused]);

  const goToRecordsSearch = (q: string) => {
    if (!q) return;
    navigate(`/records?search=${encodeURIComponent(q)}`);
    setSearchFocused(false);
  };

  const handleSearch = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    goToRecordsSearch(trimmedQuery);
  };

  return (
    <>
      <header
        className={dark ? "sticky top-0 z-40 bg-transparent" : "sticky top-0 z-40 backdrop-blur-sm border-b"}
        style={dark ? undefined : { background: "rgba(255,255,255,0.95)", borderColor: "rgba(30,26,23,0.10)" }}
      >
        <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: C.terracotta }}>
              <Pill className="w-4 h-4 text-white" strokeWidth={2.4} />
            </div>
            <span className="text-xl font-black whitespace-nowrap" style={{ color: textColor }}>건강동행</span>
          </Link>

          {isLoggedIn && (
            <nav className="hidden lg:flex items-center gap-6 min-w-0">
              {NAV_ITEMS.map((item) => (
                <div
                  key={item.to}
                  className="relative"
                  onMouseEnter={() => item.children && setHoveredTo(item.to)}
                  onMouseLeave={() => item.children && setHoveredTo(null)}
                >
                  <Link
                    to={item.to}
                    className="text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                    style={{ color: textColor }}
                  >
                    {item.label}
                  </Link>

                  {/* [2026-07-20] "더 보기" 화살표 하나로 몰아둔 드롭다운 대신, 각 메뉴에 마우스를
                      올리면 그 메뉴 바로 아래로 관련 하위 항목이 드롭다운되도록 변경. */}
                  {item.children && hoveredTo === item.to && (
                    <div className="absolute top-full left-1/2 -translate-x-1/2 pt-3 -mt-px">
                      <div
                        className="rounded-2xl p-4 flex flex-col gap-2.5 min-w-[140px]"
                        style={{ background: C.white, border: "1px solid rgba(30,26,23,0.10)", boxShadow: C.shadowDropdown }}
                      >
                        {item.children.map((child) => (
                          <Link
                            key={child.to}
                            to={child.to}
                            onClick={() => setHoveredTo(null)}
                            className="text-[14px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                            style={{ color: C.dark }}
                          >
                            {child.label}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* [2026-07-20] 항목별 호버 드롭다운과 별개로, 전체 메뉴를 한 번에 보고 싶을 때를
                  위한 통합 드롭다운 — 클릭으로 열고 닫음(호버 아님), 바깥 클릭/ESC로 닫힘. */}
              <div className="relative" ref={allMenuRef}>
                <button
                  onClick={() => setAllOpen((v) => !v)}
                  aria-expanded={allOpen}
                  aria-label="전체 메뉴"
                  className="flex items-center justify-center w-8 h-8 rounded-full transition-opacity hover:opacity-60"
                  style={{ color: textColor }}
                >
                  <ChevronDown className={`w-5 h-5 transition-transform ${allOpen ? "rotate-180" : ""}`} />
                </button>

                {allOpen && (
                  <div className="absolute top-full right-0 pt-3 -mt-px">
                    <div
                      className="rounded-2xl p-4 flex flex-col gap-1 min-w-[160px]"
                      style={{ background: C.white, border: "1px solid rgba(30,26,23,0.10)", boxShadow: C.shadowDropdown }}
                    >
                      {NAV_ITEMS.map((item) => (
                        <div key={item.to}>
                          <Link
                            to={item.to}
                            onClick={() => setAllOpen(false)}
                            className="block py-1.5 text-[14px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                            style={{ color: C.dark }}
                          >
                            {item.label}
                          </Link>
                          {item.children?.map((child) => (
                            <Link
                              key={child.to}
                              to={child.to}
                              onClick={() => setAllOpen(false)}
                              className="block py-1.5 pl-3 text-[13px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                              style={{ color: C.muted }}
                            >
                              {child.label}
                            </Link>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </nav>
          )}

          {isLoggedIn && (
            <div className="hidden lg:block relative shrink-0 w-48" ref={searchRef}>
              <form onSubmit={handleSearch} className="flex items-center relative">
                <Search className="absolute left-3 w-4 h-4 pointer-events-none" style={{ color: C.muted }} />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  placeholder="통합 검색"
                  aria-label="통합 검색"
                  className="w-full pl-9 pr-3 py-2 rounded-full border text-[13px] outline-none bg-white"
                  style={{ borderColor: "rgba(30,26,23,0.15)" }}
                />
              </form>

              {/* [2026-07-20] "알림설정", "가이드"처럼 메뉴 이름 일부만 쳐도 바로 이동할 수
                  있도록, 등록내역 검색과 별개로 메뉴 이름도 실시간으로 함께 찾아 보여준다. */}
              {searchFocused && trimmedQuery && (
                <div className="absolute top-full left-0 right-0 pt-2">
                  <div
                    className="rounded-2xl p-2 flex flex-col gap-0.5 max-h-72 overflow-y-auto"
                    style={{ background: C.white, border: "1px solid rgba(30,26,23,0.10)", boxShadow: C.shadowDropdown }}
                  >
                    {menuMatches.length > 0 && (
                      <>
                        <p className="px-3 pt-1 pb-0.5 text-[11px] font-bold" style={{ color: C.muted }}>메뉴</p>
                        {menuMatches.map((m) => (
                          <Link
                            key={m.to}
                            to={m.to}
                            onClick={() => {
                              setSearchFocused(false);
                              setSearchQuery("");
                            }}
                            className="px-3 py-2 rounded-xl text-[13px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
                            style={{ color: C.dark }}
                          >
                            {m.label}
                          </Link>
                        ))}
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => goToRecordsSearch(trimmedQuery)}
                      className="px-3 py-2 rounded-xl text-left text-[13px] font-medium transition-opacity hover:opacity-60"
                      style={{ color: C.terracotta }}
                    >
                      등록내역에서 "{trimmedQuery}" 검색
                    </button>
                  </div>
                </div>
              )}
            </div>
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
              <div key={item.to} className="border-b last:border-0" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <Link
                  to={item.to}
                  className="block text-[15px] font-medium whitespace-nowrap transition-opacity hover:opacity-60 py-3"
                  style={{ color: C.dark }}
                  onClick={() => setIsOpen(false)}
                >
                  {item.label}
                </Link>
                {item.children?.map((child) => (
                  <Link
                    key={child.to}
                    to={child.to}
                    className="block text-[14px] font-medium whitespace-nowrap transition-opacity hover:opacity-60 py-2.5 pl-4"
                    style={{ color: C.muted }}
                    onClick={() => setIsOpen(false)}
                  >
                    {child.label}
                  </Link>
                ))}
              </div>
            ))}
          </nav>
        </>
      )}
    </>
  );
}