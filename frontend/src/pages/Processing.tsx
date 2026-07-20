import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { createRecord } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName } from "../lib/session";

const steps = [
  { id: 1, label: "OCR 인식 중", desc: "처방전에서 약품 정보를 읽고 있어요" },
  { id: 2, label: "상태 예측 중", desc: "진단명과 약물을 바탕으로 환자 상태를 분석해요" },
  { id: 3, label: "맞춤 가이드 생성 중", desc: "복약 안내와 생활습관 가이드를 만들고 있어요" },
];

export default function Processing() {
  const navigate = useNavigate();
  const location = useLocation();
  const { file, patientId, caregiverId } =
    (location.state as { file?: File; patientId?: number; caregiverId?: number }) ?? {};

  const [current, setCurrent] = useState(0);
  const visualRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const runUpload = async () => {
    if (!file || !patientId) {
      navigate("/upload");
      return;
    }

    setCurrent(0);

    // 실제 단계와 무관한 시각 효과 — 응답 올 때까지 기대감만 주는 용도
    visualRef.current = setInterval(() => {
      setCurrent((prev) => (prev < steps.length - 1 ? prev + 1 : prev));
    }, 1200);

    try {
      const result = await createRecord(patientId, file, caregiverId);
      if (visualRef.current) clearInterval(visualRef.current);
      setCurrent(steps.length - 1);
      // [7/9 변경] OCR 신뢰도와 무관하게 항상 확인 화면을 거치므로 /result 인터스티셜 없이 바로 이동
      setTimeout(() => navigate(`/records/${result.record_id}/review`), 400);
    } catch (err: unknown) {
      if (visualRef.current) clearInterval(visualRef.current);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      navigate("/ocr-error", { state: { reason: detail } });
    }
  };

  useEffect(() => {
    runUpload();
    return () => {
      if (visualRef.current) clearInterval(visualRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen" style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-[600px] mx-auto flex flex-col items-center px-5 py-14 sm:px-6 sm:py-20">
        <div
          className="w-full border rounded-[20px] p-7 sm:px-10 sm:py-12 text-center"
          style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)" }}
        >
          <div className="text-4xl sm:text-5xl mb-4 sm:mb-5">⏳</div>
          <h1 className="text-[22px] sm:text-[26px] font-bold mb-2 sm:mb-2.5" style={{ color: C.dark }}>분석을 시작할게요</h1>
          <p className="text-[14px] sm:text-[15px] mb-8 sm:mb-10" style={{ color: C.muted }}>잠시만 기다려 주세요. 보통 10초 이내에 완료돼요.</p>

          <div className="flex flex-col gap-3 sm:gap-4 text-left mb-8 sm:mb-9">
            {steps.map((step, i) => {
              const done = i < current;
              const active = i === current;
              return (
                <div key={step.id} className="flex items-start gap-3 sm:gap-4 px-3.5 py-3.5 sm:px-4 rounded-xl" style={{ background: C.ivory }}>
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-bold shrink-0"
                    style={{
                      background: done ? C.success : active ? C.terracotta : C.bubbleBg,
                      color: done || active ? C.white : C.muted,
                    }}
                  >
                    {done ? "✓" : step.id}
                  </div>
                  <div className="flex-1">
                    <p className="text-[14px] sm:text-[15px] font-semibold mb-0.5" style={{ color: active ? C.dark : C.muted }}>{step.label}</p>
                    {active && (
                      <p className="text-[13px] mt-1" style={{ color: C.muted }}>{step.desc}</p>
                    )}
                  </div>
                  <div className="shrink-0">
                    {done && <span className="text-[12px] font-semibold" style={{ color: C.successText }}>완료</span>}
                    {active && <span className="text-[12px] font-semibold" style={{ color: C.terracotta }}>진행 중</span>}
                    {i > current && <span className="text-[12px]" style={{ color: C.muted }}>대기 중</span>}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-[10px] px-4 py-3" style={{ background: `${C.terracotta}10`, border: `1px solid ${C.terracotta}25` }}>
            <p className="text-[13px] leading-relaxed" style={{ color: C.terracotta }}>
              ⚠️ 이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
