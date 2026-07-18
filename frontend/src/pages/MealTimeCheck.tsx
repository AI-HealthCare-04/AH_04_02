import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { updateMealTimes } from "../api/monitoring";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { from12, HOURS_12, MINUTES_5, PERIODS, to12, WheelColumn } from "../components/WheelTimePicker";

type MealKey = "breakfast" | "lunch" | "dinner";

const MEALS: { key: MealKey; label: string }[] = [
  { key: "breakfast", label: "아침 식사" },
  { key: "lunch", label: "점심 식사" },
  { key: "dinner", label: "저녁 식사" },
];

function pillClass(active: boolean) {
  return `px-4 py-1.5 rounded-full text-[13px] font-bold border-2 transition-all ${
    active ? "bg-[#C1653D] border-[#C1653D] text-white" : "bg-[#F4F0EA] border-[rgba(30,26,23,0.12)] text-[#8A7E75]"
  }`;
}

export default function MealTimeCheck() {
  const navigate = useNavigate();
  const patientId = useGuardedPatientId();
  const [time, setTime] = useState<Record<MealKey, string>>({
    breakfast: "08:00",
    lunch: "12:30",
    dinner: "19:00",
  });
  const [regular, setRegular] = useState<Record<MealKey, boolean>>({
    breakfast: true,
    lunch: true,
    dinner: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (patientId == null) return;
    setSubmitting(true);
    setError("");
    try {
      await updateMealTimes(patientId, {
        breakfast_time: time.breakfast,
        breakfast_regular: regular.breakfast,
        lunch_time: time.lunch,
        lunch_regular: regular.lunch,
        dinner_time: time.dinner,
        dinner_regular: regular.dinner,
      });
      navigate("/dashboard");
    } catch {
      setError("저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF6F1]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-2">식사 시간 체크리스트</h1>
        <p className="text-[14px] text-[#8A7E75] mb-7">
          평소 식사 시간을 입력하면 복약 알림 시각(식전·식후)을 맞추는 데 사용해요.
        </p>

        <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-7">
          <p className="text-[13px] font-bold text-[#8A7E75] mb-4">식사 시간</p>

          {MEALS.map(({ key, label }, i) => {
            const t12 = to12(time[key]);
            return (
              <div
                key={key}
                className={`py-4 ${i < MEALS.length - 1 ? "border-b border-[#F4F0EA]" : ""}`}
              >
                <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                  <span className="text-[15px] font-medium text-[#1E1A17]">{label}</span>
                  <div className="flex gap-2">
                    <button onClick={() => setRegular((prev) => ({ ...prev, [key]: true }))} className={pillClass(regular[key])}>
                      규칙적
                    </button>
                    <button onClick={() => setRegular((prev) => ({ ...prev, [key]: false }))} className={pillClass(!regular[key])}>
                      불규칙적
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-0.5 justify-center rounded-xl bg-[#FAF6F1] py-1">
                  <WheelColumn
                    options={PERIODS}
                    value={t12.period}
                    onChange={(v) => setTime((prev) => ({ ...prev, [key]: from12(v, t12.hour, t12.minute) }))}
                    width={44}
                  />
                  <WheelColumn
                    options={HOURS_12}
                    value={t12.hour}
                    onChange={(v) => setTime((prev) => ({ ...prev, [key]: from12(t12.period, v, t12.minute) }))}
                  />
                  <span className="text-[15px] font-bold text-[#8A7E75] px-0.5">:</span>
                  <WheelColumn
                    options={MINUTES_5}
                    value={t12.minute}
                    onChange={(v) => setTime((prev) => ({ ...prev, [key]: from12(t12.period, t12.hour, v) }))}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={submitting || patientId == null}
          className="w-full py-4 rounded-xl bg-[#C1653D] text-white font-bold text-[16px] disabled:opacity-60"
        >
          {submitting ? "저장 중..." : "저장하고 시작하기"}
        </button>
      </main>
    </div>
  );
}
