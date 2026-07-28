import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Bell, Bookmark, Check, ChevronRight, Heart, Mail, Pill } from "lucide-react";
import NavBar from "../components/NavBar";
import { checkIntake, getLogs, getTodayMedications, type Medication, type MedicationLogEntry } from "../api/monitoring";
import { getNotificationSettings, type NotificationSettings } from "../api/care";
import { getCurrentPatientId, getCurrentUserName, isLoggedIn } from "../lib/session";
import { C } from "../theme";

const unsplash = (id: string, w: number, h: number) =>
  `https://images.unsplash.com/${id}?w=${w}&h=${h}&fit=crop&auto=format`;

// [7/14] Figma 원본(App.figma-export.tsx.bak)의 랜딩 페이지 5개 섹션 중 3개
// (최신 안내/자동 생성 시스템/대시보드 요약)가 이관 과정에서 빠졌던 것을 복원.
const FEATURE_TABS = [
  { Icon: Pill, label: "복약 안내" },
  { Icon: Heart, label: "생활 습관" },
  { Icon: Bell, label: "알림 설정" },
];

const VALUE_ITEMS = [
  "진료 기록 기반 복약 및 복약 스케쥴 분석",
  "개인 건강 상태에 맞는 생활 습관 가이드",
  "복약 시간 맞춤 알림 서비스",
];

// 대시보드 요약 카드의 도넛 차트(50% 고정) — Figma 원본과 동일한 SVG 원 둘레 계산
const DONUT_R = 36;
const DONUT_CX = 40;
const DONUT_CY = 40;
const DONUT_CIRC = 2 * Math.PI * DONUT_R;

