import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import {
  formatUniqueSourceRefs,
  getRecord,
  markReviewed,
  requestCorrection,
  type FieldFlagRequest,
  type LifestyleCategory,
  type RecordResult,
} from "../api/records";
import { C } from "../theme";
import { getCurrentCaregiverId, getCurrentUserName } from "../lib/session";
import { FIELDS } from "./PrescriptionReview";

// [2026-07-25 추가] caregiver_review_status 뱃지 표시.
const REVIEW_STATUS_LABEL: Record<string, { text: string; bg: string; color: string }> = {
  pending: { text: "검토 대기", bg: `${C.terracotta}15`, color: C.terracotta },
  needs_correction: { text: "환자 수정 대기", bg: "#F5E6C8", color: "#8A6D1F" },
  reviewed: { text: "검토 완료", bg: `${C.success}20`, color: "#4A7A47" },
};

// ponytail: Figma 원본은 병명 백과사전·시간대별 복약 일정 탭도 있었지만, 백엔드가
// 그런 데이터(질병 설명 DB, 복용 시간 슬롯)를 안 주기 때문에 실제로 있는 필드
// (medication_guide/lifestyle_guide/source_refs)로만 탭을 구성했습니다.
// [2026-07-23 수정] "주의사항" 탭 삭제 — 약물별 주의사항은 복약 지도 탭에서 약을 눌러
// 들어가는 DrugDetail.tsx에 이미 있어 중복이었다. 생활습관 관련 경고는 "생활습관" 탭의
// 비권장(avoid) 항목으로 흡수됐다.
const TABS = ["복약 지도", "생활습관"] as const;

function isCategoryEmpty(category: LifestyleCategory): boolean {
  return category.recommended.length === 0 && category.avoid.length === 0;
}

