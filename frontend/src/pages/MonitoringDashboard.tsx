import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Users } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import {
  getCaregiverPatients,
  getLogs,
  getSchedules,
  type MedicationLogEntry,
  type Patient,
  type Schedule,
} from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentPatientId, getCurrentUserName, isLoggedIn } from "../lib/session";
import { C } from "../theme";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function dateKey(iso: string) {
  return iso.slice(0, 10); // YYYY-MM-DD (checked_at은 ISO 문자열)
}

// [2026-07-24 추가] 여러 환자를 관리하는 보호자·기관 입장에서 특정 환자 한 명을 골라야만
// 뭔가 볼 수 있던 게 불편하다는 요청 — patient_id 쿼리파라미터가 없으면 전체 환자를
// 오늘 상태(today_status, 환자 관리 목록의 빨강/초록 점과 동일한 값이라 추가 API 호출
// 없이 바로 재사용 가능) 기준으로 요약해서 보여주고, 특정 환자를 고르면(카드 클릭 또는
// PatientManagement.tsx의 "모니터링" 버튼) 그 환자의 상세 화면(기존 UI 그대로)으로 전환된다.
function MonitoringSummary({ patients, onSelect }: { patients: Patient[]; onSelect: (id: number) => void }) {
  const missed = patients.filter((p) => p.today_status === "missed");
  const ok = patients.filter((p) => p.today_status === "ok");
  // 놓친 환자를 먼저 보여줘야 바로 조치할 수 있다.
  const sorted = [...missed, ...ok];

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="rounded-2xl p-5 flex items-center gap-3" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.terracotta}15` }}>
            <Users className="w-5 h-5" style={{ color: C.terracotta }} />
          </div>
          <div>
            <p className="text-[22px] font-black" style={{ color: C.dark }}>{patients.length}</p>
            <p className="text-[12px] font-bold" style={{ color: C.muted }}>전체 환자</p>
          </div>
        </div>
        <div className="rounded-2xl p-5 flex items-center gap-3" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: "rgba(217,79,79,0.12)" }}>
            <AlertTriangle className="w-5 h-5" style={{ color: "#D94F4F" }} />
          </div>
          <div>
            <p className="text-[22px] font-black" style={{ color: missed.length > 0 ? "#D94F4F" : C.dark }}>{missed.length}</p>
            <p className="text-[12px] font-bold" style={{ color: C.muted }}>오늘 놓침</p>
          </div>
        </div>
        <div className="rounded-2xl p-5 flex items-center gap-3" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.success}20` }}>
            <CheckCircle2 className="w-5 h-5" style={{ color: "#4A7A47" }} />
          </div>
          <div>
            <p className="text-[22px] font-black" style={{ color: C.dark }}>{ok.length}</p>
            <p className="text-[12px] font-bold" style={{ color: C.muted }}>오늘 정상</p>
          </div>
        </div>
      </div>

      <div className="rounded-2xl overflow-hidden mb-6" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
        <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
          <h2 className="text-[16px] font-black" style={{ color: C.dark }}>환자별 현황</h2>
        </div>
        {sorted.length === 0 ? (
          <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>연결된 환자가 없어요.</p>
        ) : (
          sorted.map((p, i) => (
            <button
              key={p.id}
              onClick={() => onSelect(p.id)}
              className="w-full flex items-center justify-between px-6 py-4 text-left transition-colors hover:bg-black/[0.02]"
              style={{ borderBottom: i < sorted.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ background: p.today_status === "missed" ? "#D94F4F" : C.success }}
                />
                <span className="font-bold text-[15px]" style={{ color: C.dark }}>{p.name}</span>
              </div>
              <span
                className="px-3 py-1 rounded-full text-[12px] font-bold"
                style={{
                  background: p.today_status === "missed" ? "rgba(217,79,79,0.12)" : `${C.success}20`,
                  color: p.today_status === "missed" ? "#D94F4F" : "#4A7A47",
                }}
              >
                {p.today_status === "missed" ? "오늘 놓침" : "오늘 정상"}
              </span>
            </button>
          ))
        )}
      </div>
    </>
  );
}

