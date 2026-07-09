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

export interface GuideDrug {
  drug_name: string;
  dosage_text: string;
  caution: string;
}

export interface LifestyleGuide {
  diagnosis: string;
  diet: { avoid: string[]; drug_specific: string[] };
  exercise: { type: string; duration: string; intensity: string };
}

export interface SourceRef {
  title: string;
  url: string;
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
 * 저신뢰(review_required) 항목을 수정해서 확정 제출 → 서버가 바로 RAG 가이드 생성까지 이어서 처리하고
 * 최종 RecordResult를 돌려줍니다 (POST /records와 동일한 응답 형태).
 */
export async function confirmMedications(recordId: number, medications: MedicationCorrection[]) {
  const { data } = await monitoringClient.post<RecordResult>(`/records/${recordId}/confirm`, {
    medications,
  });
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
