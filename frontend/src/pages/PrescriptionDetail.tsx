import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import NavBar from "../components/NavBar";
import { getRecord, type RecordResult } from "../api/records";
import { C } from "../theme";

const STATIC_DISCLAIMER =
  "이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.";

export default function PrescriptionDetail() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [result, setResult] = useState<RecordResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(setResult)
      .catch(() => setError("처방 기록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-3xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/records")}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 이용 기록으로
        </button>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : error || !result ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
          </div>
        ) : result.status === "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[15px] font-bold mb-2" style={{ color: C.dark }}>보호자 확인이 필요해요</p>
            <p className="text-[13px] mb-5" style={{ color: C.muted }}>
              OCR 인식 정확도가 낮은 항목이 있어요. 직접 확인·수정하면 복약 가이드를 만들어드려요.
            </p>
            <button
              onClick={() => navigate(`/records/${result.record_id}/review`)}
              className="px-6 py-3 rounded-full font-bold text-[14px] text-white"
              style={{ background: C.terracotta }}
            >
              처방전 확인하러 가기
            </button>
          </div>
        ) : result.status === "failed" || !result.guide ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[15px] font-bold mb-2" style={{ color: C.dark }}>결과를 생성하지 못했어요</p>
            <p className="text-[13px]" style={{ color: C.muted }}>
              {result.failure_reason || "안내를 만들지 못했어요."}
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-[26px] font-black" style={{ color: C.dark }}>복약 안내 결과</h1>
              <span
                className="px-3 py-1 rounded-full text-[12px] font-bold"
                style={{ background: `${C.success}20`, color: "#4A7A47" }}
              >
                ✓ 분석 완료
              </span>
            </div>

            <div
              className="rounded-xl px-4 py-3 mb-6"
              style={{ background: "#FFF8F4", border: "1px solid #F0E5D8" }}
            >
              <p className="text-[13px]" style={{ color: C.terracotta }}>⚠️ {STATIC_DISCLAIMER}</p>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <section className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                <h2 className="text-[15px] font-bold mb-4" style={{ color: C.dark }}>📄 OCR 인식 결과</h2>
                {result.medications.map((med, i) => (
                  <div
                    key={i}
                    className="flex items-start justify-between py-2.5"
                    style={{ borderTop: i > 0 ? "1px solid #F5F0EB" : undefined }}
                  >
                    <div>
                      <p className="text-[14px] font-bold" style={{ color: C.dark }}>{med.drug_name}</p>
                      <p className="text-[12px]" style={{ color: C.muted }}>{med.dosage} · {med.frequency}</p>
                      {med.review_required && (
                        <p className="text-[11px] mt-1" style={{ color: "#D98A2B" }}>
                          확인 필요 (인식 정확도 {Math.round(med.confidence * 100)}%)
                        </p>
                      )}
                    </div>
                    <span
                      className="text-[11px] px-2 py-1 rounded-full shrink-0"
                      style={{ background: "#F0E5D8", color: C.terracotta }}
                    >
                      {med.drug_class}
                    </span>
                  </div>
                ))}
              </section>

              <div className="flex flex-col gap-5">
                <section className="rounded-2xl p-5" style={{ background: "#FFF8F4", border: "1px solid #F0E5D8" }}>
                  <h2 className="text-[15px] font-bold mb-2" style={{ color: C.dark }}>🔍 진단 기반 안내</h2>
                  <p className="text-[16px] font-bold" style={{ color: C.terracotta }}>
                    {result.guide.lifestyle_guide.diagnosis}
                  </p>
                </section>

                <section className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                  <h2 className="text-[15px] font-bold mb-3" style={{ color: C.dark }}>💊 맞춤 복약 지도</h2>
                  {result.guide.medication_guide.drugs.map((drug, i) => (
                    <div key={i} className="py-2.5" style={{ borderTop: i > 0 ? "1px solid #F5F0EB" : undefined }}>
                      <p className="text-[13px] font-bold" style={{ color: "#4A4A4A" }}>💊 {drug.drug_name}</p>
                      <p className="text-[13px]" style={{ color: "#555555" }}>{drug.dosage_text}</p>
                      {drug.caution && (
                        <p className="text-[13px] mt-1" style={{ color: C.terracotta }}>⚠️ {drug.caution}</p>
                      )}
                    </div>
                  ))}
                </section>

                <section className="rounded-2xl p-5" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                  <h2 className="text-[15px] font-bold mb-3" style={{ color: C.dark }}>🌿 생활습관 개선 가이드</h2>
                  <div className="py-2.5">
                    <p className="text-[13px] font-bold" style={{ color: "#4A4A4A" }}>🥗 식이</p>
                    <p className="text-[13px]" style={{ color: "#555555" }}>
                      피해야 할 음식: {result.guide.lifestyle_guide.diet.avoid.join(", ") || "없음"}
                    </p>
                    {result.guide.lifestyle_guide.diet.drug_specific.length > 0 && (
                      <p className="text-[13px]" style={{ color: "#555555" }}>
                        {result.guide.lifestyle_guide.diet.drug_specific.join(" ")}
                      </p>
                    )}
                  </div>
                  <div className="py-2.5" style={{ borderTop: "1px solid #F5F0EB" }}>
                    <p className="text-[13px] font-bold" style={{ color: "#4A4A4A" }}>🏃 운동</p>
                    <p className="text-[13px]" style={{ color: "#555555" }}>
                      {result.guide.lifestyle_guide.exercise.type} · {result.guide.lifestyle_guide.exercise.duration} ·{" "}
                      {result.guide.lifestyle_guide.exercise.intensity}
                    </p>
                  </div>
                  {result.guide.source_refs.length > 0 && (
                    <p className="text-[12px] mt-3 pt-3" style={{ color: "#AAAAAA", borderTop: "1px solid #F5F0EB" }}>
                      출처: {result.guide.source_refs.map((s) => s.title).join(", ")}
                    </p>
                  )}
                </section>
              </div>
            </div>

            <button
              onClick={() => navigate("/chat")}
              className="w-full mt-6 py-4 rounded-xl font-bold text-[15px] text-white"
              style={{ background: C.terracotta }}
            >
              💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
            </button>
          </>
        )}
      </main>
    </div>
  );
}
