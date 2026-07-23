import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, ChevronRight } from "lucide-react";
import NavBar from "../components/NavBar";
import PatientContextBanner from "../components/PatientContextBanner";
import { listRecords, type RecordSummary } from "../api/records";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

// [2026-07-20] 등록내역(모든 상태)과 달리, 여기는 실제로 완성된 복약 가이드만 모아 보여준다 —
// 각 카드는 상세(/records/:id)가 아니라 가이드 화면(/records/:id/guide)으로 바로 연결된다.
export default function MedGuideList() {
  const navigate = useNavigate();
  const patientId = useGuardedPatientId();
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (patientId == null) return;
    // StrictMode(개발 모드)가 effect를 두 번 실행하면서 동일한 요청이 2개 동시에 나가는데,
    // 어느 쪽이 살아남을지는 브라우저/네트워크 레이어의 우연에 달려있어 취소 플래그만으론
    // "취소된 게 항상 옛(첫 번째) 요청"이라고 보장할 수 없었다 — AbortController로 옛
    // 요청을 직접 취소해서 항상 새 요청만 남게 만든다.
    const controller = new AbortController();
    listRecords(patientId, controller.signal)
      .then((list) => setRecords(list.filter((r) => r.status === "completed")))
      .catch(() => {
        if (controller.signal.aborted) return;
        setError("복약 가이드를 불러오지 못했어요.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [patientId]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner />
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>복약 가이드</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          지금까지 완성된 복약 안내를 모아서 볼 수 있어요.
        </p>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : records.length === 0 ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface, boxShadow: C.shadowCard }}>
            <p className="text-[14px] mb-4" style={{ color: C.muted }}>아직 완성된 복약 가이드가 없어요.</p>
            <button
              onClick={() => navigate("/upload")}
              className="px-6 py-3 rounded-full font-bold text-[14px] text-white"
              style={{ background: C.terracotta }}
            >
              처방전 등록하러 가기
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {records.map((r) => (
              <div
                key={r.record_id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/records/${r.record_id}/guide`)}
                onKeyDown={(e) => e.key === "Enter" && navigate(`/records/${r.record_id}/guide`)}
                className="w-full text-left rounded-2xl p-5 transition-transform hover:-translate-y-0.5 active:scale-[0.99] cursor-pointer"
                style={{ background: C.white, boxShadow: C.shadowCard }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-[12px] mb-1" style={{ color: C.muted }}>
                      {new Date(r.created_at).toLocaleDateString("ko-KR")}
                    </p>
                    <p className="text-[17px] font-black" style={{ color: C.dark }}>
                      {r.diagnosis || "진단명 확인 중"}
                    </p>
                  </div>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.success}29` }}>
                    <FileText className="w-5 h-5" style={{ color: C.successText }} />
                  </div>
                </div>
                <p className="text-[13px] mb-4" style={{ color: C.muted }}>
                  {r.drug_names.length > 0 ? r.drug_names.join(", ") : "인식된 약품 없음"}
                </p>
                <div className="border-t pt-3 flex items-center justify-end" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                  <span className="flex items-center gap-1 text-[13px] font-bold" style={{ color: C.terracotta }}>
                    가이드 보기 <ChevronRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
