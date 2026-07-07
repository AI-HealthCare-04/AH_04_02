import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { createAssessment, type CareLevel, type Level } from "../api/care";
import { getCurrentPatientId } from "../lib/session";

const CARE_LEVEL_LABEL: Record<CareLevel, string> = {
  independent: "자가관리 가능",
  guardian_check: "보호자 확인 필요",
  third_party_needed: "제3자 도움 필요",
};

const CARE_LEVEL_STYLE: Record<CareLevel, string> = {
  independent: "bg-[#8FAE8B]/10 border-[#8FAE8B] text-[#4A7A47]",
  guardian_check: "bg-[#E08A5B]/10 border-[#E08A5B] text-[#B8621B]",
  third_party_needed: "bg-[#C1653D]/10 border-[#C1653D] text-[#C1653D]",
};

const LEVELS: { key: Level; label: string }[] = [
  { key: "normal", label: "정상" },
  { key: "mild", label: "경미" },
  { key: "severe", label: "심각" },
];

function pillClass(active: boolean) {
  return `px-5 py-2 rounded-full text-[14px] font-bold border-2 transition-all ${
    active ? "bg-[#7C8B5D] border-[#7C8B5D] text-white" : "bg-[#F5F0EA] border-[#D9CFC7] text-[#888888]"
  }`;
}

export default function Check() {
  const navigate = useNavigate();
  const [cognitive, setCognitive] = useState<Level>("normal");
  const [mobility, setMobility] = useState<Level>("normal");
  const [vision, setVision] = useState<Level>("normal");
  const [awareness, setAwareness] = useState(true);
  const [willingness, setWillingness] = useState(true);
  const [result, setResult] = useState<{ care_level: CareLevel; reason: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const saved = await createAssessment({
        patient_id: getCurrentPatientId(),
        cognitive_level: cognitive,
        mobility_level: mobility,
        vision_level: vision,
        medication_awareness: awareness,
        medication_willingness: willingness,
      });
      setResult({ care_level: saved.care_level, reason: saved.reason });
    } catch {
      setError("저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF6F1]">
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black text-[#2A2A2A] mb-2">자가진단 체크리스트</h1>
        <p className="text-[14px] text-[#888888] mb-7">
          대상자의 현재 상태를 입력하면 적합한 도움 수준을 판정합니다.
        </p>

        <div className="bg-white border border-[#EEE6DC] rounded-2xl p-6 mb-5">
          <p className="text-[13px] font-bold text-[#888888] mb-4">기능 수준 평가</p>

          <div className="flex items-center justify-between py-3.5 border-b border-[#F5F0EA] flex-wrap gap-2">
            <span className="text-[15px] font-medium text-[#2A2A2A]">인지 수준</span>
            <div className="flex gap-2">
              {LEVELS.map((l) => (
                <button key={l.key} onClick={() => setCognitive(l.key)} className={pillClass(cognitive === l.key)}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between py-3.5 border-b border-[#F5F0EA] flex-wrap gap-2">
            <span className="text-[15px] font-medium text-[#2A2A2A]">거동 수준</span>
            <div className="flex gap-2">
              {LEVELS.map((l) => (
                <button key={l.key} onClick={() => setMobility(l.key)} className={pillClass(mobility === l.key)}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between py-3.5 flex-wrap gap-2">
            <span className="text-[15px] font-medium text-[#2A2A2A]">시력 수준</span>
            <div className="flex gap-2">
              {LEVELS.map((l) => (
                <button key={l.key} onClick={() => setVision(l.key)} className={pillClass(vision === l.key)}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#EEE6DC] rounded-2xl p-6 mb-7">
          <p className="text-[13px] font-bold text-[#888888] mb-4">복약 인식 및 의지</p>

          <div className="flex items-center justify-between py-3.5 border-b border-[#F5F0EA] flex-wrap gap-2">
            <span className="text-[15px] font-medium text-[#2A2A2A]">복용해야 함을 인지하는가</span>
            <div className="flex gap-2">
              <button onClick={() => setAwareness(true)} className={pillClass(awareness)}>예</button>
              <button onClick={() => setAwareness(false)} className={pillClass(!awareness)}>아니오</button>
            </div>
          </div>

          <div className="flex items-center justify-between py-3.5 flex-wrap gap-2">
            <span className="text-[15px] font-medium text-[#2A2A2A]">복용 의지가 있는가</span>
            <div className="flex gap-2">
              <button onClick={() => setWillingness(true)} className={pillClass(willingness)}>예</button>
              <button onClick={() => setWillingness(false)} className={pillClass(!willingness)}>아니오</button>
            </div>
          </div>
        </div>

        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="w-full py-4 rounded-xl bg-[#C1653D] text-white font-bold text-[16px] disabled:opacity-60"
        >
          {submitting ? "저장 중..." : "저장 및 평가하기"}
        </button>

        {result && (
          <div className={`mt-6 rounded-2xl p-6 border-2 ${CARE_LEVEL_STYLE[result.care_level]}`}>
            <p className="text-[12px] font-bold uppercase tracking-widest mb-2">평가 결과</p>
            <p className="text-[24px] font-black text-[#2A2A2A] mb-2">
              {CARE_LEVEL_LABEL[result.care_level]}
            </p>
            <p className="text-[14px] text-[#888888] leading-relaxed mb-5">{result.reason}</p>
            <button
              onClick={() => navigate("/select")}
              className="px-6 py-3 rounded-full bg-[#C1653D] text-white font-bold text-[14px]"
            >
              다음 →
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
