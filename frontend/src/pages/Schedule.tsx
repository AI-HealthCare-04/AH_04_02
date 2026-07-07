import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import NavBar from "../components/NavBar";
import {
  createSchedule,
  deleteSchedule,
  getSchedules,
  updateSchedule,
  type Schedule,
} from "../api/monitoring";
import { getCurrentPatientId } from "../lib/session";

const TIME_SLOTS = ["아침", "점심", "저녁", "취침 전"];

export default function SchedulePage() {
  const patientId = getCurrentPatientId();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const [drugName, setDrugName] = useState("");
  const [timeSlot, setTimeSlot] = useState(TIME_SLOTS[0]);
  const [memo, setMemo] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const data = await getSchedules(patientId);
      setSchedules(data);
    } catch {
      setError("일정을 불러오지 못했어요.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleActive = async (s: Schedule) => {
    setSchedules((prev) => prev.map((x) => (x.id === s.id ? { ...x, active: !x.active } : x)));
    try {
      await updateSchedule(s.id, { active: !s.active });
    } catch {
      setSchedules((prev) => prev.map((x) => (x.id === s.id ? { ...x, active: s.active } : x)));
      setError("변경하지 못했어요.");
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("이 일정을 삭제할까요?")) return;
    try {
      await deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError("삭제하지 못했어요.");
    }
  };

  const save = async () => {
    if (!drugName.trim()) return;
    setSaving(true);
    try {
      await createSchedule({ patient_id: patientId, drug_name: drugName.trim(), time_slot: timeSlot, memo: memo.trim() || undefined });
      setModalOpen(false);
      setDrugName("");
      setMemo("");
      setTimeSlot(TIME_SLOTS[0]);
      await load();
    } catch {
      setError("저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF6F1]">
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-3xl mx-auto px-6 sm:px-8 py-10">
        <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
          <div>
            <h1 className="text-[26px] font-black text-[#2A2A2A]">복약 일정</h1>
            <p className="text-[14px] text-[#888888] mt-1">복용 시간대를 등록하고 관리하세요.</p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-2 px-5 py-3 rounded-full text-white font-bold text-[14px] bg-[#C1653D]"
          >
            <Plus className="w-4 h-4" /> 새 일정 추가
          </button>
        </div>

        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        <div className="bg-white border border-[#EEE6DC] rounded-2xl overflow-hidden">
          {loading ? (
            <p className="px-6 py-8 text-center text-[14px] text-[#888888]">불러오는 중이에요...</p>
          ) : schedules.length === 0 ? (
            <p className="px-6 py-10 text-center text-[14px] text-[#888888]">등록된 일정이 없어요.</p>
          ) : (
            schedules.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between gap-4 px-6 py-4 border-b border-[#F5F0EA] last:border-0"
                style={{ opacity: s.active ? 1 : 0.5 }}
              >
                <div>
                  <p className="text-[15px] font-bold text-[#2A2A2A]">{s.drug_name}</p>
                  <p className="text-[13px] text-[#888888]">
                    {s.time_slot}
                    {s.memo ? ` · ${s.memo}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => toggleActive(s)}
                    className="px-3 py-1.5 rounded-full text-[12px] font-bold border"
                    style={{
                      borderColor: s.active ? "#8FAE8B60" : "#88888840",
                      color: s.active ? "#4A7A47" : "#888888",
                      background: s.active ? "#8FAE8B15" : "transparent",
                    }}
                  >
                    {s.active ? "사용 중" : "중지됨"}
                  </button>
                  <button onClick={() => remove(s.id)} className="w-8 h-8 rounded-full flex items-center justify-center text-[#888888] hover:bg-black/5">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: "rgba(30,26,23,0.5)" }}
          onClick={() => setModalOpen(false)}
        >
          <div className="bg-white rounded-2xl p-7 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-[19px] font-black text-[#2A2A2A] mb-5">새 일정 추가</h3>

            <label className="block text-[12px] font-bold text-[#888888] uppercase tracking-wide mb-2">약 이름</label>
            <input
              value={drugName}
              onChange={(e) => setDrugName(e.target.value)}
              placeholder="예: 암로디핀 5mg"
              className="w-full px-4 py-3 rounded-xl border border-black/12 text-[14px] outline-none mb-4"
            />

            <label className="block text-[12px] font-bold text-[#888888] uppercase tracking-wide mb-2">복용 시간대</label>
            <div className="grid grid-cols-4 gap-2 mb-4">
              {TIME_SLOTS.map((slot) => (
                <button
                  key={slot}
                  onClick={() => setTimeSlot(slot)}
                  className="py-2.5 rounded-xl text-[13px] font-bold transition-all"
                  style={{
                    background: timeSlot === slot ? "#C1653D" : "#F0EDE8",
                    color: timeSlot === slot ? "#FFFFFF" : "#888888",
                  }}
                >
                  {slot}
                </button>
              ))}
            </div>

            <label className="block text-[12px] font-bold text-[#888888] uppercase tracking-wide mb-2">메모 (선택)</label>
            <input
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder="예: 식후 30분"
              className="w-full px-4 py-3 rounded-xl border border-black/12 text-[14px] outline-none mb-6"
            />

            <div className="flex gap-3">
              <button
                onClick={() => setModalOpen(false)}
                className="flex-1 py-3 rounded-full font-bold text-[14px] border-2 border-black/12 text-[#2A2A2A]"
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
