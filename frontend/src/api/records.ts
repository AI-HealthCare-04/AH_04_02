import { dedupeInFlight } from "../lib/dedupeInFlight";
import { monitoringClient } from "./monitoringClient";

// ── 타입 정의 (records_router.py 응답 형태 그대로) ──

// [2026-07-25 추가] 보호자·기관이 "수정이 필요해요"로 지목한 칸 — PrescriptionReview.tsx의
// correction 모드가 이 목록으로 잠금(field_flags에 없는 칸)/빨간테두리(corrected=false)/
// 초록 완료(corrected=true)를 그린다.
export interface FieldFlag {
  id: number;
  field_name: string;
  reason: string;
  // [2026-07-25 추가] 보호자·기관이 지정한 정답 — 환자는 이 값을 드롭다운에서
  // 선택·확인만 한다(자유 입력 불가).
  suggested_value: string;
  corrected: boolean;
}

export interface OcrMedication {
  id: number;
  drug_name: string;
  dosage: string; // 1회 사용량 — 예: "1정", "2캡슐" (개수 단위)
  dose_amount: string; // [2026-07-25 추가] 1회 투여량 — 예: "5mg", "10ml" (질량·부피 단위)
  frequency: string;
  total_days: string;
  diagnosis: string;
  drug_class: string;
  confidence: number;
  review_required: boolean;
  field_flags: FieldFlag[];
}

/**
 * [7/9] RAG_PROVIDER=stub(기본값)과 RAG_PROVIDER=real이 서로 다른 모양을 반환한다.
 * 두 모드를 전환하며 테스트해야 하는 과도기라 필드를 전부 optional로 두고,
 * Result.tsx/MedGuide.tsx에서 어느 필드가 있는지 보고 어느 모드인지
 * 판단해서 렌더링한다. (실제 응답 샘플: docs/rag-real-response-sample.md)
 */
export interface GuideDrug {
  drug_name: string;
  // stub 모양
  dosage_text?: string;
  caution?: string;
  // 실제 파이프라인 모양
  medication_guide?: string;
  precautions?: string[];
  review_required?: boolean;
  review_reason?: string; // [2026-07-20 추가] 가이드 생성 실패 시 원인 문구(review_flags만으론 원인을 알 수 없었음)
  review_flags?: string[];
}

/** [2026-07-23 추가] 생활습관 안내 한 카테고리(식사/운동/그 외)의 권장·비권장 항목 목록. */
export interface LifestyleCategory {
  recommended: string[];
  avoid: string[];
}

/** [2026-07-21 회의 반영] 진단명 기준 생활습관 안내 1건 — 여러 약이 같은 진단명을 공유해도
 * 한 번만 생성된다(생활습관 안내는 의약품별이 아니라 진단명별이어야 한다는 결정 반영).
 * [2026-07-23 수정] 자유 텍스트 한 단락(guide: str) 대신 식사(diet)/운동(exercise)/
 * 그 외(other) × 권장(recommended)/비권장(avoid)으로 구조화됐다. */
export interface LifestyleGuideEntry {
  diagnosis: string; // 진단명 미상이면 빈 문자열(안전한 일반 안내로 대체된 상태)
  diet: LifestyleCategory;
  exercise: LifestyleCategory;
  other: LifestyleCategory;
  review_required?: boolean;
  review_reason?: string;
}

export interface LifestyleGuide {
  diagnosis: string; // 대표 진단명(헤드라인 표시용) — guides[0].diagnosis와 대체로 동일
  guides: LifestyleGuideEntry[]; // 진단명별 생활습관 안내 목록(약 개수가 아니라 고유 진단명 개수만큼)
}

