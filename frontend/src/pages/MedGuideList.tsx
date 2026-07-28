import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, ChevronRight, Trash2, CheckSquare, Square } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import PatientContextBanner from "../components/PatientContextBanner";
import PrescriptionImageViewer from "../components/PrescriptionImageViewer";
import { deleteRecord, listRecords, type RecordSummary } from "../api/records";
import { getCurrentUserName, isLoggedIn, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

// [2026-07-20] 등록내역(모든 상태)과 달리, 여기는 실제로 완성된 복약 가이드만 모아 보여준다 —
// 각 카드는 상세(/records/:id)가 아니라 가이드 화면(/records/:id/guide)으로 바로 연결된다.
// [2026-07-25 추가] Records.tsx와 동일한 선택 삭제/전체 삭제 패턴 — 여기서 지워도
// deleteRecord()는 같은 MedicalRecord를 soft-delete하니 등록내역에서도 같이 사라진다.
export default function MedGuideList() {
  const navigate = useNavigate();
  const patientId = useGuardedPatientId();
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

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

  const handleDelete = async (recordId: number) => {
    if (deletingId !== null || !window.confirm("이 복약 가이드를 삭제할까요? 되돌릴 수 없어요.")) return;
    setDeletingId(recordId);
    try {
      await deleteRecord(recordId);
      setRecords((prev) => prev.filter((r) => r.record_id !== recordId));
    } catch {
      setError("삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setDeletingId(null);
    }
  };

  const toggleSelectMode = () => {
    setSelectMode((v) => !v);
    setSelectedIds(new Set());
  };

  const toggleSelected = (recordId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  };

  const allSelected = records.length > 0 && records.every((r) => selectedIds.has(r.record_id));
  const toggleSelectAll = () => {
    setSelectedIds(allSelected ? new Set() : new Set(records.map((r) => r.record_id)));
  };

  const handleBulkDelete = async () => {
    if (bulkDeleting || selectedIds.size === 0) return;
    if (!window.confirm(`선택한 ${selectedIds.size}개를 삭제할까요? 되돌릴 수 없어요.`)) return;
    setBulkDeleting(true);
    try {
      await Promise.all([...selectedIds].map((id) => deleteRecord(id)));
      setRecords((prev) => prev.filter((r) => !selectedIds.has(r.record_id)));
      setSelectedIds(new Set());
      setSelectMode(false);
    } catch {
      setError("일부 항목을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBulkDeleting(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner />
        <div className="flex items-start justify-between mb-1">
          <h1 className="text-[26px] font-black" style={{ color: C.dark }}>복약 가이드</h1>
          {records.length > 0 && (
            <button
              onClick={toggleSelectMode}
              className="text-[13px] font-bold px-3 py-1.5 rounded-full transition-opacity hover:opacity-70 shrink-0"
              style={{ background: selectMode ? C.terracotta : `${C.terracotta}12`, color: selectMode ? C.white : C.terracotta }}
            >
              {selectMode ? "선택 취소" : "선택하기"}
            </button>
          )}
        </div>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          지금까지 완성된 복약 안내를 모아서 볼 수 있어요.
        </p>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {selectMode && records.length > 0 && (
          <div className="rounded-xl px-5 py-3 mb-5 flex items-center justify-between" style={{ background: `${C.terracotta}12` }}>
            <label className="flex items-center gap-2 text-[13px] font-bold cursor-pointer" style={{ color: C.terracotta }}>
              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} className="w-4 h-4 accent-current" />
              전체선택 · {selectedIds.size}개 선택됨
            </label>
            <button
              onClick={handleBulkDelete}
              disabled={selectedIds.size === 0 || bulkDeleting}
              className="px-4 py-2 rounded-full text-[13px] font-bold text-white disabled:opacity-50"
              style={{ background: "#D94F4F" }}
            >
              {bulkDeleting ? "삭제하는 중..." : "선택 삭제"}
            </button>
          </div>
        )}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
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
            {records.map((r) => {
              const selected = selectedIds.has(r.record_id);
              return (
                <div
                  key={r.record_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => (selectMode ? toggleSelected(r.record_id) : navigate(`/records/${r.record_id}/guide`))}
                  onKeyDown={(e) =>
                    e.key === "Enter" && (selectMode ? toggleSelected(r.record_id) : navigate(`/records/${r.record_id}/guide`))
                  }
                  className="w-full text-left rounded-2xl p-5 transition-transform hover:-translate-y-0.5 active:scale-[0.99] cursor-pointer"
                  style={{
                    background: C.white,
                    boxShadow: C.shadowCard,
                    border: selected ? `2px solid ${C.terracotta}` : "2px solid transparent",
                  }}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-start gap-3">
                      {selectMode && (
                        <span className="mt-0.5 shrink-0">
                          {selected ? (
                            <CheckSquare className="w-5 h-5" style={{ color: C.terracotta }} />
                          ) : (
                            <Square className="w-5 h-5" style={{ color: "rgba(30,26,23,0.25)" }} />
                          )}
                        </span>
                      )}
                      <div>
                        <p className="text-[12px] mb-1" style={{ color: C.muted }}>
                          {new Date(r.created_at).toLocaleDateString("ko-KR")}
                        </p>
                        <p className="text-[17px] font-black" style={{ color: C.dark }}>
                          {r.diagnosis || "진단명 확인 중"}
                        </p>
                      </div>
                    </div>
                    {!selectMode && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(r.record_id);
                          }}
                          disabled={deletingId === r.record_id}
                          aria-label="복약 가이드 삭제"
                          className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-50"
                          style={{ background: "rgba(217,79,79,0.10)" }}
                        >
                          <Trash2 className="w-4 h-4" style={{ color: "#D94F4F" }} />
                        </button>
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.success}29` }}>
                          <FileText className="w-5 h-5" style={{ color: C.successText }} />
                        </div>
                      </div>
                    )}
                  </div>
                  <p className="text-[13px] mb-4" style={{ color: C.muted }}>
                    {r.drug_names.length > 0 ? r.drug_names.join(", ") : "인식된 약품 없음"}
                  </p>
                  <div className="border-t pt-3 flex items-center justify-between" style={{ borderColor: "rgba(30,26,23,0.08)" }}>
                    <div>{r.has_image && <PrescriptionImageViewer recordId={r.record_id} />}</div>
                    <span className="flex items-center gap-1 text-[13px] font-bold" style={{ color: C.terracotta }}>
                      가이드 보기 <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
