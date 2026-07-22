import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckSquare, Plus, Square, X } from "lucide-react";
import NavBar from "../components/NavBar";
import {
  createSchedule,
  deleteSchedule,
  getKnownDrugs,
  getPatients,
  getSchedules,
  updateSchedule,
  type Schedule,
} from "../api/monitoring";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";
import { formatTime12, from12, HOURS_12, MINUTES_5, PERIODS, to12, WheelColumn } from "../components/WheelTimePicker";

// [7/8 변경] 피그마 디자인 반영 — 시간대(아침/점심/저녁) 대신 "복용 상태" 6종 + 실제 시각 입력
// [2026-07-21] PrescriptionReview.tsx(처방확인 화면)에서도 그대로 재사용하려고 export.
export const DOSE_TIMINGS = ["공복", "아침 식후", "점심 식전", "점심 식후", "저녁 식전", "저녁 식후"];

interface TimeEntry {
  key: number;
  time: string; // "HH:MM" (24시간)
  doseTiming: string;
}

interface DrugGroup {
  drugName: string;
  ids: number[];
  entries: { id: number; time: string; doseTiming: string | null }[];
  active: boolean;
  caregiverAlert: boolean;
}

/** axios 에러에서 백엔드가 내려준 실제 사유(detail)를 뽑아 표시 — "저장이 안 돼요"로만 뭉개지 않기 위함 */
function describeError(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? `${fallback} (${detail})` : fallback;
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative w-11 h-6 rounded-full transition-colors shrink-0"
      style={{ background: on ? C.terracotta : "rgba(30,26,23,0.15)" }}
    >
      <span
        className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform"
        style={{ transform: on ? "translateX(20px)" : "translateX(0)" }}
      />
    </button>
  );
}

let keySeed = 0;
const nextKey = () => ++keySeed;