export interface SourceRef {
  drug_name?: string;
  // stub 모양
  title?: string;
  url?: string;
  // 실제 파이프라인 — 의약품 인용(e약은요 + HIRA 약가마스터)
  item_name?: string;
  field?: string;
  hira_standard_code?: string;
  hira_atc_code?: string;
  hira_permit_date?: string;
  hira_active?: boolean;
  // 실제 파이프라인 — 의약품 인용(식약처 의약품제품허가정보, 2026-07-14 추가)
  // hira_active(약가 등재 상태)와는 다른 개념 — 이건 제조·판매 허가 자체의 취소여부다.
  permit_kind_code?: string;
  permit_active?: boolean;
  // 실제 파이프라인 — 생활지침 인용(2026-07-21부터 특정 약이 아니라 진단명 기준)
  diagnosis?: string;
  disease?: string;
  category?: string;
  source?: string;
  // 실제 파이프라인 — DUR 병용금기 경고 (같은 처방전의 다른 약과 금기 관계일 때만 존재)
  mixture_item_name?: string;
  prohbt_content?: string;
  // 실제 파이프라인 — DUR 노인주의/연령금기/임부금기 (다른 약과 무관, 이 약 자체의 주의사항)
  dur_category?: string;
  dur_detail?: string;
  dur_extra?: string;
}

/** source_refs 항목 하나를 사람이 읽을 수 있는 한 줄로 표시 (stub/실제 두 모양 다 처리) */
export function formatSourceRef(ref: SourceRef): string {
  if (ref.title) return ref.title; // stub 모양
  if (ref.mixture_item_name) return `⚠️ ${ref.mixture_item_name}와 병용금기${ref.prohbt_content ? ` (${ref.prohbt_content})` : ""}`;
  if (ref.dur_category) {
    const extra = ref.dur_extra ? ` (${ref.dur_extra})` : "";
    return `⚠️ ${ref.dur_category}${extra}${ref.dur_detail ? `: ${ref.dur_detail}` : ""}`;
  }
  if (ref.item_name) return `${ref.item_name}${ref.field ? ` · ${ref.field}` : ""}`; // 의약품 인용
  if (ref.disease) return ref.source ?? `${ref.disease}${ref.category ? ` · ${ref.category}` : ""}`; // 생활지침 인용 — 실제 출처(학회/기관), 없으면 질환·카테고리로 폴백
  return ref.drug_name ?? "출처 미상";
}

/** source_refs를 표시용 문자열로 변환하되, 같은 출처 텍스트가 반복되면 한 번만 남긴다
 * (여러 약이 같은 학회 지침·같은 DUR 주의를 각자 인용하는 경우가 많음). */
export function formatUniqueSourceRefs(refs: SourceRef[]): { text: string; url?: string }[] {
  const seen = new Set<string>();
  const result: { text: string; url?: string }[] = [];
  for (const ref of refs) {
    const text = formatSourceRef(ref);
    if (seen.has(text)) continue;
    seen.add(text);
    result.push({ text, url: ref.url });
  }
  return result;
}

// [2026-07-25 추가] 보호자·기관 검토 상태 — "none": 연결된 보호자·기관 없음(검토 대상 아님)
// "pending": 검토 대기 / "needs_correction": 보호자·기관이 수정 요청, 환자 응답 대기
// [2026-07-30 추가] "correction_completed": 환자가 지목된 칸을 전부 고쳐서 보호자·기관
// 재검토 대기 — 이 값이 없으면 환자가 다 고쳐도 needs_correction에 계속 머물러 있었다.
// "reviewed": 보호자·기관 최종 확인 완료
export type CaregiverReviewStatus = "none" | "pending" | "needs_correction" | "correction_completed" | "reviewed";

export interface RecordResult {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  failure_reason: string | null;
  created_at: string;
  uploaded_by_name: string | null;
  caregiver_review_status: CaregiverReviewStatus;
  has_image: boolean; // [2026-07-25 추가] 처방전 원본 사진 저장 여부 — GET /records/{id}/image
  medications: OcrMedication[];
  guide: {
    medication_guide: { drugs: GuideDrug[] };
    lifestyle_guide: LifestyleGuide;
    source_refs: SourceRef[];
  } | null;
  // [2026-07-23 추가] confirm 시점에 이미 활성 일정이 있던 약이 있으면 그 이름들 —
  // "오늘의 복약"에 중복 등록하지 않고 건너뛴 약. 없으면 빈 배열.
  duplicate_drug_names: string[];
}

