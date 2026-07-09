import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import {
  getCaregiverPatients,
  getLogs,
  getSchedules,
  type MedicationLogEntry,
  type Patient,
  type Schedule,
} from "../api/monitoring";
import { getLatestAssessment, type AssessmentResult } from "../api/care";
import { getCurrentCaregiverId, getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

const CARE_LEVEL_LABEL: Record<AssessmentResult["care_level"], string> = {
  independent: "자가관리 가능",
  guardian_check: "보호자 확인 필요",
  third_party_needed: "제3자 도움 필요",
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function dateKey(iso: string) {
  return iso.slice(0, 10); // YYYY-MM-DD (checked_at은 ISO 문자열)
}

export default function MonitoringDashboard() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();

  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState<number>(getCurrentPatientId());
  const [assessment, setAssessment] = useState<AssessmentResult | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [calMonth, setCalMonth] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  });

  useEffect(() => {
    if (!caregiverId) return;
    getCaregiverPatients(caregiverId)
      .then((list) => {
        setPatients(list);
        if (list.length > 0 && !list.some((p) => p.id === patientId)) {
          setPatientId(list[0].id);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getLatestAssessment(patientId).catch(() => null),
      getSchedules(patientId, false),
      getLogs(patientId, 45),
    ])
      .then(([a, s, l]) => {
        setAssessment(a);
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
  const missedCount = last7.filter((l) => l.status === "skipped").length;
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

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김보호" />
      <main className="max-w-4xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[24px] font-black mb-6" style={{ color: C.dark }}>모니터링 대시보드</h1>

        {patients.length > 0 && (
          <div className="flex items-center gap-3 mb-7">
            <label className="text-[14px] font-bold" style={{ color: C.muted }}>대상자 선택</label>
            <select
              value={patientId}
              onChange={(e) => setPatientId(Number(e.target.value))}
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
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
              <div className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: C.muted }}>도움 단계</p>
                {assessment ? (
                  <span
                    className="inline-block px-4 py-2 rounded-full text-[13px] font-black"
                    style={{ background: `${C.terracotta}18`, color: C.terracotta, border: `1.5px solid ${C.terracotta}40` }}
                  >
                    {CARE_LEVEL_LABEL[assessment.care_level]}
                  </span>
                ) : (
                  <p className="text-[13px]" style={{ color: C.muted }}>자가진단 기록 없음</p>
                )}
                {assessment && (
                  <p className="text-[12px] mt-3" style={{ color: C.muted }}>
                    최근 평가: {new Date(assessment.evaluated_at).toLocaleDateString("ko-KR")}
                  </p>
                )}
              </div>
              <div className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: C.muted }}>복약 이행률 (최근 7일)</p>
                <div className="flex items-baseline gap-1 mb-3">
                  <span className="text-[32px] font-black" style={{ color: C.dark }}>{adherence ?? "—"}</span>
                  {adherence !== null && <span className="text-[15px] font-bold" style={{ color: C.muted }}>%</span>}
                </div>
                <p className="text-[12px]" style={{ color: C.muted }}>
                  {last7.length > 0 ? `${last7.length}건 중 ${takenCount}건 복용` : "기록된 복약 없음"}
                </p>
              </div>
              <div className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <p className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: C.muted }}>이번 주 누락</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-[32px] font-black" style={{ color: missedCount > 0 ? "#D94F4F" : C.dark }}>{missedCount}</span>
                  <span className="text-[15px] font-bold" style={{ color: C.muted }}>건</span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl overflow-hidden mb-6" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              <div className="px-6 py-4 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <h2 className="text-[16px] font-black" style={{ color: C.dark }}>등록된 약 전체</h2>
                <span className="text-[12px]" style={{ color: C.muted }}>약 이름을 클릭하면 상세 정보를 볼 수 있어요</span>
              </div>
              {schedules.length === 0 ? (
                <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>등록된 약이 없어요.</p>
              ) : (
                <table className="w-full">
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
              )}
            </div>

            <div className="rounded-2xl p-6 mb-6" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
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

            <div className="rounded-2xl overflow-hidden mb-6" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <h2 className="text-[16px] font-black" style={{ color: C.dark }}>최근 복약 기록</h2>
              </div>
              {recentLogs.length === 0 ? (
                <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>기록이 없어요.</p>
              ) : (
                <table className="w-full">
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
                            {r.status === "taken" ? "복용완료" : "건너뜀"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
