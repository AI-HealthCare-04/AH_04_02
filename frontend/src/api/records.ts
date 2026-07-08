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
 * [7/8] RAG_PROVIDER=stub(기본값)과 RAG_PROVIDER=real이 서로 다른 모양을 반환한다.
 * 두 모드를 전환하며 테스트해야 하는 과도기라 필드를 전부 optional로 두고,
 * Result.tsx/PrescriptionDetail.tsx에서 어느 필드가 있는지 보고 어느 모드인지
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
}

/** source_refs 항목 하나를 사람이 읽을 수 있는 한 줄로 표시 (stub/실제 두 모양 다 처리) */
export function formatSourceRef(ref: SourceRef): string {
  if (ref.title) return ref.title; // stub 모양
  if (ref.item_name) return `${ref.item_name}${ref.field ? ` · ${ref.field}` : ""}`; // 의약품 인용
  if (ref.disease) return `${ref.disease}${ref.category ? ` · ${ref.category}` : ""}`; // 생활지침 인용
  return ref.drug_name ?? "출처 미상";
}

export interface RecordResult {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  failure_reason: string | null;
  medications: OcrMedication[];
  guide: {
    medication_guide: { drugs: GuideDrug[] };
    lifestyle_guide: LifestyleGuide;
    source_refs: SourceRef[];
  } | null;
}

/** 이용기록(목록) 화면용 요약 — GET /records 응답 그대로 */
export interface RecordSummary {
  record_id: number;
  status: "processing" | "review_required" | "completed" | "failed";
  created_at: string;
  diagnosis: string;
  drug_names: string[];
}

/**
 * 처방전 업로드 → OCR → 가이드 생성까지 한 번에 처리 (동기 방식, schedule_v6 원칙)
 * 몇 초 걸릴 수 있어서 Processing.tsx가 이 함수를 호출하고 기다리는 구조로 씀.
 * 폴링 없음 — 이 호출 하나가 끝나면 최종 결과.
 */
export async function createRecord(patientId: number, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await monitoringClient.post<RecordResult>("/records", formData, {
    params: { patient_id: patientId },
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/** 새로고침 등으로 결과 화면을 다시 열었을 때 재조회용 */
export async function getRecord(recordId: number) {
  const { data } = await monitoringClient.get<RecordResult>(`/records/${recordId}`);
  return data;
}

/** 이용기록 목록 (RecordsPage) */
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
 * 저신뢰(review_required) 항목을 수정해서 확정 제출 → 서버가 바로 RAG 가이드 생성까지 이어서 처리하고
 * 최종 RecordResult를 돌려줍니다 (POST /records와 동일한 응답 형태).
 */
export async function confirmMedications(recordId: number, medications: MedicationCorrection[]) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/confirm`, {
    medications,
  });
  return data;
}
