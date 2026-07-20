import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, Check } from "lucide-react";
import NavBar from "../components/NavBar";
import {
  addMedicationItem,
  confirmMedications,
  getDrugIndication,
  getRecord,
  removeMedicationItem,
  type OcrMedication,
  type RecordResult,
} from "../api/records";
import { C } from "../theme";

const FIELDS: { key: keyof OcrMedication; label: string }[] = [
  { key: "drug_name", label: "약품명" },
  { key: "dosage", label: "용량" },
  { key: "frequency", label: "복용횟수" },
  { key: "diagnosis", label: "진단명" },
  { key: "drug_class", label: "약효분류" },
];

// 용량엔 반드시 숫자+단위가 같이 있어야 함 (예: "500mg") — "500"처럼 단위 빠진 OCR 오류를 잡아냄
const DOSAGE_RE = /(\d+\/\d+|\d+\.?\d*)\s*(mg|g|ml|mcg|iu|정|캡슐|포|밀리그램|그램)/i;
function isDosageValid(dosage: string) {
  return DOSAGE_RE.test(dosage.trim());
}

type FieldIssue = { field: keyof OcrMedication; message: string };

// [7/9] 신뢰도(review_required)와 무관하게 항상 확인 화면을 거치므로, "어떤 항목이 문제인지"는
// OCR의 overall_confidence가 아니라 실제 필드 값(약품명 매칭 여부·용량 형식·빈 칸)으로 판단한다.
// 초기 로드 시(비동기 검증 전)와 렌더링 시 양쪽에서 같은 기준을 써야 해서 순수 함수로 분리했다.
function computeIssues(m: OcrMedication, drugNameOk: boolean | undefined): FieldIssue[] {
  const issues: FieldIssue[] = [];
  if (drugNameOk === false) {
    issues.push({ field: "drug_name", message: "약품명이 올바르지 않아요. 처방전의 철자를 다시 확인해주세요." });
  } else if (!m.drug_name.trim()) {
    issues.push({ field: "drug_name", message: "약품명이 비어있어요. 입력해주세요." });
  }
  if (m.dosage.trim() && !isDosageValid(m.dosage)) {
    issues.push({ field: "dosage", message: "용량 형식이 잘못됐어요 (예: 500mg처럼 단위를 함께 입력)." });
  } else if (!m.dosage.trim()) {
    issues.push({ field: "dosage", message: "용량이 비어있어요. 입력해주세요." });
  }
  (["frequency", "diagnosis", "drug_class"] as const).forEach((f) => {
    if (!m[f].trim()) {
      issues.push({ field: f, message: `${FIELDS.find((x) => x.key === f)?.label}이 비어있어요. 입력해주세요.` });
    }
  });
  return issues;
}

// 실제 백엔드 응답에는 어떤 단계가 지났는지 알려주는 값이 없어서(동기 호출 한 번으로 끝남),
// 사용자에게 진행 중임을 보여주기 위한 연출용 진행률입니다. 실제 완료 시 바로 100%로 점프합니다.
const FAKE_PROGRESS_STEPS = [22, 48, 72, 90];
const LOADING_STAGES = [
  { label: "처방전 내용 확인", threshold: 25 },
  { label: "약물 정보 검색 중", threshold: 55 },
  { label: "맞춤 가이드 생성 중", threshold: 85 },
  { label: "최종 검토 완료", threshold: 100 },
];