function emptyLifestyleCategory(): LifestyleCategory {
  return { recommended: [], avoid: [] };
}

function isLifestyleCategoryEmpty(category: LifestyleCategory): boolean {
  return category.recommended.length === 0 && category.avoid.length === 0;
}

function normalizeLifestyleCategory(raw: unknown): LifestyleCategory {
  if (!raw || typeof raw !== "object") return emptyLifestyleCategory();
  const obj = raw as Record<string, unknown>;
  const toStrings = (value: unknown): string[] =>
    Array.isArray(value) ? value.map((v) => String(v).trim()).filter(Boolean) : [];
  return { recommended: toStrings(obj.recommended), avoid: toStrings(obj.avoid) };
}

/** [2026-07-23 수정] "guides"는 이제 항목당 diet/exercise/other × recommended/avoid로
 * 구조화됐다. 이 변경 전에 이미 저장된 처방전 기록(guides[].guide 자유 텍스트, 더 옛
 * 문자열 배열, 가장 옛 최상위 diet/exercise 고정 JSON)도 죽지 않고 같은 모양으로
 * 맞춰 반환한다 — backend/routers/chat_router.py의 _summarize_lifestyle_guide와 동일한
 * 하위호환 원칙. */
function normalizeLifestyleGuide(guide: LifestyleGuide): LifestyleGuide {
  const rawGuides = guide.guides as unknown;
  if (!Array.isArray(rawGuides)) {
    const legacy = guide as unknown as {
      diet?: { avoid?: string[] };
      exercise?: { type?: string; duration?: string; intensity?: string };
    };
    if (!legacy.diet && !legacy.exercise) return { ...guide, guides: [] };
    const exercise = emptyLifestyleCategory();
    const exerciseText = [legacy.exercise?.type, legacy.exercise?.duration, legacy.exercise?.intensity]
      .filter(Boolean)
      .join(" · ");
    if (exerciseText) exercise.recommended.push(exerciseText);
    return {
      ...guide,
      guides: [
        {
          diagnosis: guide.diagnosis || "",
          diet: { recommended: [], avoid: legacy.diet?.avoid ?? [] },
          exercise,
          other: emptyLifestyleCategory(),
        },
      ],
    };
  }

  const guides = rawGuides
    .map((entry): LifestyleGuideEntry | null => {
      if (typeof entry === "string") {
        const text = entry.trim();
        if (!text) return null;
        return {
          diagnosis: guide.diagnosis || "",
          diet: emptyLifestyleCategory(),
          exercise: emptyLifestyleCategory(),
          other: { recommended: [text], avoid: [] },
        };
      }
      if (!entry || typeof entry !== "object") return null;
      const rawEntry = entry as Record<string, unknown>;
      const diagnosis = String(rawEntry.diagnosis ?? guide.diagnosis ?? "").trim();

      // v1.1 이하 — 항목당 자유 텍스트 한 단락(guide: string)이던 옛 모양.
      if (typeof rawEntry.guide === "string") {
        const text = rawEntry.guide.trim();
        if (!text) return null;
        return {
          diagnosis,
          diet: emptyLifestyleCategory(),
          exercise: emptyLifestyleCategory(),
          other: { recommended: [text], avoid: [] },
          review_required: rawEntry.review_required as boolean | undefined,
          review_reason: rawEntry.review_reason as string | undefined,
        };
      }

      const diet = normalizeLifestyleCategory(rawEntry.diet);
      const exercise = normalizeLifestyleCategory(rawEntry.exercise);
      const other = normalizeLifestyleCategory(rawEntry.other);
      if (isLifestyleCategoryEmpty(diet) && isLifestyleCategoryEmpty(exercise) && isLifestyleCategoryEmpty(other)) {
        return null;
      }
      return {
        diagnosis,
        diet,
        exercise,
        other,
        review_required: rawEntry.review_required as boolean | undefined,
        review_reason: rawEntry.review_reason as string | undefined,
      };
    })
    .filter((entry): entry is LifestyleGuideEntry => entry !== null);

  return { ...guide, guides };
}

