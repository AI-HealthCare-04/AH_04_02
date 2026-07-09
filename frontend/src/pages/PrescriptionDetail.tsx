import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
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
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/records")}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 등록내역으로
        </button>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : error || !result ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
          </div>
        ) : result.status === "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[15px] font-bold mb-2" style={{ color: C.dark }}>확인이 필요해요</p>
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
            {/* 처방 헤더 — Figma 처방 상세 화면 스타일 */}
            <div
              className="rounded-3xl p-7 mb-5"
              style={{ background: "linear-gradient(135deg, #2C2318 0%, #1E1A17 100%)", boxShadow: "0 8px 32px rgba(30,26,23,0.25)" }}
            >
              <p className="text-[13px] mb-2" style={{ color: "rgba(255,255,255,0.5)" }}>
                처방일 {new Date(result.created_at).toLocaleDateString("ko-KR")}
              </p>
              <h1 className="text-[24px] font-black mb-3" style={{ color: C.white }}>
                {result.guide.lifestyle_guide.diagnosis}
              </h1>
              <div className="flex flex-wrap gap-2">
                {result.medications.map((m) => (
                  <span key={m.id} className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.12)", color: C.white }}>
                    {m.drug_name}
                  </span>
                ))}
              </div>
            </div>

            <div
              className="rounded-xl px-4 py-3 mb-6"
              style={{ background: "#FFF8F4", border: "1px solid #F0E5D8" }}
            >
              <p className="text-[13px]" style={{ color: C.terracotta }}>⚠️ {STATIC_DISCLAIMER}</p>
            </div>

            {/* 처방 약물 정보 */}
            <h2 className="text-[16px] font-black mb-4" style={{ color: C.dark }}>📄 처방 약물 정보</h2>
            <div className="space-y-3 mb-8">
              {result.medications.map((m) => (
                <button
                  key={m.id}
                  onClick={() => navigate(`/records/${result.record_id}/drugs/${m.id}`)}
                  className="w-full text-left rounded-2xl p-5 flex items-start gap-4 transition-all hover:shadow-md"
                  style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)", border: "1.5px solid rgba(30,26,23,0.07)" }}
                >
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0 text-[20px]" style={{ background: `${C.terracotta}12` }}>💊</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-black text-[15px]" style={{ color: C.dark }}>{m.drug_name}</p>
                      <ChevronRight className="w-4 h-4 shrink-0" style={{ color: C.muted }} />
                    </div>
                    <p className="text-[12px] mb-1" style={{ color: C.muted }}>{m.drug_class}</p>
                    <p className="text-[13px]" style={{ color: C.dark }}>{m.dosage} · {m.frequency}</p>
                  </div>
                </button>
              ))}
            </div>

            <button
              onClick={() => navigate(`/records/${result.record_id}/guide`)}
              className="w-full py-4 rounded-full text-white font-black text-[16px] hover:opacity-88 transition-all flex items-center justify-center gap-1.5"
              style={{ background: C.terracotta }}
            >
              이 처방전 복약 가이드 보기 <ChevronRight className="w-4 h-4" />
            </button>
          </>
        )}
      </main>
    </div>
  );
}
