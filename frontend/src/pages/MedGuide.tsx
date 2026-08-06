import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  Dumbbell,
  Eye,
  Leaf,
  MessageCircle,
  Pill,
  Pin,
  TriangleAlert,
  Utensils,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import PrescriptionImageViewer from "../components/PrescriptionImageViewer";
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
import { getCurrentCaregiverId, getCurrentUserName, isLoggedIn } from "../lib/session";
import { FIELDS } from "../lib/prescriptionFields";

// [2026-07-25 추가] caregiver_review_status 뱃지 표시.
// [2026-07-30 수정] needs_correction은 "환자가 아직 안 고침"(보호자 요청, 응답 대기) 상태다 —
// correction_completed(환자가 다 고침, 재검토 대기)와 구분해야 아래 검토하기 버튼을
// 환자가 실제로 고치기 전에 잘못 보여주지 않는다.
const REVIEW_STATUS_LABEL: Record<string, { text: string; bg: string; color: string }> = {
  pending: { text: "검토 대기", bg: `${C.terracotta}15`, color: C.terracotta },
  needs_correction: { text: "환자 수정 대기 중", bg: "#F5E6C8", color: "#8A6D1F" },
  correction_completed: { text: "환자 수정 완료", bg: `${C.terracotta}15`, color: C.terracotta },
  reviewed: { text: "검토 완료", bg: `${C.success}20`, color: "#4A7A47" },
};

// ponytail: Figma 원본은 병명 백과사전·시간대별 복약 일정 탭도 있었지만, 백엔드가
// 그런 데이터(질병 설명 DB, 복용 시간 슬롯)를 안 주기 때문에 실제로 있는 필드
// (medication_guide/lifestyle_guide/source_refs)로만 탭을 구성했습니다.
// [2026-07-23 수정] "주의사항" 탭 삭제 — 약물별 주의사항은 복약 지도 탭에서 약을 눌러
// 들어가는 DrugDetail.tsx에 이미 있어 중복이었다. 생활습관 관련 경고는 "생활습관" 탭의
// 비권장(avoid) 항목으로 흡수됐다.
const TABS = ["복약 지도", "생활습관"] as const;

// [2026-07-25 추가] 정답 입력칸의 예시 — 칸마다 단위가 달라서 하나의 예시("예: 2정")로는
// 진단명·약효분류 같은 텍스트 칸에서 오해를 줄 수 있다.
const SUGGESTED_VALUE_EXAMPLE: Partial<Record<(typeof FIELDS)[number]["key"], string>> = {
  dosage: "예: 2정",
  dose_amount: "예: 5mg",
  frequency: "예: 2회",
  total_days: "예: 30일",
  diagnosis: "예: 제2형 당뇨병",
  drug_class: "예: 스타틴계",
};

function isCategoryEmpty(category: LifestyleCategory): boolean {
  return category.recommended.length === 0 && category.avoid.length === 0;
}

