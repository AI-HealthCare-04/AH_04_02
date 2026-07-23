import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Menu, Pill, Search, X } from "lucide-react";
import { getCurrentCaregiverId } from "../lib/session";
import { C } from "../theme";

interface NavBarProps {
  isLoggedIn?: boolean;
  userName?: string;
  variant?: "light" | "dark";
}

type NavItem = { label: string; to: string; children?: { label: string; to: string }[] };

// [2026-07-20] 별도 "더 보기" 화살표 하나에 전부 몰아두던 방식 대신, 상단 메뉴 각각에
// 마우스를 올리면 그 메뉴 바로 아래로 관련 하위 항목이 드롭다운되도록 변경 — 알림류는
// 오늘의 복약 아래, 기록류는 등록내역 아래로 그룹 분리. 복약 가이드는 하위 항목에서
// 상단 메뉴로 승격, 처방 약 등록은 맨 왼쪽으로 이동.
const PATIENT_NAV_ITEMS: NavItem[] = [
  { label: "처방 약 등록", to: "/upload" },
  {
    label: "오늘의 복약",
    to: "/dashboard",
    children: [
      { label: "복약 알림", to: "/schedule" },
      { label: "알림 설정", to: "/notification" },
      { label: "알림함", to: "/notifications" },
    ],
  },
  { label: "복약 가이드", to: "/guides" },
  {
    label: "등록내역",
    to: "/records",
    children: [
      { label: "복약기록", to: "/monitoring" },
      // [2026-07-21 추가] 보호자 초대/연결 화면(Connect.tsx) — 지금까진 대시보드
      // 배너에서만 들어갈 수 있었음. 이미 만든 페이지를 내비바에서도 바로 접근 가능하게.
      { label: "보호자 등록", to: "/connect" },
      // [2026-07-21 추가] 식사시간 설정(MealTimeCheck.tsx) — 지금까진 회원가입 직후에만
      // 들어올 수 있었음. 복용시간(식전/식후) 계산 기준이라 나중에도 고칠 수 있어야 한다.
      { label: "식사시간 등록", to: "/meal-check" },
    ],
  },
];

const CAREGIVER_NAV_ITEMS: NavItem[] = [
  { label: "환자 관리", to: "/patients" },
  { label: "알림함", to: "/notifications" },
  { label: "연결관리", to: "/connect" },
  { label: "설정", to: "/settings" },
];

/**
 * [7/8 업그레이드] 기존엔 로고만 있고 메뉴 링크는 실제로 동작하지 않았음.
 * Figma 원본 Navbar 디자인 + react-router 실제 이동으로 교체.
 * [이후] 색상을 theme.ts(C)로 통일 — 인라인 hex 제거.
 * [7/13] lg 미만 구간용 햄버거 드로어 추가 — ESC/바깥클릭 닫기, 스크롤 잠금.
 */
const AUTH_PATHS = ["/login", "/register", "/reset-password"];