export default function Landing() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [tab, setTab] = useState(0);
  const [meds, setMeds] = useState<Medication[]>([]);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [notifSettings, setNotifSettings] = useState<NotificationSettings | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const loggedIn = isLoggedIn();

  // [7/14] "최신 안내" 섹션을 처방전 등록으로 실제 등록된 약품·알림 일정(오늘자)과 연결 —
  // 더 이상 Figma의 예시 텍스트가 아니라 로그인한 환자의 실제 /monitoring/today 데이터.
  // [수정] 비로그인 방문자는 이 API들이 전부 인증이 필요해서(get_current_actor) 401이
  // 나고, monitoringClient의 인터셉터가 그걸 보고 /login으로 강제 이동시켜버린다 —
  // 로그인 상태일 때만 호출하고, 아니면 빈 상태 그대로 둬서 아래 "등록된 일정이
  // 없어요" 안내를 자연스러운 비로그인 미리보기로 쓴다.
  useEffect(() => {
    const patientId = getCurrentPatientId();
    if (!loggedIn || patientId == null) return;
    getTodayMedications(patientId)
      .then(setMeds)
      .catch(() => {});
  }, [loggedIn]);

  // [7/14] "대시보드 요약"의 생활 습관·알림 설정 카드도 모니터링 페이지와 같은 실제
  // 데이터로 연결 — 최근 7일 복약 순응률(getLogs, MonitoringDashboard.tsx와 동일 계산식)과
  // 실제 알림 켜짐/꺼짐 상태(getNotificationSettings). "건강 점수"·"다음 병원 방문"은
  // 앱에 그런 데이터 자체가 없어서 실제로 존재하는 이 두 값으로 대체한다.
  useEffect(() => {
    const patientId = getCurrentPatientId();
    if (!loggedIn || patientId == null) return;
    getLogs(patientId, 7)
      .then(setLogs)
      .catch(() => {});
    getNotificationSettings(patientId)
      .then(setNotifSettings)
      .catch(() => {});
  }, [loggedIn]);

  const takenCount = meds.filter((m) => m.status === "taken").length;
  const medsDonutPct = meds.length > 0 ? takenCount / meds.length : 0;
  const medsDonutDash = medsDonutPct * DONUT_CIRC;

  const last7Logs = logs.filter(
    (l) => Date.now() - new Date(l.checked_at).getTime() <= 7 * 24 * 60 * 60 * 1000
  );
  const adherence =
    last7Logs.length > 0
      ? Math.round((last7Logs.filter((l) => l.status === "taken").length / last7Logs.length) * 100)
      : null;
  // [7/14] 두 번째·세 번째 카드를 임의의 약 2개가 아니라 오전/오후로 나눠 보여준다.
  const morningMeds = meds.filter((m) => Number(m.time.slice(0, 2)) < 12);
  const afternoonMeds = meds.filter((m) => Number(m.time.slice(0, 2)) >= 12);

  const handleTake = async (id: string) => {
    setSavingId(id);
    try {
      await checkIntake(id, "taken");
      setMeds((prev) => prev.map((m) => (m.id === id ? { ...m, status: "taken" } : m)));
    } catch {
      // 랜딩 페이지 미리보기 카드라 실패해도 조용히 무시 — 실제 체크는 대시보드에서 다시 가능
    } finally {
      setSavingId(null);
    }
  };

  const renderPeriodCard = (title: string, list: Medication[]) => {
    const takenInPeriod = list.filter((m) => m.status === "taken").length;
    return (
      <div className="rounded-2xl p-6 flex flex-col" style={{ background: C.white, boxShadow: "0 2px 24px rgba(30,26,23,0.07)" }}>
        <div className="flex items-center gap-2 mb-5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: "rgba(224,138,91,0.10)" }}><Bookmark className="w-3.5 h-3.5" style={{ color: C.terracottaLight }} /></div>
          <span className="text-[15px] font-extrabold" style={{ color: "#2A2A2A" }}>{title}</span>
        </div>
        {list.length === 0 ? (
          <p className="text-[14px]" style={{ color: "#8A7A6A" }}>등록된 {title} 일정이 없어요.</p>
        ) : (
          <>
            <p className="text-[22px] font-extrabold mb-4" style={{ color: "#2A2A2A" }}>{takenInPeriod}/{list.length}건 복용</p>
            <div className="flex flex-col gap-2.5">
              {list.map((m, i) => {
                const done = m.status === "taken";
                return (
                  <div key={m.id} className={`flex items-center justify-between gap-2 ${i === 0 ? "" : "pt-2.5"}`} style={{ borderTop: i === 0 ? "none" : "1px solid #F0EBE3" }}>
                    <span className={`text-[14px] font-bold ${done ? "line-through" : ""}`} style={{ color: done ? "#8A7A6A" : "#2A2A2A" }}>
                      {m.name} <span className="text-[12px] font-normal" style={{ color: "#8A7A6A" }}>{m.time}</span>
                    </span>
                    <button
                      className="shrink-0 px-3.5 py-1.5 rounded-full text-[12px] font-bold"
                      style={{ background: done ? "rgba(30,26,23,0.10)" : C.success, color: done ? "#8A7A6A" : C.white, cursor: done ? "default" : "pointer" }}
                      disabled={done || savingId === m.id}
                      onClick={() => handleTake(m.id)}
                    >
                      {done ? "완료" : savingId === m.id ? "확인 중..." : "체크"}
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div style={{ fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}>
      <div className="min-h-screen flex flex-col" style={{ background: "radial-gradient(ellipse at center, #3A2A1E 0%, #1C1410 70%)" }}>
        <NavBar isLoggedIn={loggedIn} userName={getCurrentUserName()} variant="dark" />
        <div className="flex flex-col sm:flex-row sm:justify-between gap-2 px-5 pt-6 md:px-10 md:pt-10">
          <span className="text-[13px] border rounded-[20px] px-4 py-2 w-fit" style={{ color: "#D9C8B8", borderColor: "#4A3B2E" }}>수도권 독거노인 맞춤 건강 관리</span>
          <span className="text-[13px] border rounded-[20px] px-4 py-2 w-fit" style={{ color: "#D9C8B8", borderColor: "#4A3B2E" }}>독거노인 및 거동 불편 사용자를 위한 안전한 서비스</span>
        </div>
        <div className="flex-1 flex flex-col justify-center px-5 md:px-10 max-w-[900px]">
          <h1 className="text-[32px] sm:text-[42px] md:text-[56px] font-extrabold leading-[1.3] mb-6 break-keep" style={{ color: C.white }}>
            효율적인 복약 관리<br />
            <span style={{ color: "#D98552" }}>맞춤 생활 습관 개선</span><br />
            스마트 알림 서비스
          </h1>
          <p className="text-[15px] md:text-[17px] mb-8 md:mb-9 leading-[1.6] break-keep" style={{ color: "#C9BCAE" }}>
            진료 기록을 기반으로 한 맞춤형 복약 안내와 생활 습관 개선 가이드로 건강한 일상을 함께합니다.
          </p>
          {!loggedIn && (
            <div className="flex gap-3">
              <button className="px-7 py-4 md:px-9 text-[15px] md:text-[16px] font-bold rounded-full text-white" style={{ background: "#C16A45" }} onClick={() => navigate("/register")}>무료로 시작하기</button>
              <button className="px-7 py-4 md:px-9 text-[15px] md:text-[16px] font-bold rounded-full text-white bg-transparent" style={{ border: "1.5px solid #6B5B4C" }} onClick={() => navigate("/login")}>로그인</button>
            </div>
          )}
        </div>
        <p className="text-center text-[13px] pb-6" style={{ color: "#8A7A6A" }}>스크롤하여 더 알아보기</p>
      </div>

      {/* 최신 안내 */}
      <div className="px-5 py-14 md:px-10 md:py-20 max-w-[1200px] mx-auto" style={{ background: C.ivory }}>
        <div className="flex flex-col md:flex-row md:justify-between md:items-end mb-10 flex-wrap gap-5">
          <div>
            <p className="text-[13px] font-bold mb-2" style={{ color: C.terracottaLight }}>최신 안내</p>
            <h2 className="text-[26px] md:text-[36px] font-extrabold leading-[1.3]" style={{ color: "#2A2A2A" }}>최신 복약 안내 및<br />생활 습관 개선 팁</h2>
          </div>
          <p className="text-[15px] max-w-[300px] md:text-right" style={{ color: "#8A7A6A" }}>오늘의 복약 일정과 맞춤 생활 습관 가이드를 한눈에 확인하세요.</p>
        </div>

        <div className="flex gap-2 mb-8 flex-wrap">
          {FEATURE_TABS.map(({ Icon, label }, i) => (
            <button
              key={label}
              onClick={() => setTab(i)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-full text-[14px] font-bold transition-all"
              style={{
                background: tab === i ? "#2A2A2A" : "transparent",
                color: tab === i ? "#FFFFFF" : "#2A2A2A",
                border: tab === i ? "none" : "1.5px solid rgba(30,26,23,0.10)",
              }}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        {meds.length === 0 ? (
          <div className="rounded-2xl px-6 py-12 text-center" style={{ background: C.white, boxShadow: "0 2px 24px rgba(30,26,23,0.07)" }}>
            <p className="text-[15px] mb-5" style={{ color: "#8A7A6A" }}>
              아직 등록된 복약 일정이 없어요. 처방전을 등록하면 오늘의 복약과 알림이 여기에 표시돼요.
            </p>
            <button className="px-7 py-3 rounded-full text-[14px] font-bold text-white" style={{ background: "#C16A45" }} onClick={() => navigate("/upload")}>처방전 등록하러 가기</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="rounded-2xl p-6" style={{ background: "#7A3728" }}>
              <p className="text-[11px] font-bold mb-3 opacity-60 uppercase tracking-[0.08em]" style={{ color: C.ivory }}>오늘의 복약</p>
              <p className="text-[28px] md:text-[32px] font-extrabold mb-1 text-white">{takenCount}/{meds.length}건 복용 완료</p>
              <p className="text-[13px] mb-6 opacity-[0.55]" style={{ color: C.ivory }}>오늘 예정된 복약을 시간에 맞춰 복용하세요.</p>
              <div className="flex flex-col gap-3.5">
                {meds.map((m) => {
                  const done = m.status === "taken";
                  return (
                    <div key={m.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {done ? (
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0" style={{ background: C.success }}><Check className="w-3.5 h-3.5 text-white" /></div>
                        ) : (
                          <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-[11px] font-bold" style={{ background: "rgba(255,255,255,0.12)", color: C.ivory }}>{m.time.slice(0, 2)}</div>
                        )}
                        <div>
                          <p className="text-[13px] font-semibold" style={{ color: done ? "rgba(255,255,255,0.45)" : "#FFFFFF" }}>{m.name}</p>
                          <p className="text-[11px] opacity-[0.45]" style={{ color: C.ivory }}>{m.time}{m.note ? ` · ${m.note}` : ""}</p>
                        </div>
                      </div>
                      <span className="text-[12px] shrink-0" style={{ color: "rgba(255,255,255,0.6)" }}>
                        {m.status === "taken" ? "복용 완료" : m.status === "skipped" ? "건너뜀" : "미복용"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {renderPeriodCard("오전 복약", morningMeds)}
            {renderPeriodCard("오후 복약", afternoonMeds)}
          </div>
        )}
      </div>

      {/* 자동 생성 시스템 */}
      <div className="grid grid-cols-1 md:grid-cols-2 md:min-h-[500px]">
        <div className="relative h-[320px] md:h-auto">
          <img
            src={unsplash("photo-1516574187841-cb9cc2ca948b", 700, 560)}
            alt="태블릿을 사용하는 어르신"
            className="w-full h-full object-cover block"
          />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to top, rgba(30,26,23,0.88) 0%, rgba(30,26,23,0.15) 65%)" }} />
          <div className="absolute bottom-0 left-0 p-6 md:p-10">
            <span className="inline-block px-3 py-1.5 rounded-full text-[11px] font-semibold mb-4" style={{ background: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.85)" }}>맞춤형 가이드</span>
            <h3 className="text-[22px] md:text-[28px] font-extrabold leading-[1.4] text-white">맞춤 진료 기록 기반<br />복약 및 생활 습관 가이드</h3>
          </div>
        </div>
        <div className="flex flex-col justify-center px-6 py-12 md:px-16 md:py-14" style={{ background: "#EDE8DF" }}>
          <h2 className="text-[24px] md:text-[28px] font-extrabold mb-4" style={{ color: "#2A2A2A" }}>자동 생성 시스템</h2>
          <p className="text-[15px] leading-[1.6] mb-8" style={{ color: "#8A7A6A" }}>
            병원 진료 기록을 기반으로 개인별 맞춤 복약 안내와 생활 습관 개선 가이드를 자동으로 생성합니다.
          </p>
          {VALUE_ITEMS.map((item) => (
            <div key={item} className="flex items-center gap-3 mb-4">
              <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0" style={{ background: C.success }}><Check className="w-3.5 h-3.5 text-white" /></div>
              <span className="text-[14px]" style={{ color: "#2A2A2A" }}>{item}</span>
            </div>
          ))}
          <button className="flex items-center gap-2 px-7 py-3.5 rounded-full text-white font-bold text-[15px] mt-4 w-fit" style={{ background: "#C16A45" }} onClick={() => navigate("/upload")}>
            가이드 생성하기 <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 대시보드 요약 */}
      <div className="px-5 py-14 md:px-10 md:py-20 max-w-[1200px] mx-auto" style={{ background: C.ivory }}>
        <h2 className="text-[26px] md:text-[32px] font-extrabold mb-3" style={{ color: "#2A2A2A" }}>대시보드 요약</h2>
        <p className="text-[15px] mb-10" style={{ color: "#8A7A6A" }}>건강 상태를 한눈에 확인하고 필요한 관리를 시작하세요.</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 4px 28px rgba(30,26,23,0.09)" }}>
            <img src={unsplash("photo-1584308666744-24d5c474f2ae", 400, 200)} alt="약통" className="w-full h-44 object-cover block" />
            <div className="p-5">
              <p className="text-[12px] font-bold mb-3" style={{ color: "#8A7A6A" }}>복약 관리</p>
              <div className="flex items-end justify-between mb-2">
                <div>
                  <p className="text-[11px]" style={{ color: "#8A7A6A" }}>오늘 복용 완료</p>
                  <p className="text-[24px] font-extrabold" style={{ color: "#2A2A2A" }}>{takenCount} / {meds.length}</p>
                </div>
                <svg width="72" height="72" viewBox="0 0 80 80">
                  <circle cx={DONUT_CX} cy={DONUT_CY} r={DONUT_R} fill="none" stroke="#EDE8DF" strokeWidth="8" />
                  <circle
                    cx={DONUT_CX} cy={DONUT_CY} r={DONUT_R} fill="none" stroke="#C16A45" strokeWidth="8"
                    strokeDasharray={`${medsDonutDash} ${DONUT_CIRC - medsDonutDash}`} strokeLinecap="round"
                    transform="rotate(-90 40 40)"
                  />
                  <text x="40" y="45" textAnchor="middle" fontSize="13" fontWeight="700" fill="#2A2A2A">{Math.round(medsDonutPct * 100)}%</text>
                </svg>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "#EDE8DF" }}>
                <div className="h-full rounded-full" style={{ width: `${Math.round(medsDonutPct * 100)}%`, background: "#C16A45" }} />
              </div>
            </div>
          </div>

          <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 4px 28px rgba(30,26,23,0.09)" }}>
            <img src={unsplash("photo-1544367567-0f2fcb009e0b", 400, 200)} alt="스트레칭" className="w-full h-44 object-cover block" />
            <div className="p-5">
              <p className="text-[12px] font-bold mb-3" style={{ color: "#8A7A6A" }}>생활 습관</p>
              <div className="flex items-baseline gap-2 mb-0.5">
                <span className="text-[32px] font-extrabold" style={{ color: "#2A2A2A" }}>{adherence ?? "-"}{adherence != null && "%"}</span>
              </div>
              <p className="text-[12px] mb-3" style={{ color: "#8A7A6A" }}>최근 7일 복약 순응률</p>
              <div className="flex items-center gap-1.5">
                <Activity className="w-4 h-4" style={{ color: C.success }} />
                <span className="text-[13px]" style={{ color: "#2A2A2A" }}>
                  {last7Logs.length > 0 ? `최근 7일 기록 ${last7Logs.length}건` : "최근 기록 없음"}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 4px 28px rgba(30,26,23,0.09)" }}>
            <img src={unsplash("photo-1512941937669-90a1b58e7e9c", 400, 200)} alt="스마트폰" className="w-full h-44 object-cover block" />
            <div className="p-5">
              <p className="text-[12px] font-bold mb-3" style={{ color: "#8A7A6A" }}>알림 설정</p>
              <p className="text-[12px] mb-1" style={{ color: "#8A7A6A" }}>복약 알림</p>
              <p className="text-[17px] font-extrabold mb-0.5" style={{ color: "#2A2A2A" }}>{notifSettings?.medication_reminder_enabled ? "켜짐" : "꺼짐"}</p>
              <p className="text-[13px] mb-4" style={{ color: "#8A7A6A" }}>
                전체 푸시 수신 {notifSettings?.all_push_enabled ? "켜짐" : "꺼짐"}
              </p>
              <button className="w-full py-2.5 rounded-full text-[13px] font-bold text-white" style={{ background: "#C16A45" }} onClick={() => navigate("/notification")}>알림 관리하기</button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-5 py-16 md:px-10 md:py-[100px] text-center" style={{ background: "#1C1410" }}>
        <span className="inline-block text-[13px] border rounded-[20px] px-4 py-2 mb-6" style={{ color: "#D9C8B8", borderColor: "#4A3B2E" }}>지역사회 보건 서비스 지원</span>
        <h2 className="text-[26px] md:text-[36px] font-extrabold leading-[1.4] text-white break-keep">믿을 수 있는 건강 관리<br />파트너와 함께합니다</h2>
      </div>

      <div className="px-5 py-16 md:px-10 md:py-[100px] text-center" style={{ background: "#F5EDE4" }}>
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6" style={{ background: "#C16A45" }}>
          <Mail className="w-7 h-7 text-white" strokeWidth={2.2} />
        </div>
        <h3 className="text-[24px] md:text-[28px] font-extrabold mb-4" style={{ color: "#2A2A2A" }}>건강 정보 뉴스레터 구독</h3>
        <p className="text-[14px] mb-8 leading-[1.6]" style={{ color: "#8A7A6A" }}>
          매주 새로운 건강 팁과 복약 관리 정보를 이메일로 받아보세요.<br />
          언제든지 구독을 취소할 수 있습니다.
        </p>
        <div className="flex flex-col sm:flex-row justify-center gap-2 max-w-[500px] mx-auto">
          <input
            className="flex-1 px-5 py-3.5 rounded-[30px] text-[14px] outline-none"
            style={{ border: "1px solid #E0D3C4" }}
            placeholder="이메일 주소를 입력하세요"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="px-7 py-3.5 rounded-[30px] text-white font-bold" style={{ background: "#2A211B" }}>구독하기</button>
        </div>
      </div>
    </div>
  );
}
