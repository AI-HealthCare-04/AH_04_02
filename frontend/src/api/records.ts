import { monitoringClient } from "./monitoringClient";

// ── 타입 정의 (records_router.py 응답 형태 그대로) ──

export interface OcrMedication {
  id: number;
  drug_name: string;
  dosage: string;
  frequency: string;
  diagnosis: string;
  drug_class: string;
  confidence: number;
  review_required: boolean;
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
  review_flags?: string[];
}

export interface LifestyleGuide {
  diagnosis: string;
  // stub 모양
  diet?: { avoid: string[]; drug_specific: string[] };
  exercise?: { type: string; duration: string; intensity: string };
  // 실제 파이프라인 모양 — 약별 생활습관 안내 전문 리스트
  guides?: string[];
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
  // 실제 파이프라인 — 생활지침 인용
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
 * (생활지침 여러 항목이 같은 학회 지침을 공유하는 경우가 많음). */
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

export interface RecordResult {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  failure_reason: string | null;
  created_at: string;
  uploaded_by_name: string | null;
  medications: OcrMedication[];
  guide: {
    medication_guide: { drugs: GuideDrug[] };
    lifestyle_guide: LifestyleGuide;
    source_refs: SourceRef[];
  } | null;
}

/** 등록내역(목록) 화면용 요약 — GET /records 응답 그대로 */
export interface RecordSummary {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  created_at: string;
  diagnosis: string;
  drug_names: string[];
  uploaded_by_name: string | null;
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
  return data;
}

/** 새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 */
export async function getRecord(recordId: number) {
  const { data } = await monitoringClient.get<RecordResult>(`/records/${recordId}`);
  return data;
}

/**
 * [7/9 추가] 처방전 인식 실패(OcrError.tsx) 화면의 "직접 입력하기" — OCR 없이 빈 항목
 * 1개짜리 review_required 기록을 만들어서 처방전확인 화면으로 바로 이동시킵니다.
 */
export async function createManualRecord(patientId: number, caregiverId?: number) {
  const { data } = await monitoringClient.post<RecordResult>("/records/manual", null, {
    params: { patient_id: patientId, caregiver_id: caregiverId },
  });
  return data;
}

/** 처방전확인 화면 — "약물 추가" 버튼, 빈 항목을 하나 더 만들어 직접 입력할 수 있게 함 */
export async function addMedicationItem(recordId: number) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/medications`);
  return data;
}

/** 처방전확인 화면 — 잘못 추가했거나 필요 없는 항목 삭제 (최소 1개는 남아 있어야 함) */
export async function removeMedicationItem(recordId: number, medicationId: number) {
  const { data } = await monitoringClient.delete<RecordResult>(`/records/${recordId}/medications/${medicationId}`);
  return data;
}

/** 등록내역 목록 (RecordsPage) */
export async function listRecords(patientId: number) {
  const { data } = await monitoringClient.get<RecordSummary[]>("/records", {
    params: { patient_id: patientId },
  });
  return data;
}

/** 처방전확인 화면 — review_required 항목 수정 후 확정 제출용 */
export interface MedicationCorrection {
  id: number;
  drug_name: string;
  dosage: string;
  frequency: string;
  diagnosis: string;
  drug_class: string;
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
  return data;
}

/** 약물상세(DrugInfo.tsx/DrugDetail.tsx) 화면의 약효분류·적응증 표시용 */
export interface DrugIndicationInfo {
  drug_name: string;
  matched_name: string | null;
  drug_class: string;
  indication: string | null;
}

export async function getDrugIndication(drugName: string) {
  const { data } = await monitoringClient.get<DrugIndicationInfo>("/ocr/drug-info", {
    params: { drug_name: drugName },
  });
  return data;
}
