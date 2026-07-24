import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import PatientContextBanner from "../components/PatientContextBanner";
import {
  getPatientCaregivers,
  getTodayMedications,
  checkIntake,
  clearIntake,
  type Medication,
  type IntakeStatus,
} from "../api/monitoring";
import { listRecords, type RecordSummary } from "../api/records";
import { getCurrentCaregiverId, getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

export default function Dashboard() {
  const navigate = useNavigate();
  const patientId = useGuardedPatientId();
  const [meds, setMeds] = useState<Medication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // [수정] "보호자를 연결해보세요" 배너는 환자 본인이 아직 아무 보호자와도 연결 안 됐을 때
  // 초대를 유도하려는 것 — 이미 보호자로 로그인해서 이 환자를 보고 있는 사람에게는
  // (본인이 이미 연결된 보호자이므로) 의미가 없고, 눌러도 환자용 초대 화면(Connect.tsx)이
  // 떠서 혼란만 준다. 환자 본인 로그인(caregiver_id 없음)일 때만 보여준다.
  const [showBanner, setShowBanner] = useState(!getCurrentCaregiverId());
  const [recentRecords, setRecentRecords] = useState<RecordSummary[]>([]);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    if (patientId == null) return;
    getTodayMedications(patientId)
      .then(setMeds)
      .catch(() => setError("복약 목록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
    listRecords(patientId)
      .then((list) => setRecentRecords(list.filter((r) => r.status === "completed").slice(0, 2)))
      .catch(() => {});
  }, [patientId]);

  // [2026-07-22 추가] 이미 연결된 보호자가 있으면 "보호자를 연결해보세요" 배너 자체가
  // 더 이상 의미 없다 — X로 닫는 것과 별개로, 연결 여부를 실제로 확인해서 있으면 숨긴다.
  useEffect(() => {
    if (patientId == null || getCurrentCaregiverId()) return;
    getPatientCaregivers(patientId)
      .then((list) => {
        if (list.length > 0) setShowBanner(false);
      })
      .catch(() => {});
  }, [patientId]);

  // [2026-07-20] "missed"는 스케줄러가 자동으로 판정하는 상태라 사용자가 직접 누를 수 있는
  // 버튼이 없다(아래 버튼 3개는 taken/pending/skipped뿐) — 그래도 이 함수의 status 매개변수
  // 타입은 Medication.status와 맞춰 IntakeStatus 전체를 받으므로, "missed"가 들어오면
  // checkIntake(taken/skipped만 허용)로 보내지 않도록 방어적으로 막아둔다.
  const updateStatus = async (id: string, status: IntakeStatus) => {
    if (status === "missed") return;

    // 먼저 화면부터 낙관적으로 바꾸고, 실패하면 되돌림 (버튼 반응성 위해)
    const prev = meds;
    setMeds((cur) => cur.map((m) => (m.id === id ? { ...m, status } : m)));
    setSavingId(id);

    try {
      if (status === "pending") {
        await clearIntake(id);
      } else {
        await checkIntake(id, status);
      }
    } catch {
      setMeds(prev); // 실패 시 원래 상태로 롤백
    } finally {
      setSavingId(null);
    }
  };

  const today = new Date();
  const dateLabel = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일 (${"일월화수목금토"[today.getDay()]})`;

  // [2026-07-21 추가] 시간대별로 묶어서 보여줌 — "이 시간에 뭘 먹어야 하는지" 한눈에 보이게.
  // 백엔드(/monitoring/today)가 이미 time_slot 순으로 정렬해서 내려주므로 그 순서 그대로 묶기만 함.
  const medGroups: [string, Medication[]][] = [];
  meds.forEach((med) => {
    const group = medGroups.find(([time]) => time === med.time);
    if (group) group[1].push(med);
    else medGroups.push([med.time, [med]]);
  });

  return (
    <div className="min-h-screen" style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-[700px] mx-auto px-4 sm:px-5 pt-6 sm:pt-8 pb-12 sm:pb-[60px]">
        <PatientContextBanner />
        <div className="flex justify-between items-start mb-5">
          <div>
            <p className="text-[13px] mb-1" style={{ color: C.muted }}>오늘</p>
            <h1 className="text-2xl sm:text-[28px] font-extrabold" style={{ color: C.dark }}>{dateLabel}</h1>
          </div>
        </div>

        {showBanner && (
          <div className="rounded-2xl px-5 sm:px-6 py-5 flex justify-between items-center mb-6 sm:mb-8 flex-wrap gap-3" style={{ background: `${C.terracotta}18` }}>
            <div>
              <p className="text-[15px] font-bold mb-1" style={{ color: C.dark }}>보호자를 연결해보세요</p>
              <p className="text-[13px]" style={{ color: C.muted }}>복약 관리를 도울 분을 연결하면 더 안전해요</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                className="px-5 py-2.5 rounded-3xl font-bold text-[13px] cursor-pointer outline-none border-none"
                style={{ background: C.terracotta, color: C.white }}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => navigate("/connect")}
              >
                연결하러 가기
              </button>
              <button
                className="w-8 h-8 rounded-full border-none cursor-pointer text-base outline-none"
                style={{ background: `${C.terracotta}30`, color: C.muted }}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setShowBanner(false)}
              >
                ×
              </button>
            </div>
          </div>
        )}

        <h2 className="text-lg font-extrabold mb-4" style={{ color: C.dark }}>오늘의 복약</h2>

        {loading && <p className="text-sm mb-4" style={{ color: C.muted }}>불러오는 중이에요...</p>}
        {!loading && error && <p className="text-sm mb-4" style={{ color: C.danger }}>{error}</p>}
        {!loading && !error && meds.length === 0 && (
          <p className="text-sm mb-4" style={{ color: C.muted }}>등록된 복약 일정이 없어요.</p>
        )}

        <div className="flex flex-col gap-6 mb-8">
          {medGroups.map(([time, group]) => (
            <div key={time}>
              <p className="text-[13px] font-bold mb-2.5" style={{ color: C.terracotta }}>{time}</p>
              <div className="flex flex-col gap-4">
                {group.map((med) => (
            <div key={med.id} className="rounded-2xl px-5 sm:px-6 py-5 border" style={{ background: C.surface, borderColor: "rgba(30,26,23,0.12)" }}>
              <div className="flex justify-between mb-4">
                <div>
                  <p className="text-[17px] font-bold mb-1" style={{ color: C.dark }}>{med.name}</p>
                  <p className="text-[13px]" style={{ color: C.muted }}>{med.time}{med.note ? ` · ${med.note}` : ""}</p>
                </div>
                <span
                  className="text-xs font-bold rounded-xl px-2.5 py-1 h-fit whitespace-nowrap"
                  style={
                    med.status === "taken" ? { background: `${C.success}30`, color: C.successText } :
                    med.status === "skipped" ? { background: C.bubbleBg, color: C.muted } :
                    med.status === "missed" ? { background: `${C.danger}20`, color: C.danger } :
                    { background: C.bubbleBg, color: C.terracotta }
                  }
                >
                  {med.status === "taken" ? "복용완료" : med.status === "skipped" ? "건너뜀" :
                   med.status === "missed" ? "놓침" : "미복용"}
                </span>
              </div>
              <div className="flex gap-2">
                {/* [2026-07-20] "missed"는 스케줄러가 자동 판정하는 상태라 사용자가 직접 누르는
                    버튼이 아니다 — 이 배열을 IntakeStatus[]로 캐스팅하면 s가 "missed"까지
                    포함하게 되어 다음 줄 checkIntake(taken/skipped만 허용)·labels 룩업이 깨진다.
                    `as const`로 정확히 이 3개 리터럴로만 좁혀둔다. */}
                {(["taken", "pending", "skipped"] as const).map((s) => {
                  const isActive = med.status === s;
                  const labels = { taken: "복용했어요", pending: "아직이요", skipped: "건너뛸게요" };
                  return (
                    <button
                      key={s}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => updateStatus(med.id, s)}
                      disabled={savingId === med.id}
                      className="flex-1 py-3 rounded-3xl border-[1.5px] border-solid font-semibold text-sm outline-none shadow-none"
                      style={{
                        borderColor: isActive ? C.terracotta : "rgba(30,26,23,0.12)",
                        background: isActive && s === "pending" ? C.terracotta : isActive ? C.bubbleBg : C.white,
                        color: isActive && s === "pending" ? C.white : isActive ? C.terracotta : C.muted,
                        cursor: savingId === med.id ? "default" : "pointer",
                        opacity: savingId === med.id ? 0.6 : 1,
                        fontFamily: "inherit",
                      }}
                    >
                      {labels[s]}
                    </button>
                  );
                })}
              </div>
            </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl px-5 sm:px-6 py-5 flex items-center gap-4 cursor-pointer mb-8" style={{ background: C.dark }} onClick={() => navigate("/upload")}>
          <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl shrink-0" style={{ background: "rgba(255,255,255,0.12)", color: C.white }}>+</span>
          <div>
            <p className="font-bold text-[15px] mb-1" style={{ color: C.white }}>처방전으로 새 가이드 만들기</p>
            <p className="text-[13px]" style={{ color: "rgba(255,255,255,0.65)" }}>처방전 사진을 찍거나 파일을 올려주세요</p>
          </div>
          <span className="ml-auto text-xl" style={{ color: "rgba(255,255,255,0.65)" }}>›</span>
        </div>

        <h2 className="text-lg font-extrabold mb-4" style={{ color: C.dark }}>최근 받은 가이드</h2>
        {recentRecords.length === 0 ? (
          <p className="text-sm mb-8" style={{ color: C.muted }}>아직 받은 복약 가이드가 없어요.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
            {recentRecords.map((r) => (
              <div key={r.record_id} className="rounded-2xl p-5 border" style={{ background: C.surface, borderColor: "rgba(30,26,23,0.12)" }}>
                <div className="text-xl mb-3">📄</div>
                <p className="text-sm font-bold mb-5 min-h-10" style={{ color: C.dark }}>{r.diagnosis || "복약 가이드"}</p>
                <div className="flex justify-between items-center">
                  <span className="text-xs" style={{ color: C.muted }}>생성일 {new Date(r.created_at).toLocaleDateString("ko-KR")}</span>
                  <button
                    className="text-xs font-bold rounded-[14px] px-3 py-1.5 border-none cursor-pointer outline-none whitespace-nowrap"
                    style={{ color: C.terracotta, background: C.bubbleBg }}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => navigate(`/records/${r.record_id}`)}
                  >
                    자세히 보기 ›
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="text-center text-xs" style={{ color: C.muted }}>본 정보는 의료진의 진단·처방을 대체하지 않습니다</p>
      </main>
    </div>
  );
}