function LifestyleCategorySection({ icon, label, category }: { icon: string; label: string; category: LifestyleCategory }) {
  if (isCategoryEmpty(category)) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[13px] font-black mb-1.5" style={{ color: C.dark }}>{icon} {label}</p>
      {category.recommended.length > 0 && (
        <ul className="space-y-1 mb-2">
          {category.recommended.map((item, i) => (
            <li key={`rec-${i}`} className="flex items-start gap-2 text-[14px] leading-relaxed" style={{ color: C.dark }}>
              <span style={{ color: C.success }}>✓</span> {item}
            </li>
          ))}
        </ul>
      )}
      {category.avoid.length > 0 && (
        <ul className="space-y-1">
          {category.avoid.map((item, i) => (
            <li key={`avoid-${i}`} className="flex items-start gap-2 text-[14px] leading-relaxed" style={{ color: C.terracotta }}>
              <span>✕</span> {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MedGuide() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [result, setResult] = useState<RecordResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]>("복약 지도");
  // [2026-07-25 추가] 보호자·기관 검토 흐름 — 환자가 등록한 모든 처방전을 한 번은
  // 확인하게 하기 위함. isCaregiver는 이 화면을 보는 사람이 보호자/기관 계정인지.
  const isCaregiver = getCurrentCaregiverId() != null;
  const [flagging, setFlagging] = useState(false);
  // key: `${ocr_result_id}:${field_name}`, value: 사유 텍스트(선택된 칸만 존재)
  const [selectedFlags, setSelectedFlags] = useState<Record<string, string>>({});
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(setResult)
      .catch(() => setError("복약 가이드를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  const toggleFlag = (medId: number, field: string, checked: boolean) => {
    const key = `${medId}:${field}`;
    setSelectedFlags((prev) => {
      const next = { ...prev };
      if (checked) next[key] = "";
      else delete next[key];
      return next;
    });
  };

  const handleSubmitFlags = async () => {
    if (!result) return;
    const flags: FieldFlagRequest[] = Object.entries(selectedFlags)
      .filter(([, reason]) => reason.trim())
      .map(([key, reason]) => {
        const [medId, fieldName] = key.split(":");
        return { ocr_result_id: Number(medId), field_name: fieldName, reason: reason.trim() };
      });
    if (flags.length === 0) {
      setError("수정이 필요한 칸에 이유를 적어주세요.");
      return;
    }
    setReviewSubmitting(true);
    try {
      setResult(await requestCorrection(result.record_id, flags));
      setFlagging(false);
      setSelectedFlags({});
      setError("");
    } catch {
      setError("수정 요청을 보내지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setReviewSubmitting(false);
    }
  };

  const handleMarkReviewed = async () => {
    if (!result) return;
    setReviewSubmitting(true);
    try {
      setResult(await markReviewed(result.record_id));
    } catch {
      setError("검토 처리에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setReviewSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
      </div>
    );
  }

  if (error || !result?.guide) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <div className="rounded-2xl p-10 m-8 text-center" style={{ background: C.surface }}>
          <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "가이드를 찾을 수 없어요."}</p>
        </div>
      </div>
    );
  }

  const { guide } = result;

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate(`/records/${result.record_id}`)}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 처방 상세로
        </button>

        <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>{guide.lifestyle_guide.diagnosis}</p>
        <h1 className="text-[24px] font-black mb-6" style={{ color: C.dark }}>복약 가이드</h1>

        {/* [2026-07-25 추가] 환자가 등록한 처방전을 연결된 보호자·기관이 한 번은 확인하게
            하는 검토 흐름 — OCR 인식 오류 여부와 무관하게 항상 대상이 된다(caregiver_review_status
            가 "none"이면 연결된 보호자·기관이 없다는 뜻이라 아예 안 보여준다). */}
        {isCaregiver && result.caregiver_review_status !== "none" && (
          <div className="rounded-2xl p-5 mb-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
            <div className="flex items-center justify-between gap-3 mb-1">
              <p className="text-[14px] font-black" style={{ color: C.dark }}>👀 보호자·기관 검토</p>
              <span
                className="px-2.5 py-1 rounded-full text-[11px] font-bold"
                style={{
                  background: REVIEW_STATUS_LABEL[result.caregiver_review_status].bg,
                  color: REVIEW_STATUS_LABEL[result.caregiver_review_status].color,
                }}
              >
                {REVIEW_STATUS_LABEL[result.caregiver_review_status].text}
              </span>
            </div>

            {error && <p className="text-[13px] mt-2" style={{ color: "#D94F4F" }}>{error}</p>}

            {result.caregiver_review_status === "reviewed" ? (
              <p className="text-[13px] mt-1" style={{ color: C.muted }}>검토를 완료했어요.</p>
            ) : !flagging ? (
              <>
                <p className="text-[13px] mt-1 mb-3" style={{ color: C.muted }}>
                  {result.caregiver_review_status === "needs_correction"
                    ? "환자에게 수정을 요청했어요. 아래에서 수정 완료된 칸을 확인하고 최종 검토해 주세요."
                    : "내용을 확인하고, 문제가 없으면 검토했어요를 눌러주세요."}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={handleMarkReviewed}
                    disabled={reviewSubmitting}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] text-white disabled:opacity-50"
                    style={{ background: C.success }}
                  >
                    ✓ 검토했어요
                  </button>
                  <button
                    onClick={() => setFlagging(true)}
                    disabled={reviewSubmitting}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] border-2 disabled:opacity-50"
                    style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
                  >
                    수정이 필요해요
                  </button>
                </div>
              </>
            ) : (
              <div className="mt-2">
                <p className="text-[13px] mb-3" style={{ color: C.muted }}>
                  문제가 있는 칸을 고르고 이유를 적어주세요. 환자에게 바로 알림이 가요.
                </p>
                <div className="space-y-3">
                  {result.medications.map((m) => (
                    <div key={m.id} className="rounded-xl p-4" style={{ background: C.white }}>
                      <p className="text-[14px] font-bold mb-2" style={{ color: C.dark }}>{m.drug_name}</p>
                      <div className="space-y-2">
                        {FIELDS.filter(({ key }) => key !== "drug_name").map(({ key, label }) => {
                          const flagKey = `${m.id}:${key}`;
                          const checked = flagKey in selectedFlags;
                          return (
                            <div key={key}>
                              <label className="flex items-center gap-2 text-[13px]" style={{ color: C.dark }}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={(e) => toggleFlag(m.id, key, e.target.checked)}
                                  className="w-4 h-4 accent-current"
                                />
                                {label}
                                <span style={{ color: C.muted }}>({String(m[key]) || "빈 값"})</span>
                              </label>
                              {checked && (
                                <input
                                  value={selectedFlags[flagKey]}
                                  onChange={(e) =>
                                    setSelectedFlags((prev) => ({ ...prev, [flagKey]: e.target.value }))
                                  }
                                  placeholder="이유를 적어주세요 (예: 1정이 아니라 2정이에요)"
                                  className="w-full mt-1.5 px-3 py-2 rounded-lg border text-[13px] outline-none"
                                  style={{ borderColor: `${C.terracottaLight}60` }}
                                />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => {
                      setFlagging(false);
                      setSelectedFlags({});
                      setError("");
                    }}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] border-2"
                    style={{ borderColor: "rgba(30,26,23,0.15)", color: C.muted }}
                  >
                    취소
                  </button>
                  <button
                    onClick={handleSubmitFlags}
                    disabled={reviewSubmitting || Object.keys(selectedFlags).length === 0}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] text-white disabled:opacity-50"
                    style={{ background: C.terracotta }}
                  >
                    수정 요청 보내기
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {!isCaregiver && result.caregiver_review_status === "needs_correction" && (
          <button
            onClick={() => navigate(`/records/${result.record_id}/review?mode=correction`)}
            className="w-full text-left rounded-2xl p-4 mb-6 flex items-center justify-between gap-3"
            style={{ background: "#FFF4E0", border: "1px solid #F0D9A8" }}
          >
            <span className="text-[13px] font-bold" style={{ color: "#8A6D1F" }}>
              ⚠️ 보호자·기관이 수정을 요청했어요 — 확인하고 수정하기
            </span>
            <ChevronRight className="w-4 h-4 shrink-0" style={{ color: "#8A6D1F" }} />
          </button>
        )}

        <div className="flex gap-2 mb-6 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-5 py-2.5 rounded-full text-[14px] font-bold transition-all"
              style={{
                background: tab === t ? C.terracotta : C.white,
                color: tab === t ? C.white : C.muted,
                boxShadow: tab === t ? "none" : "0 2px 8px rgba(30,26,23,0.06)",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "복약 지도" && (
          <div className="space-y-3">
            {guide.medication_guide.drugs.map((d, i) => {
              const med = result.medications.find((m) => m.drug_name === d.drug_name);
              // [7/9] dosage_text(stub) / medication_guide(실제) 중 있는 걸 씀
              const guideText = d.medication_guide ?? d.dosage_text ?? "";
              const content = (
                <>
                  <div className="flex items-center justify-between gap-3 mb-1.5">
                    <p className="text-[15px] font-black" style={{ color: C.dark }}>💊 {d.drug_name}</p>
                    <div className="flex items-center gap-2 shrink-0">
                      {med?.drug_class && (
                        <span
                          className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                          style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                        >
                          {med.drug_class}
                        </span>
                      )}
                      {med && <ChevronRight className="w-4 h-4" style={{ color: C.muted }} />}
                    </div>
                  </div>
                  {med?.frequency && (
                    <p className="text-[12px] mb-2" style={{ color: C.muted }}>{med.frequency}</p>
                  )}
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{guideText}</p>
                </>
              );
              return med ? (
                <button
                  key={i}
                  onClick={() => navigate(`/records/${result.record_id}/drugs/${med.id}`)}
                  className="w-full text-left rounded-2xl p-5 transition-all hover:shadow-md"
                  style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}
                >
                  {content}
                </button>
              ) : (
                <div key={i} className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  {content}
                </div>
              );
            })}
          </div>
        )}

        {tab === "생활습관" && (
          <div className="space-y-4">
            {guide.lifestyle_guide.guides.length > 0 ? (
              guide.lifestyle_guide.guides.map((entry, i) => {
                const isEmpty =
                  isCategoryEmpty(entry.diet) && isCategoryEmpty(entry.exercise) && isCategoryEmpty(entry.other);
                return (
                  <div key={i} className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                    <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>🌿 {entry.diagnosis || "생활습관 안내"}</p>
                    <LifestyleCategorySection icon="🥗" label="식사" category={entry.diet} />
                    <LifestyleCategorySection icon="🏃" label="운동" category={entry.exercise} />
                    <LifestyleCategorySection icon="📌" label="그 외" category={entry.other} />
                    {isEmpty && (
                      <p className="text-[14px]" style={{ color: C.muted }}>안내할 내용이 없어요.</p>
                    )}
                  </div>
                );
              })
            ) : (
              <p className="text-[14px]" style={{ color: C.muted }}>생활습관 안내가 아직 없어요.</p>
            )}
          </div>
        )}

        {guide.source_refs.length > 0 && (() => {
          const uniqueRefs = formatUniqueSourceRefs(guide.source_refs);
          return (
            <p className="text-[12px] mt-6" style={{ color: C.muted }}>
              출처:{" "}
              {uniqueRefs.map((s, i) => (
                <span key={i}>
                  {/* [7/9] url(stub)이 있을 때만 링크로, 실제 파이프라인 인용(url 없음)은 텍스트로만 표시 */}
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline" style={{ color: C.muted }}>
                      {s.text}
                    </a>
                  ) : (
                    s.text
                  )}
                  {i < uniqueRefs.length - 1 && ", "}
                </span>
              ))}
            </p>
          );
        })()}

        <button
          onClick={() => navigate("/chat", { state: { diagnosis: guide.lifestyle_guide.diagnosis } })}
          className="w-full mt-8 py-4 rounded-xl font-bold text-[15px] text-white"
          style={{ background: C.terracotta }}
        >
          💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}