export default function SchedulePage() {
  const patientId = useGuardedPatientId();
  const navigate = useNavigate();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [knownDrugs, setKnownDrugs] = useState<string[]>([]);
  const [patientValid, setPatientValid] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingDrug, setEditingDrug] = useState<string | null>(null);

  const [drugMode, setDrugMode] = useState<"select" | "custom">("select");
  const [drugName, setDrugName] = useState("");
  const [entries, setEntries] = useState<TimeEntry[]>([
    { key: nextKey(), time: "08:00", doseTiming: DOSE_TIMINGS[1] },
  ]);
  const [caregiverAlert, setCaregiverAlert] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState("");

  // [2026-07-22 추가] 약물별로 여러 개 선택해서 한 번에 삭제 — Records.tsx의 선택 삭제와
  // 동일한 패턴(drugName으로 그룹이 묶이므로 id 대신 drugName을 키로 씀).
  const [selectMode, setSelectMode] = useState(false);
  const [selectedDrugs, setSelectedDrugs] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const load = async (pid: number) => {
    try {
      const [scheduleData, drugData, patients] = await Promise.all([
        getSchedules(pid),
        getKnownDrugs(pid),
        getPatients(),
      ]);
      setSchedules(scheduleData);
      setKnownDrugs(drugData);
      // [7/8 추가] 저장이 조용히 404로 실패하는 원인 방지 — patient_id가 이제 존재하지 않는
      // (예: app.db를 지운 뒤 옛 로그인 정보가 남아있는) 경우를 목록 조회 시점에 미리 알려줌
      setPatientValid(patients.some((p) => p.id === pid));
      setError("");
    } catch (e) {
      setError(describeError(e, "일정을 불러오지 못했어요."));
    } finally {
      setLoading(false);
    }
  };

  const relogin = () => {
    localStorage.removeItem("patient_id");
    localStorage.removeItem("caregiver_id");
    navigate("/login");
  };

  useEffect(() => {
    if (patientId == null) return;
    load(patientId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  const groups = useMemo<DrugGroup[]>(() => {
    const map = new Map<string, DrugGroup>();
    for (const s of schedules) {
      const g =
        map.get(s.drug_name) ??
        ({ drugName: s.drug_name, ids: [], entries: [], active: false, caregiverAlert: false } as DrugGroup);
      g.ids.push(s.id);
      g.entries.push({ id: s.id, time: s.time_slot, doseTiming: s.dose_timing });
      if (s.active) g.active = true;
      if (s.caregiver_alert) g.caregiverAlert = true;
      map.set(s.drug_name, g);
    }
    for (const g of map.values()) g.entries.sort((a, b) => a.time.localeCompare(b.time));
    return Array.from(map.values());
  }, [schedules]);

  const openAddModal = () => {
    setEditingDrug(null);
    setDrugMode(knownDrugs.length > 0 ? "select" : "custom");
    setDrugName(knownDrugs[0] ?? "");
    setEntries([{ key: nextKey(), time: "08:00", doseTiming: DOSE_TIMINGS[1] }]);
    setCaregiverAlert(true);
    setModalError("");
    setModalOpen(true);
  };

  const openEditModal = (group: DrugGroup) => {
    setEditingDrug(group.drugName);
    setDrugMode(knownDrugs.includes(group.drugName) ? "select" : "custom");
    setDrugName(group.drugName);
    setEntries(group.entries.map((e) => ({ key: nextKey(), time: e.time, doseTiming: e.doseTiming ?? DOSE_TIMINGS[1] })));
    setCaregiverAlert(group.caregiverAlert);
    setModalError("");
    setModalOpen(true);
  };

  const addTimeEntry = () => {
    setEntries((prev) => [...prev, { key: nextKey(), time: "08:00", doseTiming: DOSE_TIMINGS[1] }]);
  };

  const removeTimeEntry = (key: number) => {
    setEntries((prev) => (prev.length > 1 ? prev.filter((e) => e.key !== key) : prev));
  };

  const updateEntry = (key: number, patch: Partial<TimeEntry>) => {
    setEntries((prev) => prev.map((e) => (e.key === key ? { ...e, ...patch } : e)));
  };

  const toggleGroupActive = async (group: DrugGroup) => {
    const next = !group.active;
    setSchedules((prev) => prev.map((s) => (group.ids.includes(s.id) ? { ...s, active: next } : s)));
    try {
      await Promise.all(group.ids.map((id) => updateSchedule(id, { active: next })));
    } catch (e) {
      setError(describeError(e, "변경하지 못했어요."));
      if (patientId != null) await load(patientId);
    }
  };

  const toggleGroupAlert = async (group: DrugGroup) => {
    const next = !group.caregiverAlert;
    setSchedules((prev) =>
      prev.map((s) => (group.ids.includes(s.id) ? { ...s, caregiver_alert: next } : s))
    );
    try {
      await Promise.all(group.ids.map((id) => updateSchedule(id, { caregiver_alert: next })));
    } catch (e) {
      setError(describeError(e, "변경하지 못했어요."));
      if (patientId != null) await load(patientId);
    }
  };

  const removeGroup = async (group: DrugGroup) => {
    if (!window.confirm(`'${group.drugName}' 일정을 모두 삭제할까요?`)) return;
    try {
      await Promise.all(group.ids.map((id) => deleteSchedule(id)));
      setSchedules((prev) => prev.filter((s) => !group.ids.includes(s.id)));
    } catch (e) {
      setError(describeError(e, "삭제하지 못했어요."));
    }
  };

  const toggleSelectMode = () => {
    setSelectMode((v) => !v);
    setSelectedDrugs(new Set());
  };

  const toggleSelectedDrug = (drugName: string) => {
    setSelectedDrugs((prev) => {
      const next = new Set(prev);
      if (next.has(drugName)) next.delete(drugName);
      else next.add(drugName);
      return next;
    });
  };

  const handleBulkDelete = async () => {
    if (bulkDeleting || selectedDrugs.size === 0) return;
    if (!window.confirm(`선택한 ${selectedDrugs.size}개 약물 일정을 모두 삭제할까요?`)) return;
    setBulkDeleting(true);
    try {
      const targetIds = groups.filter((g) => selectedDrugs.has(g.drugName)).flatMap((g) => g.ids);
      await Promise.all(targetIds.map((id) => deleteSchedule(id)));
      setSchedules((prev) => prev.filter((s) => !targetIds.includes(s.id)));
      setSelectedDrugs(new Set());
      setSelectMode(false);
    } catch (e) {
      setError(describeError(e, "일부 항목을 삭제하지 못했어요."));
    } finally {
      setBulkDeleting(false);
    }
  };

  const save = async () => {
    if (patientId == null) return;
    const name = drugName.trim();
    if (!name) {
      setModalError("약물을 선택하거나 입력해주세요.");
      return;
    }
    if (entries.some((e) => !e.time)) {
      setModalError("복용 시간을 입력해주세요.");
      return;
    }
    setSaving(true);
    setModalError("");
    try {
      if (editingDrug) {
        const group = groups.find((g) => g.drugName === editingDrug);
        if (group) await Promise.all(group.ids.map((id) => deleteSchedule(id)));
      }
      await Promise.all(
        entries.map((e) =>
          createSchedule({
            patient_id: patientId,
            drug_name: name,
            time_slot: e.time,
            dose_timing: e.doseTiming,
            caregiver_alert: caregiverAlert,
          })
        )
      );
      setModalOpen(false);
      await load(patientId);
    } catch (e) {
      console.error("[Schedule] 저장 실패", e);
      setModalError(describeError(e, "저장하지 못했어요."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F2E8D8]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-3xl mx-auto px-6 sm:px-8 py-10">
        <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
          <div>
            <h1 className="text-[26px] font-black text-[#1E1A17]">복약 일정</h1>
            <p className="text-[14px] text-[#8A7E75] mt-1">복용 시간대를 등록하고 관리하세요.</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {groups.length > 0 && (
              <button
                onClick={toggleSelectMode}
                className="text-[13px] font-bold px-3 py-1.5 rounded-full transition-opacity hover:opacity-70"
                style={{ background: selectMode ? C.terracotta : `${C.terracotta}12`, color: selectMode ? C.white : C.terracotta }}
              >
                {selectMode ? "선택 취소" : "선택하기"}
              </button>
            )}
            <button
              onClick={openAddModal}
              className="flex items-center gap-2 px-5 py-3 rounded-full text-white font-bold text-[14px] bg-[#C1653D]"
            >
              <Plus className="w-4 h-4" /> 새 일정 추가
            </button>
          </div>
        </div>

        {selectMode && (
          <div className="rounded-xl px-5 py-3 mb-5 flex items-center justify-between" style={{ background: `${C.terracotta}12` }}>
            <span className="text-[13px] font-bold" style={{ color: C.terracotta }}>{selectedDrugs.size}개 선택됨</span>
            <button
              onClick={handleBulkDelete}
              disabled={selectedDrugs.size === 0 || bulkDeleting}
              className="px-4 py-2 rounded-full text-[13px] font-bold text-white disabled:opacity-50"
              style={{ background: "#D94F4F" }}
            >
              {bulkDeleting ? "삭제하는 중..." : "선택 삭제"}
            </button>
          </div>
        )}

        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        {!loading && !patientValid && (
          <div className="mb-5 p-4 rounded-xl" style={{ background: `${C.danger}12`, border: `1px solid ${C.danger}35` }}>
            <p className="text-[14px] font-bold text-[#D94F4F] mb-1">환자 정보를 찾을 수 없어요</p>
            <p className="text-[13px] text-[#8A7E75] mb-3">
              기존 로그인 정보가 만료되었을 수 있어요 (예: 서버 데이터가 초기화됨). 다시 로그인하면 해결돼요.
            </p>
            <button
              onClick={relogin}
              className="px-4 py-2 rounded-full bg-[#C1653D] text-white text-[13px] font-bold"
            >
              다시 로그인하기
            </button>
          </div>
        )}

        <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden">
          {loading ? (
            <p className="px-6 py-8 text-center text-[14px] text-[#8A7E75]">불러오는 중이에요...</p>
          ) : groups.length === 0 ? (
            <p className="px-6 py-10 text-center text-[14px] text-[#8A7E75]">등록된 일정이 없어요.</p>
          ) : (
            groups.map((g) => {
              const selected = selectedDrugs.has(g.drugName);
              return (
              <div
                key={g.drugName}
                role={selectMode ? "button" : undefined}
                tabIndex={selectMode ? 0 : undefined}
                onClick={() => selectMode && toggleSelectedDrug(g.drugName)}
                className="flex items-center justify-between gap-4 px-6 py-4 border-b border-[#F4F0EA] last:border-0 flex-wrap"
                style={{ opacity: g.active ? 1 : 0.5, cursor: selectMode ? "pointer" : "default" }}
              >
                <div className="flex items-start gap-3 min-w-[160px]">
                  {selectMode && (
                    <span className="mt-0.5 shrink-0">
                      {selected ? (
                        <CheckSquare className="w-5 h-5" style={{ color: C.terracotta }} />
                      ) : (
                        <Square className="w-5 h-5" style={{ color: "rgba(30,26,23,0.25)" }} />
                      )}
                    </span>
                  )}
                  <div>
                    <p className="text-[15px] font-bold text-[#1E1A17]">{g.drugName}</p>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      {g.entries.map((e) => (
                        <span
                          key={e.id}
                          className="px-2 py-0.5 rounded-md text-[11px] font-bold"
                          style={{ background: C.bubbleBg, color: C.muted }}
                        >
                          {formatTime12(e.time)}
                        </span>
                      ))}
                    </div>
                    <p className="text-[13px] text-[#8A7E75] mt-1">
                      {Array.from(new Set(g.entries.map((e) => e.doseTiming).filter(Boolean))).join(" · ") || "-"}
                    </p>
                  </div>
                </div>
                {!selectMode && (
                  <div className="flex items-center gap-5 shrink-0">
                    <div className="text-center">
                      <p className="text-[11px] text-[#8A7E75] mb-1">보호자 알림</p>
                      <Toggle on={g.caregiverAlert} onClick={() => toggleGroupAlert(g)} />
                    </div>
                    <div className="text-center">
                      <p className="text-[11px] text-[#8A7E75] mb-1">사용 여부</p>
                      <Toggle on={g.active} onClick={() => toggleGroupActive(g)} />
                    </div>
                    <button
                      onClick={() => openEditModal(g)}
                      className="px-3 py-1.5 rounded-full text-[12px] font-bold border border-[rgba(30,26,23,0.12)] text-[#1E1A17]"
                    >
                      수정
                    </button>
                    <button
                      onClick={() => removeGroup(g)}
                      className="w-8 h-8 rounded-full flex items-center justify-center text-[#8A7E75] hover:bg-[rgba(30,26,23,0.05)]"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
              );
            })
          )}
        </div>
      </main>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4 overflow-y-auto py-8"
          style={{ background: "rgba(30,26,23,0.5)" }}
          onClick={() => setModalOpen(false)}
        >
          <div
            className="bg-[#F9F4EB] rounded-2xl p-7 w-full max-w-sm my-auto max-h-[calc(100vh-4rem)] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-[19px] font-black text-[#1E1A17] mb-5">
              {editingDrug ? "일정 수정" : "새 일정 추가"}
            </h3>

            <label className="block text-[12px] font-bold text-[#8A7E75] uppercase tracking-wide mb-2">
              약물 선택
            </label>
            {drugMode === "select" ? (
              <>
                <select
                  value={drugName}
                  onChange={(e) => setDrugName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-[rgba(30,26,23,0.12)] text-[14px] outline-none mb-2 bg-white"
                >
                  {knownDrugs.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    setDrugMode("custom");
                    setDrugName("");
                  }}
                  className="text-[12px] font-bold text-[#C1653D] mb-4"
                >
                  + 목록에 없는 약물 직접 입력
                </button>
              </>
            ) : (
              <>
                <input
                  value={drugName}
                  onChange={(e) => setDrugName(e.target.value)}
                  placeholder="예: 암로디핀 5mg"
                  className="w-full px-4 py-3 rounded-xl border border-[rgba(30,26,23,0.12)] text-[14px] outline-none mb-2"
                />
                {knownDrugs.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => setDrugMode("select")}
                    className="text-[12px] font-bold text-[#C1653D] mb-4"
                  >
                    목록에서 선택하기
                  </button>
                ) : (
                  <div className="mb-4" />
                )}
              </>
            )}

            <label className="block text-[12px] font-bold text-[#8A7E75] uppercase tracking-wide mb-2">
              복용 시간
            </label>
            <div className="space-y-3 mb-2">
              {entries.map((entry) => {
                const t12 = to12(entry.time);
                return (
                  <div key={entry.key} className="rounded-xl border border-[rgba(30,26,23,0.10)] p-3">
                    <div className="flex items-center gap-2 mb-2.5">
                      <div className="flex items-center gap-0.5 flex-1 justify-center">
                        <WheelColumn
                          options={PERIODS}
                          value={t12.period}
                          onChange={(v) => updateEntry(entry.key, { time: from12(v, t12.hour, t12.minute) })}
                          width={44}
                        />
                        <WheelColumn
                          options={HOURS_12}
                          value={t12.hour}
                          onChange={(v) => updateEntry(entry.key, { time: from12(t12.period, v, t12.minute) })}
                        />
                        <span className="text-[15px] font-bold text-[#8A7E75] px-0.5">:</span>
                        <WheelColumn
                          options={MINUTES_5}
                          value={t12.minute}
                          onChange={(v) => updateEntry(entry.key, { time: from12(t12.period, t12.hour, v) })}
                        />
                      </div>
                      {entries.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeTimeEntry(entry.key)}
                          className="w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-[#8A7E75] hover:bg-[rgba(30,26,23,0.05)]"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {DOSE_TIMINGS.map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => updateEntry(entry.key, { doseTiming: d })}
                          className="py-2 rounded-lg text-[12px] font-bold transition-all"
                          style={{
                            background: entry.doseTiming === d ? C.terracotta : C.bubbleBg,
                            color: entry.doseTiming === d ? C.white : C.muted,
                          }}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <button type="button" onClick={addTimeEntry} className="text-[12px] font-bold text-[#C1653D] mb-5">
              + 시간 추가
            </button>

            <div className="flex items-start justify-between gap-3 mb-6 p-4 rounded-xl bg-[#F2E8D8]">
              <div>
                <p className="text-[14px] font-bold text-[#1E1A17]">보호자에게도 알림</p>
                <p className="text-[12px] text-[#8A7E75] mt-0.5">복약 시간에 보호자에게도 알림을 전송합니다</p>
              </div>
              <Toggle on={caregiverAlert} onClick={() => setCaregiverAlert((v) => !v)} />
            </div>

            {modalError && <p className="text-[13px] text-[#D94F4F] mb-4">{modalError}</p>}

            <div className="flex gap-3">
              <button
                onClick={() => setModalOpen(false)}
                className="flex-1 py-3 rounded-full font-bold text-[14px] border-2 border-[rgba(30,26,23,0.12)] text-[#1E1A17]"
              >
                취소
              </button>
              <button
                onClick={save}
                disabled={saving || !drugName.trim()}
                className="flex-1 py-3 rounded-full font-bold text-[14px] text-white bg-[#C1653D] disabled:opacity-50"
              >
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
