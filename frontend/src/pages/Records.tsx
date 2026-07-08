import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search, FileText, ChevronRight } from "lucide-react";
import NavBar from "../components/NavBar";
import { listRecords, type RecordSummary } from "../api/records";
import { getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

const STATUS_LABEL: Record<RecordSummary["status"], { text: string; bg: string; color: string }> = {
  completed: { text: "분석 완료", bg: `${C.success}20`, color: "#4A7A47" },
  review_required: { text: "확인 필요", bg: C.warningBg, color: C.warningText },
  processing: { text: "처리 중", bg: C.bubbleBg, color: C.muted },
  failed: { text: "실패", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
};

export default function Records() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const patientId = Number(searchParams.get("patient_id")) || getCurrentPatientId();
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listRecords(patientId)
      .then(setRecords)
      .catch(() => setError("이용 기록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const filtered = records.filter(
    (r) =>
      !search ||
      r.diagnosis.includes(search) ||
      r.drug_names.some((d) => d.includes(search))
  );

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>이용 기록</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          지금까지 업로드한 처방전과 복약 안내 결과를 확인할 수 있어요.
        </p>

        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: C.muted }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="진단명 또는 약품명 검색"
            className="w-full pl-11 pr-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)" }}
          />
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            <p className="text-[14px]" style={{ color: C.muted }}>
              {records.length === 0 ? "아직 업로드한 처방전이 없어요." : "검색 결과가 없어요."}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((r) => {
              const s = STATUS_LABEL[r.status];
              return (
                <button
                  key={r.record_id}
                  onClick={() => navigate(`/records/${r.record_id}`)}
                  className="w-full text-left rounded-2xl p-5 transition-transform hover:-translate-y-0.5"
                  style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}
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
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.terracotta}12` }}>
                      <FileText className="w-5 h-5" style={{ color: C.terracotta }} />
                    </div>
                  </div>
                  <p className="text-[13px] mb-4" style={{ color: C.muted }}>
                    {r.drug_names.length > 0 ? r.drug_names.join(", ") : "인식된 약품 없음"}
                  </p>
                  <div className="border-t pt-3 flex items-center justify-between" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                    <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: s.bg, color: s.color }}>
                      {s.text}
                    </span>
                    <span className="flex items-center gap-1 text-[13px] font-bold" style={{ color: C.terracotta }}>
                      자세히 보기 <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