export default function PrescriptionReview() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [record, setRecord] = useState<RecordResult | null>(null);
  const [edited, setEdited] = useState<Record<number, OcrMedication>>({});
  const [confirmed, setConfirmed] = useState<Set<number>>(new Set());
  // 약품명이 실제 존재하는 약인지(e약은요/HIRA 매칭) — key: 항목 id, undefined면 아직 조회 전
  const [drugNameOk, setDrugNameOk] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addingItem, setAddingItem] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const [showFinalModal, setShowFinalModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  // 항목별 입력칸을 감싸는 컨테이너 — blur 시 포커스가 "같은 항목의 다른 칸"으로
  // 이동하는 중인지 판별해서, 그 경우엔 아직 확인 완료 처리하지 않기 위함
  const itemContainerRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(async (data) => {
        setRecord(data);
        const initial: Record<number, OcrMedication> = {};
        data.medications.forEach((m) => (initial[m.id] = { ...m }));
        setEdited(initial);

        // [7/9] 신뢰도와 무관하게 항상 모든 항목의 약품명을 검증한다 (예전엔 review_required
        // 항목만 검증했음 — 그래서 신뢰도가 높으면 오타가 있어도 그냥 넘어갔었다).
        const nameOkEntries = await Promise.all(
          data.medications.map(async (m) => {
            try {
              const info = await getDrugIndication(m.drug_name);
              return [m.id, info.matched_name !== null] as const;
            } catch {
              return [m.id, true] as const; // 조회 실패(네트워크 등)는 오류로 단정하지 않음
            }
          })
        );
        const nameOkMap: Record<number, boolean> = {};
        nameOkEntries.forEach(([id, ok]) => { nameOkMap[id] = ok; });
        setDrugNameOk(nameOkMap);

        // 문제 없는 항목은 바로 "확인 완료"(초록)로 시작 — 사용자가 다시 볼 필요 없게.
        const doneIds = data.medications
          .filter((m) => computeIssues(m, nameOkMap[m.id]).length === 0)
          .map((m) => m.id);
        setConfirmed(new Set(doneIds));
      })
      .catch(() => setError("처방전 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  const update = (id: number, field: keyof OcrMedication, value: string) => {
    setEdited((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  };

  const fieldIssues = (item: OcrMedication): FieldIssue[] =>
    computeIssues(edited[item.id] ?? item, drugNameOk[item.id]);

  // 항목의 모든 칸을 채운 채로 "그 항목을 완전히 벗어나면"(blur) 자동으로 "확인 완료" 처리합니다.
  // 약품명은 다시 입력했으면 e약은요/HIRA 재조회로 실제 존재하는 약인지 확인하고,
  // 용량은 단위 포함 형식인지 확인한 뒤에야 완료 처리합니다.
  // [수정] relatedTarget(다음에 포커스를 받을 요소)이 같은 항목 컨테이너 안에 있으면
  // — 즉 사용자가 같은 항목의 다음 칸으로 탭/클릭 이동 중이면 — 아직 다 안 봤으니
  // 확인 완료로 잠그지 않고 계속 입력 가능한 상태로 둔다.
  const handleBlur = async (id: number, field: keyof OcrMedication, relatedTarget: EventTarget | null) => {
    const m = edited[id];
    if (!m) return;

    let nameOk = drugNameOk[id];
    if (field === "drug_name") {
      try {
        const info = await getDrugIndication(m.drug_name);
        nameOk = info.matched_name !== null;
        setDrugNameOk((prev) => ({ ...prev, [id]: nameOk as boolean }));
      } catch {
        // 조회 실패(네트워크 등) 시엔 기존 상태를 유지 — 오류로 단정하지 않음
      }
    }

    const container = itemContainerRefs.current[id];
    if (relatedTarget instanceof Node && container?.contains(relatedTarget)) return;

    const current = edited[id];
    if (computeIssues(current, nameOk).length === 0) {
      setConfirmed((prev) => new Set([...prev, id]));
    }
  };

  const startReEdit = (id: number) => {
    setConfirmed((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const addItem = async () => {
    if (!record || addingItem) return;
    setAddingItem(true);
    try {
      const updated = await addMedicationItem(record.record_id);
      setRecord(updated);
      const next: Record<number, OcrMedication> = { ...edited };
      updated.medications.forEach((m) => {
        if (!(m.id in next)) next[m.id] = { ...m };
      });
      setEdited(next);
    } catch {
      setError("약물을 추가하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setAddingItem(false);
    }
  };

  const removeItem = async (id: number) => {
    if (!record || removingId !== null) return;
    setRemovingId(id);
    try {
      const updated = await removeMedicationItem(record.record_id, id);
      setRecord(updated);
      setEdited((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setConfirmed((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch {
      setError("약물을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setRemovingId(null);
    }
  };

  // [7/9] review_required(OCR 전체 신뢰도) 기준으로 나누던 걸 없앴다 — 이제 모든 항목을
  // 똑같이 보여주고, 문제 있는지는 항목별로(computeIssues) 판단한다.
  const allItems = record?.medications ?? [];
  const allOk = allItems.length > 0 && allItems.every((m) => confirmed.has(m.id));

  const startGuideGeneration = async () => {
    if (!record) return;
    setShowFinalModal(false);
    setError("");
    setProgress(0);
    setGenerating(true);

    let done = false;
    (async () => {
      for (const step of FAKE_PROGRESS_STEPS) {
        await new Promise((r) => setTimeout(r, 450));
        if (done) return;
        setProgress((p) => Math.max(p, step));
      }
    })();

    try {
      const corrections = allItems.map((m) => {
        const e = edited[m.id];
        return {
          id: m.id,
          drug_name: e.drug_name.trim(),
          dosage: e.dosage.trim(),
          frequency: e.frequency.trim(),
          diagnosis: e.diagnosis.trim(),
          drug_class: e.drug_class.trim(),
        };
      });
      const updated = await confirmMedications(record.record_id, corrections);
      done = true;
      setProgress(100);
      setTimeout(() => navigate(`/records/${updated.record_id}`), 500);
    } catch {
      done = true;
      setGenerating(false);
      setError("확정 처리에 실패했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  // ── 가이드 생성 중 로딩 화면 ──────────────────────────────────────────────
  if (generating) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName="김건강" />
        <div className="flex-1 flex flex-col items-center justify-center px-8">
        <div className="relative mb-8 flex items-center justify-center">
          <div
            style={{
              width: 128,
              height: 128,
              borderRadius: "50%",
              background: `conic-gradient(${C.terracotta} ${progress * 3.6}deg, rgba(193,101,61,0.15) ${progress * 3.6}deg)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.25s",
            }}
          >
            <div
              style={{
                width: 100,
                height: 100,
                borderRadius: "50%",
                background: C.ivory,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center text-[30px]"
                style={{
                  background: `linear-gradient(135deg, ${C.terracotta} 0%, #A5522F 100%)`,
                  boxShadow: "0 6px 20px rgba(193,101,61,0.35)",
                }}
              >
                📋
              </div>
            </div>
          </div>
        </div>
        <h2 className="text-[22px] font-black mb-2 text-center" style={{ color: C.dark }}>
          복약 가이드를 만들고 있어요
        </h2>
        <p className="text-[14px] mb-8 text-center leading-relaxed" style={{ color: C.muted }}>
          처방전 정보를 분석하고
          <br />
          맞춤 복약 가이드를 생성 중이에요
        </p>
        <div className="w-72 mb-6">
          <div className="h-2.5 rounded-full overflow-hidden mb-2" style={{ background: "rgba(30,26,23,0.10)" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${progress}%`,
                background: `linear-gradient(90deg, ${C.terracotta}, ${C.terracottaLight})`,
                transitionDuration: "250ms",
              }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[12px]" style={{ color: C.muted }}>분석중...</span>
            <span className="text-[14px] font-black" style={{ color: C.terracotta }}>{progress}%</span>
          </div>
        </div>
        <div className="space-y-2.5">
          {LOADING_STAGES.map(({ label, threshold }) => {
            const stepDone = progress >= threshold;
            const active = !stepDone && progress >= threshold - 30;
            return (
              <div key={label} className="flex items-center gap-3">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all"
                  style={{ background: stepDone ? C.success : active ? `${C.terracotta}20` : "rgba(30,26,23,0.08)" }}
                >
                  {stepDone ? (
                    <Check className="w-3.5 h-3.5 text-white" />
                  ) : active ? (
                    <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.terracotta }} />
                  ) : null}
                </div>
                <span className="text-[14px]" style={{ color: stepDone ? C.dark : C.muted, fontWeight: stepDone ? 700 : 400 }}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : !record ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
        ) : record.status !== "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[14px]" style={{ color: C.muted }}>이미 확인이 끝난 처방전이에요.</p>
            <button
              onClick={() => navigate(`/records/${record.record_id}`)}
              className="mt-4 px-6 py-3 rounded-full font-bold text-[14px] text-white"
              style={{ background: C.terracotta }}
            >
              결과 보러 가기
            </button>
          </div>
        ) : (
          <>
            <p className="text-[13px] font-bold mb-1" style={{ color: C.terracottaLight }}>처방전 인식 완료</p>
            <h1 className="text-[26px] font-black mb-2" style={{ color: C.dark }}>처방전 확인 및 수정</h1>
            <p className="text-[14px] mb-6" style={{ color: C.muted }}>
              오류가 있는 항목을 수정하면{" "}
              <span className="font-bold" style={{ color: C.success }}>자동으로 확인 완료</span>가 돼요.
            </p>

            {/* 확인 진행률 */}
            <div
              className="px-5 py-4 rounded-2xl mb-7 transition-all"
              style={{
                background: allOk ? `${C.success}12` : C.white,
                border: allOk ? `2px solid ${C.success}` : "none",
                boxShadow: allOk ? "none" : "0 2px 12px rgba(30,26,23,0.06)",
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] font-bold" style={{ color: C.dark }}>확인 진행률</span>
                <div className="flex items-center gap-1.5">
                  {allOk && <Check className="w-4 h-4" style={{ color: C.success }} />}
                  <span className="text-[14px] font-black" style={{ color: allOk ? C.success : C.terracotta }}>
                    {confirmed.size} / {allItems.length} 완료
                  </span>
                </div>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "rgba(30,26,23,0.08)" }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${allItems.length ? (confirmed.size / allItems.length) * 100 : 0}%`,
                    background: allOk ? C.success : C.terracotta,
                    transitionDuration: "600ms",
                  }}
                />
              </div>
              {allOk && (
                <p className="text-[12px] font-bold mt-1.5" style={{ color: "#4A7A47" }}>
                  모두 완료됐어요! 아래에서 최종 확인 후 가이드를 만들어보세요.
                </p>
              )}
            </div>

            <div className="space-y-5 mb-7">
              {allItems.map((item) => {
                const isDone = confirmed.has(item.id);
                const issues = fieldIssues(item);
                return (
                  <div key={item.id}>
                    <div
                      className="rounded-2xl overflow-hidden transition-all"
                      style={{
                        background: isDone ? `${C.success}0D` : C.white,
                        border: isDone ? `2px solid ${C.success}` : "2px solid #D94F4F",
                        boxShadow: isDone ? "0 4px 20px rgba(143,174,139,0.20)" : "0 4px 24px rgba(30,26,23,0.10)",
                      }}
                    >
                      <div
                        className="flex items-center justify-between px-6 py-3 border-b"
                        style={{
                          borderColor: isDone ? `${C.success}30` : "rgba(217,79,79,0.15)",
                          background: isDone ? `${C.success}18` : "rgba(217,79,79,0.05)",
                        }}
                      >
                        {isDone ? (
                          <span className="px-3 py-1 rounded-full text-[12px] font-bold text-white" style={{ background: C.success }}>
                            ✓ 확인 완료
                          </span>
                        ) : (
                          <span className="px-3 py-1 rounded-full text-[12px] font-black text-white" style={{ background: "#D94F4F" }}>
                            ⚠ 확인 필요
                          </span>
                        )}
                        <div className="flex items-center gap-2">
                          {isDone && (
                            <button
                              onClick={() => startReEdit(item.id)}
                              className="text-[12px] font-bold px-3 py-1.5 rounded-full transition-all hover:opacity-80"
                              style={{ background: "rgba(143,174,139,0.18)", color: "#4A7A47" }}
                            >
                              수정하기
                            </button>
                          )}
                          {(record?.medications.length ?? 0) > 1 && (
                            <button
                              onClick={() => removeItem(item.id)}
                              disabled={removingId === item.id}
                              className="text-[12px] font-bold px-3 py-1.5 rounded-full transition-all hover:opacity-80 disabled:opacity-50"
                              style={{ background: "rgba(217,79,79,0.12)", color: "#D94F4F" }}
                            >
                              {removingId === item.id ? "삭제 중..." : "삭제"}
                            </button>
                          )}
                        </div>
                      </div>

                      {!isDone && (
                        <div
                          className="mx-5 mt-4 px-4 py-3 rounded-xl flex items-start gap-2.5"
                          style={{ background: "rgba(217,79,79,0.06)", border: "1px solid rgba(217,79,79,0.18)" }}
                        >
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "#D94F4F" }} />
                          {issues.length > 0 ? (
                            <div>
                              <p className="text-[12px] font-bold mb-1" style={{ color: "#C13F3F" }}>수정이 필요한 항목</p>
                              <ul className="space-y-0.5">
                                {issues.map((iss) => (
                                  <li key={iss.field} className="text-[12px]" style={{ color: "#C13F3F" }}>
                                    <span className="font-bold">{FIELDS.find((f) => f.key === iss.field)?.label}</span> — {iss.message}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : (
                            <p className="text-[12px]" style={{ color: "#C13F3F" }}>
                              이 항목은 문제없이 인식됐어요. 필요하면 내용을 직접 수정해주세요.
                            </p>
                          )}
                        </div>
                      )}

                      <div
                        ref={(el) => { itemContainerRefs.current[item.id] = el; }}
                        className="p-6 grid grid-cols-2 gap-4"
                      >
                        {FIELDS.map(({ key, label }) => {
                          const hasIssue = !isDone && issues.some((iss) => iss.field === key);
                          return (
                            <div key={key} className={key === "drug_name" ? "col-span-2" : ""}>
                              <label
                                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider mb-1.5"
                                style={{ color: hasIssue ? "#D94F4F" : C.muted }}
                              >
                                {label}
                                {hasIssue && (
                                  <span
                                    className="px-1.5 py-0.5 rounded text-[9px] font-black normal-case tracking-normal"
                                    style={{ background: "#D94F4F", color: C.white }}
                                  >
                                    오류
                                  </span>
                                )}
                              </label>
                              {isDone ? (
                                <p
                                  className="text-[14px] px-4 py-2.5 rounded-xl font-medium"
                                  style={{ color: C.dark, background: `${C.success}12` }}
                                >
                                  {String(edited[item.id]?.[key] ?? "")}
                                </p>
                              ) : (
                                <input
                                  value={String(edited[item.id]?.[key] ?? "")}
                                  onChange={(e) => update(item.id, key, e.target.value)}
                                  onBlur={(e) => handleBlur(item.id, key, e.relatedTarget)}
                                  className="w-full px-4 py-2.5 rounded-xl border text-[14px] outline-none transition-all"
                                  style={{
                                    borderColor: hasIssue ? "#D94F4F" : `${C.terracottaLight}60`,
                                    background: C.white,
                                    color: C.dark,
                                  }}
                                />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {!isDone && (
                      <div
                        className="flex items-center justify-between gap-4 px-5 py-4 rounded-2xl mt-3"
                        style={{ background: "#FBF8F3", border: "1px solid rgba(30,26,23,0.09)" }}
                      >
                        <p className="text-[13px] font-medium" style={{ color: C.dark }}>
                          약품명을 찾기 어려우신가요? AI 챗봇이 도와드릴게요
                        </p>
                        <button
                          onClick={() => navigate("/chat")}
                          className="shrink-0 px-4 py-2.5 rounded-full text-white font-bold text-[13px] hover:opacity-88 transition-all whitespace-nowrap"
                          style={{ background: C.terracotta }}
                        >
                          챗봇에게 물어보기 💬
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}

              <button
                onClick={addItem}
                disabled={addingItem}
                className="w-full py-4 rounded-2xl font-bold text-[14px] border-2 border-dashed transition-all hover:bg-black/[0.02] disabled:opacity-50"
                style={{ borderColor: "rgba(30,26,23,0.18)", color: C.muted }}
              >
                {addingItem ? "추가하는 중..." : "+ 약물 추가"}
              </button>
            </div>

            {!allOk && (
              <div
                className="rounded-xl px-5 py-3 mb-5 flex items-center gap-2.5"
                style={{ background: "rgba(30,26,23,0.04)", border: "1px solid rgba(30,26,23,0.10)" }}
              >
                <AlertCircle className="w-4 h-4 shrink-0" style={{ color: C.muted }} />
                <p className="text-[13px]" style={{ color: C.muted }}>오류 항목을 수정하면 자동으로 확인 완료 처리돼요.</p>
              </div>
            )}

            {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

            <button
              disabled={!allOk}
              onClick={() => allOk && setShowFinalModal(true)}
              className="w-full py-5 rounded-full text-white text-[16px] font-black transition-all"
              style={{
                background: allOk ? C.terracotta : "#C8BFB8",
                cursor: allOk ? "pointer" : "not-allowed",
                boxShadow: allOk ? "0 8px 24px rgba(193,101,61,0.30)" : "none",
              }}
            >
              {allOk ? "✓ 확인 완료 · 복약 가이드 만들기" : "확인 완료하고 가이드 만들기"}
            </button>
            <p className="text-center text-[12px] mt-4" style={{ color: C.muted }}>
              본 정보는 의료진의 진단·처방을 대체하지 않습니다
            </p>
          </>
        )}
      </main>

      {showFinalModal && record && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: "rgba(30,26,23,0.55)" }}
          onClick={() => setShowFinalModal(false)}
        >
          <div className="rounded-3xl p-8 w-full max-w-md" style={{ background: C.white }} onClick={(e) => e.stopPropagation()}>
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 text-[28px]"
              style={{ background: `${C.success}15` }}
            >
              ✅
            </div>
            <h3 className="text-[20px] font-black text-center mb-2" style={{ color: C.dark }}>한 번 더 확인해주세요</h3>
            <p className="text-[14px] text-center mb-6" style={{ color: C.muted }}>
              아래 내용으로 복약 가이드를 만들게 돼요. 맞으면 "가이드 만들기"를 눌러주세요.
            </p>
            <div className="rounded-2xl p-4 mb-6 space-y-2" style={{ background: C.ivory }}>
              {allItems.map((m) => {
                const e = edited[m.id] ?? m;
                return (
                  <div key={m.id} className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: C.success }} />
                    <div>
                      <span className="text-[14px] font-bold" style={{ color: C.dark }}>{e.drug_name}</span>
                      <span className="text-[13px] ml-2" style={{ color: C.muted }}>{e.dosage} · {e.diagnosis}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowFinalModal(false)}
                className="flex-1 py-3.5 rounded-full font-bold border-2 text-[15px]"
                style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
              >
                다시 확인
              </button>
              <button
                onClick={startGuideGeneration}
                className="flex-[1.5] py-3.5 rounded-full text-white font-black text-[15px] hover:opacity-88 transition-all"
                style={{ background: C.terracotta, boxShadow: "0 4px 16px rgba(193,101,61,0.30)" }}
              >
                가이드 만들기 →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