function normalizeRecordResult(result: RecordResult): RecordResult {
  if (!result.guide) return result;
  return {
    ...result,
    guide: {
      ...result.guide,
      lifestyle_guide: normalizeLifestyleGuide(result.guide.lifestyle_guide),
    },
  };
}

/** 등록내역(목록) 화면용 요약 — GET /records 응답 그대로 */
export interface RecordSummary {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  created_at: string;
  diagnosis: string;
  drug_names: string[];
  uploaded_by_name: string | null;
  // [2026-07-21 추가] 즐겨찾기처럼 목록 위쪽에 고정 — 목록은 이 값 기준으로 이미 정렬되어 온다
  pinned: boolean;
  caregiver_review_status: CaregiverReviewStatus;
  has_image: boolean;
}

/** [2026-07-25 추가] 처방전 원본 사진 — 인증이 필요한 엔드포인트라 <img src="...">로
 * 바로 못 쓴다(브라우저가 직접 요청하면 Authorization 헤더가 안 붙음). Blob으로 받아서
 * object URL을 만들어 반환 — 다 쓰면 호출부가 URL.revokeObjectURL()로 정리해야 한다.
 * record_id로만 조회해서 이 처방전에 연결된 사진만 불러온다(다른 기록의 사진이 섞일 수 없음). */
// [2026-07-28 버그수정] 휴대폰으로 찍은 처방전 원본 사진은 용량이 몇 MB씩 될 수 있는데,
// 공용 axios 클라이언트의 전역 10초 타임아웃(monitoringClient.ts)을 그대로 썼다 —
// askChat/getDrugIndication이 이미 겪은 것과 같은 문제(TROUBLESHOOTING.md 2026-07-09
// 항목 참고)로, 로컬(loopback)에서는 안 걸리다가 실제 배포 환경(휴대폰 네트워크 → nginx
// → 백엔드)에서는 10초를 넘겨 실패할 수 있다. LLM 호출만큼 오래 걸리진 않지만 넉넉하게 잡는다.
export async function getRecordImageBlobUrl(recordId: number): Promise<string> {
  const { data } = await monitoringClient.get(`/records/${recordId}/image`, {
    responseType: "blob",
    timeout: 30000,
  });
  return URL.createObjectURL(data);
}

/**
 * 처방전 업로드 → OCR → 가이드 생성까지 한 번에 처리 (동기 방식, schedule_v6 원칙)
 * 몇 초 걸릴 수 있어서 Processing.tsx가 이 함수를 호출하고 기다리는 구조로 씀.
 * 폴링 없음 — 이 호출 하나가 끝나면 최종 결과.
 * [7/9 추가] caregiverId를 넘기면 "보호자가 대신 업로드"로 기록됩니다 (생략하면 본인).
 */
export async function createRecord(patientId: number, file: File, caregiverId?: number) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await monitoringClient.post<RecordResult>("/records", formData, {
    params: { patient_id: patientId, caregiver_id: caregiverId },
    headers: { "Content-Type": "multipart/form-data" },
    // OCR+RAG_PROVIDER=real 파이프라인은 수십 초가 걸릴 수 있어 클라이언트 기본
    // timeout(10s, monitoringClient.ts)보다 훨씬 길게 잡는다. 실제로는 응답이
    // 오는데도 프론트가 먼저 타임아웃 나서 OcrError 화면이 뜨던 문제 수정.
    timeout: 120000,
  });
  return normalizeRecordResult(data);
}

/** 새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 */
// [2026-07-31 버그수정] getRecordImageBlobUrl/createRecord와 같은 이유로 timeout을 늘린다 —
// 공용 클라이언트의 기본 10초(monitoringClient.ts)로는 로컬(loopback)에서는 안 걸리다가
// 실제 배포 환경(브라우저 → nginx → 백엔드, DB도 원격 Aiven)에서만 가끔 넘겨서, 가이드가
// 실제로는 저장돼 있는데도 화면엔 "안 나옴"으로 보이던 문제.
export async function getRecord(recordId: number) {
  const { data } = await monitoringClient.get<RecordResult>(`/records/${recordId}`, {
    timeout: 120000,
  });
  return normalizeRecordResult(data);
}

