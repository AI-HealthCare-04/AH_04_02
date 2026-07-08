import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import NavBar from "../components/NavBar";
import { getLogs, getSchedules, type MedicationLogEntry, type Schedule } from "../api/monitoring";
import { getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

export default function DrugDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { scheduleId } = useParams<{ scheduleId: string }>();
  const stateSchedule = (location.state as { schedule?: Schedule } | null)?.schedule;

  const [schedule, setSchedule] = useState<Schedule | null>(stateSchedule ?? null);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [loading, setLoading] = useState(!stateSchedule);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!scheduleId) return;
    const id = Number(scheduleId);
    const patientId = getCurrentPatientId();

    const loadSchedule = stateSchedule
      ? Promise.resolve(stateSchedule)
      : getSchedules(patientId, false).then((list) => list.find((s) => s.id === id) ?? null);

    Promise.all([loadSchedule, getLogs(patientId, 60)])
      .then(([s, allLogs]) => {
        setSchedule(s);
        setLogs(allLogs.filter((l) => l.schedule_id === id));
      })
      .catch(() => setError("약품 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scheduleId]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김보호" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/monitoring")}
          className="flex items-center gap-1 text-[13px] font-bold mb-6 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 모니터링으로 돌아가기
        </button>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : !schedule ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "약품 정보를 찾을 수 없어요."}</p>
        ) : (
          <>
            <div
              className="rounded-3xl p-7 mb-5"
              style={{ background: `linear-gradient(135deg, ${C.terracotta} 0%, #A5522F 100%)`, boxShadow: "0 8px 32px rgba(193,101,61,0.30)" }}
            >
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 text-[32px]" style={{ background: "rgba(255,255,255,0.18)" }}>💊</div>
                <div className="flex-1">
                  <p className="text-[13px] font-bold mb-1" style={{ color: "rgba(255,255,255,0.65)" }}>
                    {schedule.active ? "사용 중" : "중지됨"}
                  </p>
                  <h1 className="text-[26px] font-black leading-tight mb-2" style={{ color: C.white }}>{schedule.drug_name}</h1>
                  <div className="flex flex-wrap gap-2">
                    <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                      복용 시간 {schedule.time_slot}
                    </span>
                    {schedule.memo && (
                      <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                        {schedule.memo}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2.5 px-4 py-3.5 rounded-2xl mb-5" style={{ background: C.warningBg, border: `1px solid ${C.warningBorder}` }}>
              <span className="text-[14px] shrink-0">ℹ️</span>
              <p className="text-[12px] leading-relaxed" style={{ color: C.warningText }}>
                복용법·주의사항 등 상세 의약품 정보는 아직 준비 중이에요. 정확한 복약 지도는 담당 의사·약사에게 확인하세요.
              </p>
            </div>

            <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
              <div className="px-6 py-4 border-b" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                <h2 className="text-[15px] font-black" style={{ color: C.dark }}>최근 복용 기록</h2>
              </div>
              {logs.length === 0 ? (
                <p className="px-6 py-8 text-center text-[14px]" style={{ color: C.muted }}>기록이 없어요.</p>
              ) : (
                logs
                  .sort((a, b) => +new Date(b.checked_at) - +new Date(a.checked_at))
                  .slice(0, 20)
                  .map((log) => (
                    <div key={log.id} className="flex items-center justify-between px-6 py-3.5 border-b last:border-0" style={{ borderColor: "rgba(30,26,23,0.06)" }}>
                      <span className="text-[13px]" style={{ color: C.dark }}>
                        {new Date(log.checked_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span
                        className="px-3 py-1 rounded-full text-[12px] font-bold"
                        style={{
                          background: log.status === "taken" ? `${C.success}20` : "rgba(217,79,79,0.12)",
                          color: log.status === "taken" ? "#4A7A47" : "#D94F4F",
                        }}
                      >
                        {log.status === "taken" ? "복용완료" : "건너뜀"}
                      </span>
                    </div>
                  ))
              )}
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => navigate("/chat")}
                className="flex-1 py-4 rounded-full font-bold text-[15px] border-2 transition-all"
                style={{ borderColor: C.terracotta, color: C.terracotta }}
              >
                챗봇에게 질문하기 💬
              </button>
              <button
                onClick={() => navigate("/monitoring")}
                className="flex-1 py-4 rounded-full font-bold text-[15px] text-white transition-all"
                style={{ background: C.terracotta }}
              >
                확인 완료
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