function LifestyleCategorySection({ icon: Icon, label, category }: { icon: LucideIcon; label: string; category: LifestyleCategory }) {
  if (isCategoryEmpty(category)) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="flex items-center gap-1.5 text-[13px] font-black mb-1.5" style={{ color: C.dark }}>
        <Icon className="w-[15px] h-[15px]" style={{ color: C.terracotta }} strokeWidth={2.2} /> {label}
      </p>
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
  const [reviewing, setReviewing] = useState(false);
  // key: `${ocr_result_id}:${field_name}`, value: 사유+정답(선택된 칸만 존재)
  // [2026-07-25 추가] suggestedValue — 환자가 자유 입력 대신 이 값만 드롭다운에서
  // 고르게 하려면 보호자·기관이 정답을 미리 지정해둬야 한다.
  const [selectedFlags, setSelectedFlags] = useState<Record<string, { reason: string; suggestedValue: string }>>({});
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  // [2026-07-25 추가] 제출 실패(빈 칸/네트워크 오류)를 팝업으로 알린다 — 입력한 내용은
  // selectedFlags에 그대로 남아있어서 팝업을 닫고 이어서 작성할 수 있다(처음부터 다시 X).
  const [flagError, setFlagError] = useState("");

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
      if (checked) next[key] = { reason: "", suggestedValue: "" };
      else delete next[key];
      return next;
    });
  };

  const handleSubmitFlags = async () => {
    if (!result) return;
    // [2026-07-25 수정] 이유는 선택 — 정답(suggestedValue)만 필수. 비어있으면 팝업으로
    // 알리고 selectedFlags는 그대로 둬서 이어서 채울 수 있게 한다.
    const entries = Object.entries(selectedFlags);
    if (entries.length === 0 || entries.some(([, v]) => !v.suggestedValue.trim())) {
      setFlagError("정답을 입력하지 않은 칸이 있어요. 마저 입력해주세요.");
      return;
    }
    const flags: FieldFlagRequest[] = entries.map(([key, v]) => {
      const [medId, fieldName] = key.split(":");
      return {
        ocr_result_id: Number(medId),
        field_name: fieldName,
        reason: v.reason.trim(),
        suggested_value: v.suggestedValue.trim(),
      };
    });
    setReviewSubmitting(true);
    try {
      setResult(await requestCorrection(result.record_id, flags));
      setReviewing(false);
      setSelectedFlags({});
      setError("");
    } catch {
      setFlagError("수정 요청을 보내지 못했어요. 잠시 후 다시 시도해 주세요.");
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
        <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
        <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
          <Skeleton className="h-3 w-24 mb-2" />
          <Skeleton className="h-7 w-40 mb-6" />
          <div className="flex gap-2 mb-6">
            <Skeleton className="h-10 w-24 rounded-full" />
            <Skeleton className="h-10 w-24 rounded-full" />
          </div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        </main>
      </div>
    );
  }

  if (error || !result?.guide) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
        <div className="rounded-2xl p-10 m-8 text-center" style={{ background: C.surface }}>
          <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "가이드를 찾을 수 없어요."}</p>
        </div>
      </div>
    );
  }

  const { guide } = result;

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate(`/records/${result.record_id}`)}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 처방 상세로
        </button>

        <div className="flex items-center justify-between gap-3 mb-1">
          <p className="text-[13px] font-bold" style={{ color: C.terracotta }}>{guide.lifestyle_guide.diagnosis}</p>
          {result.has_image && <PrescriptionImageViewer recordId={result.record_id} />}
        </div>
        <h1 className="text-[24px] font-black mb-6" style={{ color: C.dark }}>복약 가이드</h1>

        {/* [2026-07-25 추가] 환자가 등록한 처방전을 연결된 보호자·기관이 한 번은 확인하게
            하는 검토 흐름 — OCR 인식 오류 여부와 무관하게 항상 대상이 된다(caregiver_review_status
            가 "none"이면 연결된 보호자·기관이 없다는 뜻이라 아예 안 보여준다). */}
        {isCaregiver && result.caregiver_review_status !== "none" && (
          <div className="rounded-2xl p-5 mb-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
            <div className="flex items-center justify-between gap-3 mb-1">
              <p className="flex items-center gap-1.5 text-[14px] font-black" style={{ color: C.dark }}>
                <Eye className="w-4 h-4" style={{ color: C.terracotta }} strokeWidth={2.2} /> 보호자·기관 검토
              </p>
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
            ) : result.caregiver_review_status === "needs_correction" ? (
              // [2026-07-30 추가] 보호자·기관이 방금 수정을 요청한 직후 — 환자가 아직 안 고쳤으니
              // 검토하기 버튼을 눌러도 볼 게 없다. 환자가 다 고치면 correction_completed로 바뀌면서
              // 아래 분기(검토하기 버튼)로 넘어간다.
              <p className="text-[13px] mt-1" style={{ color: C.muted }}>
                환자가 아직 수정하지 않았어요. 환자가 수정을 완료하면 검토할 수 있어요.
              </p>
            ) : !reviewing ? (
              <>
                <p className="text-[13px] mt-1 mb-3" style={{ color: C.muted }}>
                  {result.caregiver_review_status === "correction_completed"
                    ? "환자가 수정을 완료했어요. 검토하기를 눌러 칸별로 확인해 주세요."
                    : "검토하기를 눌러 환자가 확인한 처방전 내용을 그대로 확인해 주세요."}
                </p>
                <button
                  onClick={() => setReviewing(true)}
                  disabled={reviewSubmitting}
                  className="w-full py-2.5 rounded-full font-bold text-[13px] text-white disabled:opacity-50"
                  style={{ background: C.terracotta }}
                >
                  검토하기
                </button>
              </>
            ) : (
              <div className="mt-2">
                {/* [2026-07-27 추가] 칸별로 검토하는 동안 원본 사진을 참고할 수 있게 — 환자가
                    처방전을 확인·수정할 때와 동일하게 챗봇 버튼 위에 뜨는 작은 팝업. */}
                {result.has_image && <PrescriptionImageViewer recordId={result.record_id} floating />}
                <p className="text-[13px] mb-3" style={{ color: C.muted }}>
                  {/* [2026-07-27 수정] 이유는 선택이라는 안내는 실제로 칸을 지목할 때만 의미가
                      있어서, 지목 안 하고 그냥 검토만 하는 경우까지 아우르는 문구로 바꿨다. */}
                  문제가 있는 칸을 고르면 정답을 입력할 수 있어요. 문제가 없으면 아래 검토했어요를 눌러주세요.
                </p>
                {/* [2026-07-25 수정] 환자가 처방전을 확인·수정할 때 보는 것과 같은 칸 구조
                    (레이블 박스 그리드)로 보여준다 — 체크한 칸만 빨간 테두리로 표시. */}
                <div className="space-y-4">
                  {result.medications.map((m) => (
                    <div key={m.id} className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="px-6 py-4" style={{ background: C.surface }}>
                        <p className="flex items-center gap-1.5 font-black text-[15px]" style={{ color: C.dark }}>
                          <Pill className="w-4 h-4" style={{ color: C.terracotta }} strokeWidth={2.2} /> {m.drug_name}
                        </p>
                      </div>
                      <div className="p-6 grid grid-cols-2 gap-4">
                        {FIELDS.filter(({ key }) => key !== "drug_name").map(({ key, label }) => {
                          const flagKey = `${m.id}:${key}`;
                          const checked = flagKey in selectedFlags;
                          return (
                            <div key={key}>
                              <label
                                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider mb-1.5 cursor-pointer"
                                style={{ color: checked ? "#D94F4F" : C.muted }}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={(e) => toggleFlag(m.id, key, e.target.checked)}
                                  className="w-3.5 h-3.5 accent-current"
                                />
                                {label}
                              </label>
                              <p
                                className="text-[14px] px-4 py-2.5 rounded-xl font-medium"
                                style={{
                                  color: C.dark,
                                  background: checked ? "rgba(217,79,79,0.06)" : "rgba(30,26,23,0.04)",
                                  border: checked ? "2px solid #D94F4F" : "2px solid transparent",
                                }}
                              >
                                {String(m[key]) || "-"}
                              </p>
                              {checked && (
                                <div className="mt-1.5 space-y-1.5">
                                  <input
                                    value={selectedFlags[flagKey].reason}
                                    onChange={(e) =>
                                      setSelectedFlags((prev) => ({ ...prev, [flagKey]: { ...prev[flagKey], reason: e.target.value } }))
                                    }
                                    placeholder="이유 (선택) — 예: 1정이 아니라 2정이에요"
                                    className="w-full px-3 py-2 rounded-lg border text-[13px] outline-none"
                                    style={{ borderColor: `${C.terracottaLight}60` }}
                                  />
                                  {/* [2026-07-25 추가] 정답 — 환자는 이 값을 드롭다운에서 선택만 하게 되므로
                                      여기서 정확한 값을 입력해둬야 한다. 칸마다 단위가 달라서 예시도 칸별로. */}
                                  <input
                                    value={selectedFlags[flagKey].suggestedValue}
                                    onChange={(e) =>
                                      setSelectedFlags((prev) => ({ ...prev, [flagKey]: { ...prev[flagKey], suggestedValue: e.target.value } }))
                                    }
                                    placeholder={SUGGESTED_VALUE_EXAMPLE[key] ?? "정답을 입력해주세요"}
                                    className="w-full px-3 py-2 rounded-lg border text-[13px] outline-none font-bold"
                                    style={{ borderColor: C.terracotta, color: C.terracotta }}
                                  />
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                {/* [2026-07-27 수정] "수정이 필요해요"를 상단이 아니라 여기(칸별 검토를 마친
                    뒤)로 옮겼다 — 보호자·기관이 내용을 실제로 보지도 않고 바로 판단을 눌러버리는
                    걸 막기 위함. 검토했어요는 지목한 칸이 없어도 항상 누를 수 있고, 수정이
                    필요해요는 최소 1칸을 지목해야 활성화된다(정답까지 채워야 실제 제출됨). */}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={handleMarkReviewed}
                    disabled={reviewSubmitting}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] text-white disabled:opacity-50"
                    style={{ background: C.success }}
                  >
                    ✓ 검토했어요
                  </button>
                  <button
                    onClick={handleSubmitFlags}
                    disabled={reviewSubmitting || Object.keys(selectedFlags).length === 0}
                    className="flex-1 py-2.5 rounded-full font-bold text-[13px] text-white disabled:opacity-50"
                    style={{ background: C.terracotta }}
                  >
                    수정이 필요해요
                  </button>
                </div>
              </div>
            )}

            {/* [2026-07-25 추가] 빈 칸/전송 실패는 팝업으로 알린다 — selectedFlags는 그대로
                남아있어서 닫고 이어서 작성할 수 있다. */}
            {flagError && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center px-4"
                style={{ background: "rgba(30,26,23,0.55)" }}
                onClick={() => setFlagError("")}
              >
                <div className="rounded-3xl p-6 w-full max-w-sm" onClick={(e) => e.stopPropagation()} style={{ background: C.surface }}>
                  <p className="text-[15px] font-black mb-2" style={{ color: C.dark }}>다시 확인해주세요</p>
                  <p className="text-[13px] mb-5" style={{ color: C.muted }}>{flagError}</p>
                  <button
                    onClick={() => setFlagError("")}
                    className="w-full py-3 rounded-full font-bold text-[14px] text-white"
                    style={{ background: C.terracotta }}
                  >
                    확인
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
            <span className="flex items-center gap-1.5 text-[13px] font-bold" style={{ color: "#8A6D1F" }}>
              <TriangleAlert className="w-4 h-4 shrink-0" style={{ color: "#8A6D1F" }} strokeWidth={2.2} />
              보호자·기관이 수정을 요청했어요 — 확인하고 수정하기
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
                    <p className="flex items-center gap-1.5 text-[15px] font-black" style={{ color: C.dark }}>
                      <Pill className="w-4 h-4" style={{ color: C.terracotta }} strokeWidth={2.2} /> {d.drug_name}
                    </p>
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
                    <p className="flex items-center gap-1.5 text-[15px] font-black mb-3" style={{ color: C.dark }}>
                      <Leaf className="w-4 h-4" style={{ color: C.success }} strokeWidth={2.2} /> {entry.diagnosis || "생활습관 안내"}
                    </p>
                    <LifestyleCategorySection icon={Utensils} label="식사" category={entry.diet} />
                    <LifestyleCategorySection icon={Dumbbell} label="운동" category={entry.exercise} />
                    <LifestyleCategorySection icon={Pin} label="그 외" category={entry.other} />
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
          className="w-full mt-8 py-4 rounded-xl font-bold text-[15px] text-white flex items-center justify-center gap-2"
          style={{ background: C.terracotta }}
        >
          <MessageCircle className="w-[18px] h-[18px]" strokeWidth={2.2} /> 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}