export default function MonitoringDashboard() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  // [2026-07-27 추가] 환자 본인 계정은 caregiverId가 없다 — 여러 환자 중 고를 필요 없이
  // 항상 자기 자신의 기록을 본다.
  const selfPatientId = getCurrentPatientId();
  const [searchParams, setSearchParams] = useSearchParams();
  // [2026-07-24 수정] localStorage의 "마지막으로 본 환자"에 암묵적으로 의존하던 걸
  // patient_id 쿼리파라미터로 바꿨다 — 없으면 요약 화면, 있으면 그 환자의 상세 화면이라는
  // 게 URL만 보고도 명확해지고, 새로고침·공유해도 같은 화면이 뜬다.
  const patientIdParam = searchParams.get("patient_id");
  const patientId = patientIdParam ? Number(patientIdParam) : caregiverId ? null : selfPatientId;

  const [patients, setPatients] = useState<Patient[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [calMonth, setCalMonth] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });

  const selectPatient = (id: number) => {
    localStorage.setItem("patient_id", String(id));
    setSearchParams({ patient_id: String(id) });
  };

  useEffect(() => {
    // [2026-07-27 수정] caregiverId가 없으면 환자 본인 계정 — getCaregiverPatients를 부를
    // 필요가 없다(고를 환자 목록 자체가 없음). patientId는 위에서 이미 selfPatientId로
    // 정해져 있으니 아래 두 번째 effect가 그 값으로 로딩을 마무리한다. selfPatientId까지
    // 없는 비정상 상태일 때만 에러로 끝낸다(PatientManagement.tsx와 동일한 패턴).
    if (!caregiverId) {
      if (selfPatientId == null) {
        setError("로그인 정보를 확인할 수 없어요.");
        setLoading(false);
      }
      return;
    }
    getCaregiverPatients(caregiverId)
      .then(setPatients)
      .catch(() => {})
      .finally(() => {
        if (patientId == null) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId]);

  useEffect(() => {
    if (patientId == null) return;
    setLoading(true);
    Promise.all([getSchedules(patientId, false), getLogs(patientId, 45)])
      .then(([s, l]) => {
        setSchedules(s);
        setLogs(l);
      })
      .catch(() => setError("모니터링 데이터를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const now = Date.now();
  const last7 = useMemo(
    () => logs.filter((l) => now - new Date(l.checked_at).getTime() <= 7 * 24 * 60 * 60 * 1000),
    [logs, now]
  );
  const takenCount = last7.filter((l) => l.status === "taken").length;
  // [2026-07-19] "건너뜀"(사용자가 직접 건너뛴 것)과 "놓침"(스케줄러가 감지한 무응답)을
  // 합쳐서 이행률 미달로 집계한다 — 이 페이지의 missedCount는 항상 "복용 안 함" 전체를 뜻했다.
  const missedCount = last7.filter((l) => l.status === "skipped" || l.status === "missed").length;
  const adherence = last7.length > 0 ? Math.round((takenCount / last7.length) * 100) : null;

  const dayStatus = useMemo(() => {
    const byDay = new Map<string, { taken: number; total: number }>();
    logs.forEach((l) => {
      const key = dateKey(l.checked_at);
      const entry = byDay.get(key) ?? { taken: 0, total: 0 };
      entry.total += 1;
      if (l.status === "taken") entry.taken += 1;
      byDay.set(key, entry);
    });
    const result = new Map<string, "all" | "partial" | "none">();
    byDay.forEach((v, k) => {
      result.set(k, v.taken === v.total ? "all" : v.taken > 0 ? "partial" : "none");
    });
    return result;
  }, [logs]);

  const calCells = useMemo(() => {
    const { year, month } = calMonth;
    const firstWeekday = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();
    const cells: (number | null)[] = Array(firstWeekday).fill(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    return cells;
  }, [calMonth]);

  const isFutureMonth = (() => {
    const n = new Date();
    return calMonth.year > n.getFullYear() || (calMonth.year === n.getFullYear() && calMonth.month >= n.getMonth() + 1);
  })();

  const dotColor = { all: C.success, partial: C.terracottaLight, none: "#D9C8B8" } as const;

  const recentLogs = useMemo(
    () => [...logs].sort((a, b) => +new Date(b.checked_at) - +new Date(a.checked_at)).slice(0, 10),
    [logs]
  );

  if (patientId == null) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
        <main className="max-w-4xl mx-auto px-6 sm:px-8 py-10">
          <h1 className="text-[24px] font-black mb-1" style={{ color: C.dark }}>모니터링 대시보드</h1>
          <p className="text-[14px] mb-7" style={{ color: C.muted }}>연결된 환자들의 오늘 복약 현황을 한눈에 확인하세요.</p>
          {error ? (
            <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error}</p>
          ) : loading ? (
            <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
          ) : (
            <MonitoringSummary patients={patients} onSelect={selectPatient} />
          )}
        </main>
      </div>
    );
  }

  const selectedPatient = patients.find((p) => p.id === patientId);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-4xl mx-auto px-6 sm:px-8 py-10">
        {/* [2026-07-27 수정] "전체 요약"은 여러 환자를 관리하는 보호자·기관 전용 화면이라
            환자 본인 계정에는 돌아갈 곳이 없다 — caregiverId가 있을 때만 보여준다. */}
        {caregiverId && (
          <button
            onClick={() => setSearchParams({})}
            className="text-[13px] font-bold mb-3 inline-block"
            style={{ color: C.muted }}
          >
            ← 전체 요약
          </button>
        )}
        <h1 className="text-[24px] font-black mb-6" style={{ color: C.dark }}>
          {!caregiverId ? "나의 복약 기록" : selectedPatient ? `${selectedPatient.name}님 모니터링` : "모니터링 대시보드"}
        </h1>

        {patients.length > 0 && (
          <div className="flex items-center gap-3 mb-7">
            <label className="text-[14px] font-bold" style={{ color: C.muted }}>대상자 선택</label>
            <select
              value={patientId ?? ""}
              onChange={(e) => selectPatient(Number(e.target.value))}
              className="px-4 py-2.5 rounded-xl border text-[14px] outline-none bg-white"
              style={{ borderColor: "rgba(30,26,23,0.15)", minWidth: 200 }}
            >
              {patients.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: C.muted }}>복약 이행률 (최근 7일)</p>
                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-[32px] font-black" style={{ color: C.dark }}>{adherence ?? "—"}</span>
                  {adherence !== null && <span className="text-[15px] font-bold" style={{ color: C.muted }}>%</span>}
                </div>
                <p className="text-[12px]" style={{ color: C.muted }}>
                  {last7.length > 0 ? `${last7.length}건 중 ${takenCount}건 복용` : "기록된 복약 없음"}
                </p>
              </div>
              <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: C.muted }}>이번 주 누락</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-[32px] font-black" style={{ color: missedCount > 0 ? "#D94F4F" : C.dark }}>{missedCount}</span>
                  <span className="text-[15px] font-bold" style={{ color: C.muted }}>건</span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl overflow-hidden mb-6" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              <div className="px-6 py-4 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <h2 className="text-[16px] font-black" style={{ color: C.dark }}>등록된 약 전체</h2>
                <span className="text-[12px]" style={{ color: C.muted }}>약 이름을 클릭하면 상세 정보를 볼 수 있어요</span>
              </div>
              {schedules.length === 0 ? (
                <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>등록된 약이 없어요.</p>
              ) : (
                <>
                  {/* 모바일: 좁은 화면에서 표 컬럼이 한 글자씩 줄바꿈되는 걸 피하려고 카드형으로 */}
                  <div className="sm:hidden">
                    {schedules.map((s, i) => (
                      <div
                        key={s.id}
                        className="px-5 py-4 cursor-pointer transition-colors hover:bg-black/[0.02]"
                        style={{ borderBottom: i < schedules.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}
                        onClick={() => navigate(`/drugs/${s.id}`, { state: { schedule: s } })}
                      >
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="font-bold text-[15px]" style={{ color: C.terracotta }}>{s.drug_name}</span>
                          <span
                            className="shrink-0 px-3 py-1 rounded-full text-[12px] font-bold"
                            style={{ background: s.active ? `${C.success}20` : "rgba(30,26,23,0.07)", color: s.active ? "#4A7A47" : C.muted }}
                          >
                            {s.active ? "사용 중" : "중지"}
                          </span>
                        </div>
                        <p className="text-[13px]" style={{ color: C.muted }}>{s.time_slot}{s.memo ? ` · ${s.memo}` : ""}</p>
                      </div>
                    ))}
                  </div>
                  <table className="w-full hidden sm:table">
                    <thead>
                      <tr style={{ borderBottom: "1px solid rgba(30,26,23,0.08)" }}>
                        {["약 이름", "복용 시간", "메모", "사용 여부"].map((h) => (
                          <th key={h} className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wider" style={{ color: C.muted }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {schedules.map((s, i) => (
                        <tr
                          key={s.id}
                          className="cursor-pointer transition-colors hover:bg-black/[0.02]"
                          style={{ borderBottom: i < schedules.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}
                          onClick={() => navigate(`/drugs/${s.id}`, { state: { schedule: s } })}
                        >
                          <td className="px-5 py-3.5 font-bold text-[14px] hover:underline" style={{ color: C.terracotta }}>{s.drug_name}</td>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>{s.time_slot}</td>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>{s.memo || "—"}</td>
                          <td className="px-5 py-3.5">
                            <span
                              className="px-3 py-1 rounded-full text-[12px] font-bold"
                              style={{ background: s.active ? `${C.success}20` : "rgba(30,26,23,0.07)", color: s.active ? "#4A7A47" : C.muted }}
                            >
                              {s.active ? "사용 중" : "중지"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>

            <div className="rounded-2xl p-6 mb-6" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-[16px] font-black" style={{ color: C.dark }}>이번 달 복약 현황</h2>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() =>
                      setCalMonth((p) => (p.month === 1 ? { year: p.year - 1, month: 12 } : { ...p, month: p.month - 1 }))
                    }
                    className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-black/5 text-[18px] font-bold"
                    style={{ color: C.dark }}
                  >
                    ‹
                  </button>
                  <span className="text-[14px] font-black px-3 min-w-[100px] text-center" style={{ color: C.dark }}>
                    {calMonth.year}년 {calMonth.month}월
                  </span>
                  <button
                    onClick={() =>
                      !isFutureMonth &&
                      setCalMonth((p) => (p.month === 12 ? { year: p.year + 1, month: 1 } : { ...p, month: p.month + 1 }))
                    }
                    className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-black/5 text-[18px] font-bold"
                    style={{ color: isFutureMonth ? "rgba(30,26,23,0.2)" : C.dark, cursor: isFutureMonth ? "not-allowed" : "pointer" }}
                  >
                    ›
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-7 mb-1">
                {WEEKDAYS.map((d) => (
                  <div key={d} className="text-center text-[11px] font-bold py-1.5" style={{ color: C.muted }}>{d}</div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-y-0.5">
                {calCells.map((day, i) => {
                  if (!day) return <div key={i} className="py-2" />;
                  const key = `${calMonth.year}-${String(calMonth.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                  const st = dayStatus.get(key);
                  return (
                    <button
                      key={i}
                      onClick={() => navigate(`/monitoring/logs/${key}?patient_id=${patientId}`)}
                      className="flex flex-col items-center py-2 rounded-xl transition-colors hover:bg-black/[0.05]"
                    >
                      <span className="text-[12px] font-bold mb-1" style={{ color: C.dark }}>{day}</span>
                      {st ? <div className="w-2 h-2 rounded-full" style={{ background: dotColor[st] }} /> : <div className="w-2 h-2" />}
                    </button>
                  );
                })}
              </div>
              <div className="flex items-center gap-5 mt-4 pt-4 border-t" style={{ borderColor: "rgba(30,26,23,0.07)" }}>
                {[{ color: C.success, label: "전부 복용" }, { color: C.terracottaLight, label: "일부 복용" }, { color: "#D9C8B8", label: "미복용" }].map(
                  ({ color, label }) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                      <span className="text-[12px]" style={{ color: C.muted }}>{label}</span>
                    </div>
                  )
                )}
              </div>
            </div>

            <div className="rounded-2xl overflow-hidden mb-6" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <h2 className="text-[16px] font-black" style={{ color: C.dark }}>최근 복약 기록</h2>
              </div>
              {recentLogs.length === 0 ? (
                <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>기록이 없어요.</p>
              ) : (
                <>
                  <div className="sm:hidden">
                    {recentLogs.map((r, i) => (
                      <div key={r.id} className="px-5 py-4" style={{ borderBottom: i < recentLogs.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="font-semibold text-[14px]" style={{ color: C.dark }}>{r.drug_name}</span>
                          <span
                            className="shrink-0 px-3 py-1 rounded-full text-[12px] font-bold"
                            style={{
                              background: r.status === "taken" ? `${C.success}20` : "rgba(217,79,79,0.12)",
                              color: r.status === "taken" ? "#4A7A47" : "#D94F4F",
                            }}
                          >
                            {r.status === "taken" ? "복용완료" : r.status === "missed" ? "놓침" : "건너뜀"}
                          </span>
                        </div>
                        <p className="text-[13px]" style={{ color: C.muted }}>
                          {new Date(r.checked_at).toLocaleDateString("ko-KR")} · {r.time_slot}
                        </p>
                      </div>
                    ))}
                  </div>
                  <table className="w-full hidden sm:table">
                    <thead>
                      <tr style={{ borderBottom: "1px solid rgba(30,26,23,0.08)" }}>
                        {["날짜", "약 이름", "복용 시간", "상태"].map((h) => (
                          <th key={h} className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wider" style={{ color: C.muted }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {recentLogs.map((r) => (
                        <tr key={r.id} style={{ borderBottom: "1px solid rgba(30,26,23,0.06)" }}>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>
                            {new Date(r.checked_at).toLocaleDateString("ko-KR")}
                          </td>
                          <td className="px-5 py-3.5 font-semibold text-[14px]" style={{ color: C.dark }}>{r.drug_name}</td>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>{r.time_slot}</td>
                          <td className="px-5 py-3.5">
                            <span
                              className="px-3 py-1 rounded-full text-[12px] font-bold"
                              style={{
                                background: r.status === "taken" ? `${C.success}20` : "rgba(217,79,79,0.12)",
                                color: r.status === "taken" ? "#4A7A47" : "#D94F4F",
                              }}
                            >
                              {r.status === "taken" ? "복용완료" : r.status === "missed" ? "놓침" : "건너뜀"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