/**
 * [7/9 추가] 처방전 인식 실패(OcrError.tsx) 화면의 "직접 입력하기" — OCR 없이 빈 항목
 * 1개짜리 review_required 기록을 만들어서 처방전확인 화면으로 바로 이동시킵니다.
 */
export async function createManualRecord(patientId: number, caregiverId?: number) {
  const { data } = await monitoringClient.post<RecordResult>("/records/manual", null, {
    params: { patient_id: patientId, caregiver_id: caregiverId },
  });
  return normalizeRecordResult(data);
}

/** 처방전확인 화면 — "약물 추가" 버튼, 빈 항목을 하나 더 만들어 직접 입력할 수 있게 함 */
export async function addMedicationItem(recordId: number) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/medications`);
  return normalizeRecordResult(data);
}

/** 처방전확인 화면 — 잘못 추가했거나 필요 없는 항목 삭제 (최소 1개는 남아 있어야 함) */
export async function removeMedicationItem(recordId: number, medicationId: number) {
  const { data } = await monitoringClient.delete<RecordResult>(`/records/${recordId}/medications/${medicationId}`);
  return normalizeRecordResult(data);
}

/** 등록내역 목록 (RecordsPage) */
export async function listRecords(patientId: number, signal?: AbortSignal) {
  const { data } = await monitoringClient.get<RecordSummary[]>("/records", {
    params: { patient_id: patientId },
    signal,
  });
  return data;
}

/** [2026-07-16 추가] 등록내역 삭제 (soft-delete) — 목록/상세 조회에서 이후 제외됨 */
export async function deleteRecord(recordId: number) {
  await monitoringClient.delete(`/records/${recordId}`);
}

/** [2026-07-21 추가] 등록내역 즐겨찾기처럼 위쪽에 고정/해제 */
export async function pinRecord(recordId: number, pinned: boolean) {
  await monitoringClient.patch(`/records/${recordId}/pin`, { pinned });
}

/** 처방전확인 화면 — review_required 항목 수정 후 확정 제출용 */
export interface MedicationCorrection {
  id: number;
  drug_name: string;
  dosage: string;
  dose_amount: string;
  frequency: string;
  total_days: string;
  diagnosis: string;
  drug_class: string;
  // [2026-07-21 추가] 처방확인 화면에서 고른 복용시간(공복/아침 식후 등, 순서대로 시간대에 매핑)
  dose_timings: string[];
}

/**
 * 확인 화면에서 확정 제출 → 서버가 바로 RAG 가이드 생성까지 이어서 처리하고
 * 최종 RecordResult를 돌려줍니다 (POST /records와 동일한 응답 형태).
 * [7/9 변경] 신뢰도와 무관하게 항상 이 호출에서 RAG를 생성하므로, createRecord와 같은
 * 이유로 timeout을 늘린다 — 기본 10초로는 실제 파이프라인이 끝나기 전에 타임아웃난다.
 */
export async function confirmMedications(recordId: number, medications: MedicationCorrection[]) {
  const { data } = await monitoringClient.post<RecordResult>(
    `/records/${recordId}/confirm`,
    { medications },
    { timeout: 120000 }
  );
  return normalizeRecordResult(data);
}

// [2026-07-25 추가] 보호자·기관 검토 흐름 — MedGuide.tsx(검토했어요/수정이 필요해요),
// PrescriptionReview.tsx(correction 모드)에서 쓴다.

export interface FieldFlagRequest {
  ocr_result_id: number;
  field_name: string;
  reason: string;
  suggested_value: string;
}

/** 보호자·기관이 "수정이 필요해요"로 지목한 칸들을 저장하고 환자에게 알린다. */
export async function requestCorrection(recordId: number, flags: FieldFlagRequest[]) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/request-correction`, { flags });
  return normalizeRecordResult(data);
}