export default function NavBar({ isLoggedIn = false, userName = "", variant = "light" }: NavBarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const dark = variant === "dark";
  const textColor = dark ? C.white : C.dark;
  const [isOpen, setIsOpen] = useState(false);
  const [hoveredTo, setHoveredTo] = useState<string | null>(null);
  const [allOpen, setAllOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  // [2026-07-20] 통합검색이 lg 미만(모바일 포함 전체)에서 아예 안 보이던 문제 —
  // 데스크톱 입력창 대신, 돋보기 버튼을 누르면 헤더 아래로 펼쳐지는 검색줄을 추가.
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const allMenuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const navItems = getCurrentCaregiverId() ? CAREGIVER_NAV_ITEMS : PATIENT_NAV_ITEMS;
  // [2026-07-20] 통합검색에서 "알림설정", "가이드"처럼 메뉴 이름 일부만 쳐도 해당 메뉴로
  // 바로 이동할 수 있게 — 상단 메뉴+하위 항목을 한 겹으로 펼친 검색 대상 목록.
  const allMenuEntries: { label: string; to: string }[] = navItems.flatMap((item) => [
    { label: item.label, to: item.to },
    ...(item.children ?? []),
  ]);
  const trimmedQuery = searchQuery.trim();
  const menuMatches = trimmedQuery ? allMenuEntries.filter((e) => e.label.includes(trimmedQuery)) : [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
        setHoveredTo(null);
        setAllOpen(false);
        setSearchFocused(false);
        setMobileSearchOpen(false);
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

  // 현재 경로가 이 메뉴(또는 그 하위 항목) 소속인지 — 정확히 같거나 그 경로로 시작하면
  // (예: /records/3/review도 "등록내역" 소속) 활성 메뉴로 보고 주황색으로 강조한다.
  const isActivePath = (to: string) => location.pathname === to || location.pathname.startsWith(`${to}/`);
  const isActiveItem = (item: NavItem) =>
    isActivePath(item.to) || (item.children?.some((c) => isActivePath(c.to)) ?? false);

  const goToRecordsSearch = (q: string) => {
    if (!q) return;
    navigate(`/records?search=${encodeURIComponent(q)}`);
    setSearchFocused(false);
    setMobileSearchOpen(false);
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
        <div className="max-w-7xl mx-auto px-6 sm:px-10 h-16 grid grid-cols-[auto_1fr_auto] items-center gap-4">
          <Link to="/" className="flex items-center gap-2 shrink-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: C.terracotta }}>
              <Pill className="w-4 h-4 text-white" strokeWidth={2.4} />
            </div>
            <span className="text-xl font-black whitespace-nowrap" style={{ color: textColor }}>건강동행</span>
          </Link>

          {isLoggedIn && (
            <nav className="hidden lg:flex items-center justify-center gap-6 min-w-0">
              {navItems.map((item) => (
                <div
                  key={item.to}
                  className="relative"
                  onMouseEnter={() => item.children && setHoveredTo(item.to)}
                  onMouseLeave={() => item.children && setHoveredTo(null)}
                >
                  <Link
                    to={item.to}
                    className="text-[15px] whitespace-nowrap transition-opacity hover:opacity-60"
                    style={{
                      color: isActiveItem(item) ? C.terracotta : textColor,
                      fontWeight: isActiveItem(item) ? 700 : 500,
                    }}
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

                {/* [2026-07-20] 화살표 자기 자리에 붙는 세로 목록 대신, 메가메뉴처럼 nav 전체
                    중앙 아래로 내려와 상단 메뉴별 열(column)로 나란히 보여주는 형태로 변경. */}
                {allOpen && (
                  <div className="fixed left-0 right-0 top-16 pt-3 -mt-px flex justify-center">
                    <div
                      className="rounded-2xl p-6 flex gap-10"
                      style={{ background: C.white, border: "1px solid rgba(30,26,23,0.10)", boxShadow: C.shadowDropdown }}
                    >
                      {navItems.map((item) => (
                        <div key={item.to} className="flex flex-col gap-2 min-w-[110px]">
                          <Link
                            to={item.to}
                            onClick={() => setAllOpen(false)}
                            className="py-1 text-[14px] font-bold whitespace-nowrap transition-opacity hover:opacity-60"
                            style={{ color: C.dark }}
                          >
                            {item.label}
                          </Link>
                          {item.children?.map((child) => (
                            <Link
                              key={child.to}
                              to={child.to}
                              onClick={() => setAllOpen(false)}
                              className="text-[13px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
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

          <div className="flex items-center gap-3 shrink-0">
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

            {isLoggedIn ? (
              <>
                <button
                  className="lg:hidden flex items-center justify-center w-8 h-8 transition-opacity hover:opacity-60"
                  onClick={() => {
                    setMobileSearchOpen((v) => !v);
                    setIsOpen(false);
                  }}
                  aria-expanded={mobileSearchOpen}
                  aria-label="통합 검색"
                  style={{ color: textColor }}
                >
                  {mobileSearchOpen ? <X className="w-5 h-5" /> : <Search className="w-5 h-5" />}
                </button>

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
                  onClick={() => {
                    setIsOpen((v) => !v);
                    setMobileSearchOpen(false);
                  }}
                  aria-expanded={isOpen}
                  aria-label="메뉴"
                  style={{ color: textColor }}
                >
                  {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>
              </>
            ) : (
              !dark && !AUTH_PATHS.includes(location.pathname) && (
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
            {navItems.map((item) => (
              <div key={item.to} className="border-b last:border-0" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <Link
                  to={item.to}
                  className="block text-[15px] whitespace-nowrap transition-opacity hover:opacity-60 py-3"
                  style={{
                    color: isActiveItem(item) ? C.terracotta : C.dark,
                    fontWeight: isActiveItem(item) ? 700 : 500,
                  }}
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

      {isLoggedIn && mobileSearchOpen && (
        <>
          <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setMobileSearchOpen(false)} />
          <div
            className="fixed top-16 left-0 right-0 z-40 lg:hidden border-b backdrop-blur-sm px-4 py-3"
            style={{ background: "rgba(255,255,255,0.97)", borderColor: "rgba(30,26,23,0.10)" }}
          >
            <form onSubmit={handleSearch} className="flex items-center relative">
              <Search className="absolute left-3 w-4 h-4 pointer-events-none" style={{ color: C.muted }} />
              <input
                autoFocus
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="통합 검색"
                aria-label="통합 검색"
                className="w-full pl-9 pr-3 py-3 rounded-full border text-[15px] outline-none bg-white"
                style={{ borderColor: "rgba(30,26,23,0.15)" }}
              />
            </form>

            {trimmedQuery && (
              <div
                className="mt-2 rounded-2xl p-2 flex flex-col gap-0.5 max-h-72 overflow-y-auto"
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
                          setMobileSearchOpen(false);
                          setSearchQuery("");
                        }}
                        className="px-3 py-2.5 rounded-xl text-[14px] font-medium whitespace-nowrap transition-opacity hover:opacity-60"
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
                  className="px-3 py-2.5 rounded-xl text-left text-[14px] font-medium transition-opacity hover:opacity-60"
                  style={{ color: C.terracotta }}
                >
                  등록내역에서 "{trimmedQuery}" 검색
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
