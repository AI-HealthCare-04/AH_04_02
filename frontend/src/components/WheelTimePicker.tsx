import { useEffect, useRef } from "react";
import { C } from "../theme";

// [2026-07-16] Schedule.tsx의 "복용 시간" 휠 피커를 그대로 뽑아냄 — MealTimeCheck.tsx도
// 동일한 시간 입력 UI가 필요해서 공용 컴포넌트로 분리 (기존 동작은 그대로 유지).
export const PERIODS = ["오전", "오후"];
export const HOURS_12 = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"));
export const MINUTES_5 = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, "0"));

export function formatTime12(time: string) {
  const [hStr, m] = time.split(":");
  const h = Number(hStr);
  if (Number.isNaN(h)) return time;
  const period = h < 12 ? "오전" : "오후";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${period} ${String(h12).padStart(2, "0")}:${m ?? "00"}`;
}

/** 24시간 "HH:MM" → 휠 피커용 {오전/오후, 01~12시, 5분단위} */
export function to12(time: string) {
  const [hStr, mStr] = time.split(":");
  const h = Number(hStr) || 0;
  const period = h < 12 ? "오전" : "오후";
  let h12 = h % 12;
  if (h12 === 0) h12 = 12;
  const m = Number(mStr) || 0;
  const roundedM = (Math.round(m / 5) * 5) % 60;
  return { period, hour: String(h12).padStart(2, "0"), minute: String(roundedM).padStart(2, "0") };
}

/** 휠 피커 선택값 → 24시간 "HH:MM" */
export function from12(period: string, hour: string, minute: string) {
  let h = Number(hour) % 12;
  if (period === "오후") h += 12;
  return `${String(h).padStart(2, "0")}:${minute}`;
}

/** 시간 휠(스크롤) 피커 한 칸 — 오전/오후, 시, 분 각각에 재사용 */
export function WheelColumn({
  options,
  value,
  onChange,
  width = 52,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  width?: number;
}) {
  const itemH = 34;
  const ref = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const idx = options.indexOf(value);
    if (ref.current && idx >= 0) {
      const target = idx * itemH;
      if (Math.abs(ref.current.scrollTop - target) > 2) ref.current.scrollTop = target;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const settle = (idx: number) => {
    ref.current?.scrollTo({ top: idx * itemH, behavior: "smooth" });
  };

  const handleScroll = () => {
    if (!ref.current) return;
    const idx = Math.round(ref.current.scrollTop / itemH);
    const clamped = Math.max(0, Math.min(options.length - 1, idx));
    if (options[clamped] !== value) onChange(options[clamped]);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => settle(clamped), 120);
  };

  return (
    <div className="relative" style={{ width, height: itemH * 3 }}>
      <div
        ref={ref}
        onScroll={handleScroll}
        className="wheel-scroll h-full overflow-y-scroll"
        style={{ scrollSnapType: "y mandatory" }}
      >
        <div style={{ height: itemH }} />
        {options.map((opt, i) => (
          <div
            key={opt}
            onClick={() => {
              onChange(opt);
              settle(i);
            }}
            className="flex items-center justify-center text-[15px] font-bold cursor-pointer select-none"
            style={{ height: itemH, scrollSnapAlign: "center", color: opt === value ? C.terracotta : C.muted }}
          >
            {opt}
          </div>
        ))}
        <div style={{ height: itemH }} />
      </div>
      <div
        className="absolute left-0 right-0 pointer-events-none border-t border-b"
        style={{ top: itemH, height: itemH, borderColor: `${C.terracotta}30` }}
      />
    </div>
  );
}
