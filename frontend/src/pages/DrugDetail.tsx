import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  Archive,
  Ban,
  ChevronLeft,
  Frown,
  Info,
  Loader2,
  MessageCircle,
  Pill,
  ShieldAlert,
  Shuffle,
  Stethoscope,
  TriangleAlert,
} from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import PatientContextBanner from "../components/PatientContextBanner";
import { checkIntake, getLogs, getSchedules, type MedicationLogEntry, type Schedule } from "../api/monitoring";
import { getDrugIndication, type DrugIndicationInfo } from "../api/records";
import { getCurrentCaregiverId, getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

export default function DrugDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { scheduleId } = useParams<{ scheduleId: string }>();
  const stateSchedule = (location.state as { schedule?: Schedule } | null)?.schedule;
  const patientId = useGuardedPatientId();

  const [schedule, setSchedule] = useState<Schedule | null>(stateSchedule ?? null);
  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [drugInfo, setDrugInfo] = useState<DrugIndicationInfo | null>(null);
  const [drugInfoLoading, setDrugInfoLoading] = useState(false);
  const [loading, setLoading] = useState(!stateSchedule);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!scheduleId || patientId == null) return;
    const id = Number(scheduleId);

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
  }, [scheduleId, patientId]);

  useEffect(() => {
    if (!schedule) return;
    // [2026-07-21 추가] e약은요/허가정보/DUR live 조회(_fetch_rag_drug_detail)는 후보 이름별로
    // 순차 API 호출이 여러 번 걸려 수 초가 걸릴 수 있다 — drugInfo가 null인 로딩 중과
    // "조회했지만 없음"을 구분 못 해서, 로딩 중에도 "확인하지 못했어요"가 먼저 보이던 문제.
    setDrugInfoLoading(true);
    getDrugIndication(schedule.drug_name)
      .then(setDrugInfo)
      .catch(() => setDrugInfo(null))
      .finally(() => setDrugInfoLoading(false));
  }, [schedule]);

  const hasPatientSummary = !!(
    drugInfo?.patient_summary &&
    (drugInfo.patient_summary.must_check.length ||
      drugInfo.patient_summary.tell_doctor.length ||
      drugInfo.patient_summary.avoid_together.length)
  );

  // 모니터링(보호자용) 화면에서만 오는 경로라, 여기서 체크하면 "보호자가 대신" 기록으로 남깁니다.
  const handleCheck = async (status: "taken" | "skipped") => {
    if (!scheduleId || checking || patientId == null) return;
    setChecking(true);
    try {
      await checkIntake(scheduleId, status, getCurrentCaregiverId() ?? undefined);
      const allLogs = await getLogs(patientId, 60);
      setLogs(allLogs.filter((l) => l.schedule_id === Number(scheduleId)));
    } catch {
      setError("체크에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner afterSwitchPath="/monitoring" />
        <button
          onClick={() => navigate("/monitoring")}
          className="flex items-center gap-1 text-[13px] font-bold mb-6 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 모니터링으로 돌아가기
        </button>

        {loading ? (
          <>
            <div className="rounded-3xl p-7 mb-5" style={{ background: "rgba(193,101,61,0.15)" }}>
              <div className="flex items-start gap-5">
                <Skeleton className="w-16 h-16 shrink-0" style={{ background: "rgba(193,101,61,0.25)" }} />
                <div className="flex-1">
                  <Skeleton className="h-3 w-20 mb-3" style={{ background: "rgba(193,101,61,0.25)" }} />
                  <Skeleton className="h-6 w-40 mb-2" style={{ background: "rgba(193,101,61,0.25)" }} />
                </div>
              </div>
            </div>
            <div className="flex gap-3 mb-5">
              <Skeleton className="h-[52px] flex-1" />
              <Skeleton className="h-[52px] flex-1" />
            </div>
            <div className="space-y-4">
              {[1, 2].map((i) => (
                <div key={i} className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <Skeleton className="h-4 w-28 mb-3" />
                  <Skeleton className="h-3 w-full mb-2" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              ))}
            </div>
          </>
        ) : !schedule ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "약품 정보를 찾을 수 없어요."}</p>
        ) : (
          <>
            <div
              className="rounded-3xl p-7 mb-5"
              style={{ background: `linear-gradient(135deg, ${C.terracotta} 0%, #A5522F 100%)`, boxShadow: "0 8px 32px rgba(193,101,61,0.30)" }}
            >
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.22)" }}>
                  <Pill className="w-8 h-8" style={{ color: C.white }} strokeWidth={2.2} />
                </div>
                <div className="flex-1">
                  <p className="text-[13px] font-bold mb-1" style={{ color: "rgba(255,255,255,0.65)" }}>
                    {schedule.active ? "사용 중" : "중지됨"}
                  </p>
                  <h1 className="text-[26px] font-black leading-tight mb-2" style={{ color: C.white }}>{schedule.drug_name}</h1>
                  <div className="flex flex-wrap gap-2">
                    {drugInfo?.drug_class && (
                      <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                        {drugInfo.drug_class}
                      </span>
                    )}
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

            <div className="flex gap-3 mb-5">
              <button
                onClick={() => handleCheck("taken")}
                disabled={checking}
                className="flex-1 py-3.5 rounded-full font-bold text-[14px] text-white transition-all disabled:opacity-50"
                style={{ background: C.success }}
              >
                ✓ 오늘 복용 확인
              </button>
              <button
                onClick={() => handleCheck("skipped")}
                disabled={checking}
                className="flex-1 py-3.5 rounded-full font-bold text-[14px] border-2 transition-all disabled:opacity-50"
                style={{ borderColor: "rgba(30,26,23,0.15)", color: C.muted }}
              >
                건너뛰었어요
              </button>
            </div>

            <div className="flex items-start gap-2.5 px-4 py-3.5 rounded-2xl mb-5" style={{ background: C.warningBg, border: `1px solid ${C.warningBorder}` }}>
              <Info className="w-[14px] h-[14px] shrink-0" style={{ color: C.warningText }} strokeWidth={2.2} />
              <p className="text-[12px] leading-relaxed" style={{ color: C.warningText }}>
                아래 정보는 일반적인 복약 안내입니다. 정확한 복약 지도는 담당 의사·약사에게 확인하세요.
              </p>
            </div>

            {drugInfo?.indication && (
              <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                <div className="flex items-center gap-2.5 mb-3">
                  <Stethoscope className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                  <h2 className="text-[15px] font-black" style={{ color: C.dark }}>적응증</h2>
                </div>
                <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.indication}</p>
              </div>
            )}

            {/* [2026-07-20] 복약 일정(MedicationSchedule)은 처방전 OCR 기록과 연결돼 있지
                않아서, rag/ 패키지의 e약은요·DUR live API를 약품명만으로 온디맨드 보강
                조회한다(GET /ocr/drug-info, ocr_router.py의 _fetch_rag_drug_detail) —
                미등재 약품이거나 조회 실패 시엔 필드별로 null이라 아래에서 조건부 렌더링. */}
            {/* [2026-07-20 추가] 허가사항/e약은요 원문은 의료 전문용어라 환자가 그대로 읽기
                어렵다 — LLM이 "꼭 확인/의사·약사에게 알려주세요/함께 피할 것" 3분류로 쉽게
                요약해둔 게 있으면 그걸 우선 보여주고, 없으면(LLM 미사용/실패) 원문 카드로
                폴백한다. */}
            {drugInfoLoading ? (
              <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                <div className="flex items-center gap-2.5">
                  <Loader2 className="w-[18px] h-[18px] animate-spin" style={{ color: C.terracotta }} strokeWidth={2.2} />
                  <p className="text-[13px]" style={{ color: C.muted }}>
                    주의사항·부작용·약물 상호작용·보관 방법을 조회하는 중이에요...
                  </p>
                </div>
              </div>
            ) : hasPatientSummary ? (
              <>
                {!!drugInfo?.patient_summary?.must_check.length && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <TriangleAlert className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>꼭 확인하세요</h2>
                    </div>
                    {drugInfo.patient_summary.must_check.map((line, i) => (
                      <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                    ))}
                  </div>
                )}

                {!!drugInfo?.patient_summary?.tell_doctor.length && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <MessageCircle className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>의사·약사에게 알려주세요</h2>
                    </div>
                    {drugInfo.patient_summary.tell_doctor.map((line, i) => (
                      <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                    ))}
                  </div>
                )}

                {!!drugInfo?.patient_summary?.avoid_together.length && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <Ban className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>함께 조심하세요</h2>
                    </div>
                    {drugInfo.patient_summary.avoid_together.map((line, i) => (
                      <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                {drugInfo?.precautions && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <TriangleAlert className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>주의사항</h2>
                    </div>
                    <p className="text-[14px] leading-relaxed whitespace-pre-line" style={{ color: C.dark }}>{drugInfo.precautions}</p>
                  </div>
                )}

                {drugInfo?.side_effects && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <Frown className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>부작용</h2>
                    </div>
                    <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.side_effects}</p>
                  </div>
                )}

                {drugInfo?.interactions && (
                  <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                    <div className="flex items-center gap-2.5 mb-3">
                      <Shuffle className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                      <h2 className="text-[15px] font-black" style={{ color: C.dark }}>약물 상호작용</h2>
                    </div>
                    <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.interactions}</p>
                  </div>
                )}
              </>
            )}

            {drugInfo?.storage && (
              <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                <div className="flex items-center gap-2.5 mb-3">
                  <Archive className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                  <h2 className="text-[15px] font-black" style={{ color: C.dark }}>보관 방법</h2>
                </div>
                <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.storage}</p>
              </div>
            )}

            {!!drugInfo?.dur_cautions?.length && (
              <div className="rounded-2xl p-6 mb-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                <div className="flex items-center gap-2.5 mb-3">
                  <ShieldAlert className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} />
                  <h2 className="text-[15px] font-black" style={{ color: C.dark }}>복용 시 유의(DUR)</h2>
                </div>
                {drugInfo.dur_cautions.map((c, i) => (
                  <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>
                    <span className="font-bold">[{c.category}]</span> {c.detail}
                    {c.extra ? ` (${c.extra})` : ""}
                  </p>
                ))}
              </div>
            )}

            {!drugInfoLoading &&
              !hasPatientSummary &&
              !drugInfo?.precautions &&
              !drugInfo?.side_effects &&
              !drugInfo?.interactions &&
              !drugInfo?.storage &&
              !drugInfo?.dur_cautions?.length && (
                <div className="rounded-2xl p-5 mb-5" style={{ background: "#F5F2ED" }}>
                  <p className="text-[13px]" style={{ color: C.muted }}>
                    이 약의 주의사항·부작용·약물 상호작용·보관 방법에 대해 조회되는 내용이 없어요.
                  </p>
                </div>
              )}

            <div className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
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
                      <div>
                        <p className="text-[13px]" style={{ color: C.dark }}>
                          {new Date(log.checked_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </p>
                        <p className="text-[11px] mt-0.5" style={{ color: C.muted }}>확인자 · {log.confirmed_by_name}</p>
                      </div>
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
                onClick={() => navigate("/chat", { state: { drugName: schedule.drug_name } })}
                className="flex-1 py-4 rounded-full font-bold text-[15px] border-2 transition-all flex items-center justify-center gap-2"
                style={{ borderColor: C.terracotta, color: C.terracotta }}
              >
                <MessageCircle className="w-[18px] h-[18px]" strokeWidth={2.2} /> 챗봇에게 질문하기
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
