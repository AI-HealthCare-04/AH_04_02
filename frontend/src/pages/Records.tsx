import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search, FileText, ChevronRight, Trash2, Star, CheckSquare, Square } from "lucide-react";
import NavBar from "../components/NavBar";
import { deleteRecord, listRecords, pinRecord, type RecordSummary } from "../api/records";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
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
  const guardedPatientId = useGuardedPatientId();
  const patientId = Number(searchParams.get("patient_id")) || guardedPatientId;
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [dateFilter, setDateFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [pinningId, setPinningId] = useState<number | null>(null);
  // [2026-07-21 추가] 여러 개 선택해서 한 번에 삭제하는 기능
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // [2026-07-20] 내비바 통합검색창에서 /records?search=...로 넘어오는 경우 반영 — useState
  // 초기값만으론 이미 /records에 있을 때(같은 라우트라 리마운트 없이 쿼리스트링만 바뀜)
  // 반영이 안 돼서 searchParams가 바뀔 때마다 동기화되도록 별도 effect로 분리.
  useEffect(() => {
    setSearch(searchParams.get("search") ?? "");
  }, [searchParams]);

  useEffect(() => {
    if (patientId == null) return;
    loadRecords();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  const loadRecords = async () => {
    if (patientId == null) return;
    setError("");
    try {
      setRecords(await listRecords(patientId));
    } catch {
      setError("등록내역을 불러오지 못했어요.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (recordId: number) => {
    if (deletingId !== null || !window.confirm("이 등록내역을 삭제할까요? 되돌릴 수 없어요.")) return;
    setDeletingId(recordId);
    try {
      await deleteRecord(recordId);
      await loadRecords();
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

  // [2026-07-21 추가] 즐겨찾기처럼 위쪽에 고정 — 낙관적으로 먼저 바꾸고, 목록도 고정 우선으로
  // 다시 정렬한다(서버가 내려주는 순서와 동일한 규칙: pinned desc, 그다음 기존 순서 유지).
  const handleTogglePin = async (r: RecordSummary) => {
    if (pinningId !== null) return;
    setPinningId(r.record_id);
    const nextPinned = !r.pinned;
    const prev = records;
    setRecords((cur) => {
      const updated = cur.map((x) => (x.record_id === r.record_id ? { ...x, pinned: nextPinned } : x));
      return [...updated].sort((a, b) => Number(b.pinned) - Number(a.pinned));
    });
    try {
      await pinRecord(r.record_id, nextPinned);
    } catch {
      setRecords(prev);
      setError("고정 상태를 바꾸지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setPinningId(null);
    }
  };

  const filtered = records.filter(
    (r) =>
      (!search || r.diagnosis.includes(search) || r.drug_names.some((d) => d.includes(search))) &&
      (!dateFilter || r.created_at.slice(0, 10) === dateFilter)
  );

  // [2026-07-22 추가] 지금 보이는(검색/날짜 필터 적용된) 목록 기준 전체선택/해제
  const allFilteredSelected = filtered.length > 0 && filtered.every((r) => selectedIds.has(r.record_id));
  const toggleSelectAll = () => {
    setSelectedIds(allFilteredSelected ? new Set() : new Set(filtered.map((r) => r.record_id)));
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <div className="flex items-start justify-between mb-1">
          <h1 className="text-[26px] font-black" style={{ color: C.dark }}>등록내역</h1>
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
          지금까지 업로드한 처방전과 복약 안내 결과를 확인할 수 있어요.
        </p>

        {selectMode && (
          <div className="rounded-xl px-5 py-3 mb-5 flex items-center justify-between" style={{ background: `${C.terracotta}12` }}>
            <label className="flex items-center gap-2 text-[13px] font-bold cursor-pointer" style={{ color: C.terracotta }}>
              <input type="checkbox" checked={allFilteredSelected} onChange={toggleSelectAll} className="w-4 h-4 accent-current" />
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

        <div className="flex gap-2 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: C.muted }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="진단명 또는 약품명 검색"
              className="w-full pl-11 pr-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
              style={{ borderColor: "rgba(30,26,23,0.15)" }}
            />
          </div>
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="px-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)", color: dateFilter ? C.dark : C.muted }}
          />
          {dateFilter && (
            <button
              onClick={() => setDateFilter("")}
              className="px-4 py-3 rounded-xl text-[13px] font-bold shrink-0"
              style={{ background: `${C.terracotta}12`, color: C.terracotta }}
            >
              초기화
            </button>
          )}
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            <p className="text-[14px]" style={{ color: C.muted }}>
              {records.length === 0 ? "아직 업로드한 처방전이 없어요." : "검색 결과가 없어요."}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((r) => {
              const s = STATUS_LABEL[r.status];
              const selected = selectedIds.has(r.record_id);
              return (
                <div
                  key={r.record_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => (selectMode ? toggleSelected(r.record_id) : navigate(`/records/${r.record_id}`))}
                  onKeyDown={(e) =>
                    e.key === "Enter" && (selectMode ? toggleSelected(r.record_id) : navigate(`/records/${r.record_id}`))
                  }
                  className="w-full text-left rounded-2xl p-5 transition-transform hover:-translate-y-0.5 cursor-pointer"
                  style={{
                    background: C.surface,
                    boxShadow: "0 2px 16px rgba(30,26,23,0.07)",
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
                        <div className="flex items-center gap-1.5 mb-1">
                          {r.pinned && <Star className="w-3 h-3" fill={C.terracotta} style={{ color: C.terracotta }} />}
                          <p className="text-[12px]" style={{ color: C.muted }}>
                            {new Date(r.created_at).toLocaleDateString("ko-KR")}
                          </p>
                        </div>
                        <p className="text-[17px] font-black" style={{ color: C.dark }}>
                          {r.diagnosis || "진단명 확인 중"}
                        </p>
                        {r.uploaded_by_name && (
                          <p className="text-[11px] font-bold mt-1" style={{ color: C.terracotta }}>
                            {r.uploaded_by_name}님이 대신 올려드렸어요
                          </p>
                        )}
                      </div>
                    </div>
                    {!selectMode && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTogglePin(r);
                          }}
                          disabled={pinningId === r.record_id}
                          aria-label={r.pinned ? "고정 해제" : "위쪽에 고정"}
                          className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-50"
                          style={{ background: r.pinned ? `${C.terracotta}20` : "rgba(30,26,23,0.06)" }}
                        >
                          <Star className="w-4 h-4" fill={r.pinned ? C.terracotta : "none"} style={{ color: r.pinned ? C.terracotta : C.muted }} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(r.record_id);
                          }}
                          disabled={deletingId === r.record_id}
                          aria-label="등록내역 삭제"
                          className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-50"
                          style={{ background: "rgba(217,79,79,0.10)" }}
                        >
                          <Trash2 className="w-4 h-4" style={{ color: "#D94F4F" }} />
                        </button>
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${C.terracotta}12` }}>
                          <FileText className="w-5 h-5" style={{ color: C.terracotta }} />
                        </div>
                      </div>
                    )}
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
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