/** 보호자·기관의 최종 "검토했어요". */
export async function markReviewed(recordId: number) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/mark-reviewed`);
  return normalizeRecordResult(data);
}

/** 환자가 지목된 칸 하나를 고친다 — 적용되는 값은 항상 보호자·기관이 지정한
 * suggested_value뿐이라(자유 입력 없음), 어떤 칸인지만 알려주면 된다. 활성 플래그가
 * 없는 칸은 서버가 거부한다. */
export async function correctMedicationField(recordId: number, medicationId: number, fieldName: string) {
  const { data } = await monitoringClient.patch<RecordResult>(
    `/records/${recordId}/medications/${medicationId}/correct`,
    { field_name: fieldName }
  );
  return normalizeRecordResult(data);
}

export interface RecordCorrectionNotice {
  id: number;
  record_id: number;
  patient_id: number;
  patient_name: string;
  // [2026-07-30 추가] "review_completed": 보호자·기관이 검토를 완료 — 환자에게 알림.
  event: "review_pending" | "correction_requested" | "correction_completed" | "review_completed";
  created_at: string;
  read_at: string | null;
}

/** 읽지 않은 처방전 검토 알림 — 환자는 "수정 요청"/"검토 완료"를, 보호자·기관은 "수정 완료"를 받는다.
 *
 * [2026-08-03 추가] NavBar(뱃지)와 알림함 화면(Notifications.tsx)이 같은 페이지에서 동시에
 * 이 함수를 호출한다 — api/monitoring.ts의 getCaregiverPatients와 동일한 in-flight 캐시
 * 패턴(dedupeInFlight)으로 중복 네트워크 호출을 없앤다. */
export const listCorrectionNotices = dedupeInFlight(async () => {
  const { data } = await monitoringClient.get<RecordCorrectionNotice[]>("/records/notices");
  return data;
});

export async function markCorrectionNoticeRead(noticeId: number) {
  await monitoringClient.post(`/records/notices/${noticeId}/read`);
}

/** DUR 노인주의/연령금기/임부금기 — "약 하나" 자체의 속성(다른 약과 무관하게 표시됨) */
export interface DurCaution {
  category: string;
  detail: string | null;
  extra: string | null;
}

/** [2026-07-20 추가] precautions~interactions 원문(허가사항/e약은요)을 환자용 쉬운 말
 * 3분류로 요약한 값 — LLM 미사용/실패 시 null(화면은 원문 카드로 폴백). */
export interface PatientPrecautionSummary {
  must_check: string[]; // 이런 증상이 있으면 즉시 병원·약사에게
  tell_doctor: string[]; // 복용 전 의사·약사에게 미리 알려야 하는 것
  avoid_together: string[]; // 이 약과 함께 피해야 하는 것
}

/** 약물상세(DrugInfo.tsx/DrugDetail.tsx) 화면의 약효분류·적응증 표시용.
 * [2026-07-20 추가] precautions~dur_cautions는 rag/ 패키지의 e약은요·DUR live API로
 * 온디맨드 보강 조회한 값 — 미등재 약품이거나 조회 실패 시 null/빈 배열로 내려온다. */
export interface DrugIndicationInfo {
  drug_name: string;
  matched_name: string | null;
  drug_class: string;
  indication: string | null;
  precautions: string | null;
  side_effects: string | null;
  interactions: string | null;
  storage: string | null;
  dur_cautions: DurCaution[];
  patient_summary: PatientPrecautionSummary | null;
}

export async function getDrugIndication(drugName: string) {
  const { data } = await monitoringClient.get<DrugIndicationInfo>("/ocr/drug-info", {
    params: { drug_name: drugName },
    // e약은요/허가사항/DUR live 조회와 환자용 LLM 요약까지 거치면 약품에 따라
    // 10초를 넘을 수 있다. 공통 timeout(10초)을 그대로 쓰면 응답이 있는데도
    // 프론트가 먼저 포기해서 "등록된 주의사항이 없어요"로 보일 수 있다.
    timeout: 120000,
  });
  return data;
}
