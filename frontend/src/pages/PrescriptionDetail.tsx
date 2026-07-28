import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, FileText, Pill, TriangleAlert } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import PrescriptionImageViewer from "../components/PrescriptionImageViewer";
import { getRecord, type RecordResult } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName, isLoggedIn } from "../lib/session";

const STATIC_DISCLAIMER =
  "이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.";

export default function PrescriptionDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { recordId } = useParams<{ recordId: string }>();
  const [result, setResult] = useState<RecordResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // [2026-07-23 추가] PrescriptionReview.tsx에서 확정 직후 넘어올 때만 있는 값 —
  // 이미 활성 일정이 있어 새로 등록하지 않은 약 이름들("이미 등록된 처방" 배너용).
  const duplicateDrugNames = (location.state as { duplicateDrugNames?: string[] } | null)?.duplicateDrugNames ?? [];

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(setResult)
      .catch(() => setError("처방 기록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/records")}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 등록내역으로
        </button>

        {duplicateDrugNames.length > 0 && (
          <div
            className="rounded-xl px-4 py-3 mb-5"
            style={{ background: C.warningBg, border: `1px solid ${C.warningBorder}` }}
          >
            <p className="text-[13px] font-bold" style={{ color: C.warningText }}>
              {duplicateDrugNames.join(", ")}은(는) 이미 등록된 처방이에요
            </p>
            <p className="text-[12px] mt-0.5" style={{ color: C.warningText }}>
              오늘의 복약에 중복으로 추가하지 않았어요.
            </p>
          </div>
        )}

        {loading ? (
          <>
            <div className="rounded-3xl p-7 mb-5" style={{ background: "#2C2318" }}>
              <Skeleton className="h-3 w-24 mb-3" style={{ background: "rgba(255,255,255,0.15)" }} />
              <Skeleton className="h-6 w-48 mb-4" style={{ background: "rgba(255,255,255,0.15)" }} />
              <div className="flex gap-2">
                <Skeleton className="h-6 w-20 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }} />
                <Skeleton className="h-6 w-20 rounded-full" style={{ background: "rgba(255,255,255,0.15)" }} />
              </div>
            </div>
            <div className="space-y-3 mb-8">
              {[1, 2].map((i) => (
                <div key={i} className="rounded-2xl p-5 flex items-start gap-4" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <Skeleton className="w-11 h-11 shrink-0" />
                  <div className="flex-1">
                    <Skeleton className="h-4 w-32 mb-2" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : error || !result ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface }}>
            <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
          </div>
        ) : result.status === "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface }}>
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
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface }}>
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

            {result.has_image && (
              <div className="flex justify-end mb-3">
                <PrescriptionImageViewer recordId={result.record_id} />
              </div>
            )}

            <div
              className="rounded-xl px-4 py-3 mb-6"
              style={{ background: "#FFF8F4", border: "1px solid #F0E5D8" }}
            >
              <p className="flex items-start gap-1.5 text-[13px]" style={{ color: C.terracotta }}>
                <TriangleAlert className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={2.2} /> {STATIC_DISCLAIMER}
              </p>
            </div>

            {/* 처방 약물 정보 */}
            <h2 className="flex items-center gap-1.5 text-[16px] font-black mb-4" style={{ color: C.dark }}>
              <FileText className="w-[18px] h-[18px]" style={{ color: C.terracotta }} strokeWidth={2.2} /> 처방 약물 정보
            </h2>
            <div className="space-y-3 mb-8">
              {result.medications.map((m) => (
                <button
                  key={m.id}
                  onClick={() => navigate(`/records/${result.record_id}/drugs/${m.id}`)}
                  className="w-full text-left rounded-2xl p-5 flex items-start gap-4 transition-all hover:shadow-md"
                  style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)", border: "1.5px solid rgba(30,26,23,0.07)" }}
                >
                  <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: C.terracotta }}>
                    <Pill className="w-5 h-5" style={{ color: C.white }} strokeWidth={2.2} />
                  </div>
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
