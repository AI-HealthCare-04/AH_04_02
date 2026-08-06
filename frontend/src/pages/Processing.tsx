import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { TriangleAlert } from "lucide-react";
import NavBar from "../components/NavBar";
import yakkongMascot from "../assets/yakkong-mascot.png";
import { createRecord, getDrugIndication } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName, isLoggedIn } from "../lib/session";

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
  // [2026-07-22 추가] React StrictMode(main.tsx)는 개발 모드에서 마운트 이펙트를 일부러
  // 두 번 실행한다 — 여기 가드가 없으면 그때마다 POST /records가 두 번 나가서 같은
  // 처방전이 등록내역에 중복으로 쌓였다(실제 공유 DB에서 확인된 원인). 컴포넌트가 같은
  // 인스턴스로 두 번째 이펙트를 도는 것뿐이라 ref 값은 그대로 살아있으므로, 이미 한 번
  // 시작했으면 두 번째 실행은 건너뛴다.
  const startedRef = useRef(false);

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
      // [2026-08-04 추가, 사용자 지적 반영] PrescriptionReview.tsx가 마운트되자마자
      // getRecord() 재조회 + 약품명당 getDrugIndication() 검증을 또 해서, 이 화면을
      // 벗어난 뒤에도 눈에 띄게 한 번 더 기다려야 했다 — 여기서 미리 다 끝내고
      // navigate state로 넘기면 도착하자마자 바로 렌더링된다(리뷰 쪽은 state가
      // 없을 때만 기존처럼 자기가 다시 불러온다 — 새로고침/직접 진입 대비).
      const nameOkEntries = await Promise.all(
        result.medications.map(async (m) => {
          try {
            const info = await getDrugIndication(m.drug_name);
            return [m.id, info.matched_name !== null] as const;
          } catch {
            return [m.id, true] as const;
          }
        })
      );
      const drugNameOk: Record<number, boolean> = {};
      nameOkEntries.forEach(([id, ok]) => { drugNameOk[id] = ok; });

      if (visualRef.current) clearInterval(visualRef.current);
      setCurrent(steps.length - 1);
      // [7/9 변경] OCR 신뢰도와 무관하게 항상 확인 화면을 거치므로 /result 인터스티셜 없이 바로 이동
      setTimeout(
        () => navigate(`/records/${result.record_id}/review`, { state: { record: result, drugNameOk } }),
        400
      );
    } catch (err: unknown) {
      if (visualRef.current) clearInterval(visualRef.current);
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      navigate("/ocr-error", { state: { reason: detail } });
    }
  };

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    runUpload();
    return () => {
      if (visualRef.current) clearInterval(visualRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen" style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-[600px] mx-auto flex flex-col items-center px-5 py-14 sm:px-6 sm:py-20">
        <div
          className="w-full border rounded-[20px] p-7 sm:px-10 sm:py-12 text-center"
          style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)" }}
        >
          <img src={yakkongMascot} alt="" className="w-16 h-16 sm:w-20 sm:h-20 mx-auto mb-4 sm:mb-5" />
          <h1 className="text-[22px] sm:text-[26px] font-bold mb-2 sm:mb-2.5" style={{ color: C.dark }}>분석을 시작할게요</h1>
          <p className="text-[14px] sm:text-[15px] mb-8 sm:mb-10" style={{ color: C.muted }}>잠시만 기다려 주세요. 보통 1분 정도 걸려요.</p>

          <div className="flex flex-col gap-3 sm:gap-4 text-left mb-8 sm:mb-9">
            {steps.map((step, i) => {
              const done = i < current;
              const active = i === current;
              return (
                <div key={step.id} className="flex items-start gap-3 sm:gap-4 px-3.5 py-3.5 sm:px-4 rounded-xl" style={{ background: C.ivory }}>
                  <div className="relative w-8 h-8 shrink-0">
                    <div
                      className="absolute inset-0 rounded-full flex items-center justify-center text-[13px] font-bold"
                      style={{
                        background: done ? C.success : C.bubbleBg,
                        color: done ? C.white : active ? C.terracotta : C.muted,
                      }}
                    >
                      {done ? "✓" : step.id}
                    </div>
                    {/* [2026-07-22 추가] 마지막 단계(맞춤 가이드 생성)는 실제 LLM 호출이라 화면상
                        가짜 진행바가 멈춰 보여도 실제로는 계속 처리 중이다 — 진행 중인 단계에
                        도는 링을 씌워 "멈춘 게 아니라 로딩 중"임을 보여준다. */}
                    {active && (
                      <div
                        className="absolute inset-0 rounded-full animate-spin"
                        style={{ border: "2.5px solid transparent", borderTopColor: C.terracotta, borderRightColor: `${C.terracotta}35` }}
                      />
                    )}
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
            <p className="flex items-start gap-1.5 text-[13px] leading-relaxed" style={{ color: C.terracotta }}>
              <TriangleAlert className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={2.2} /> 이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
