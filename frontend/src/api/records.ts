import { monitoringClient } from "./monitoringClient";

// ── 타입 정의 (records_router.py 응답 형태 그대로) ──

export interface OcrMedication {
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
  status: "processing" | "completed" | "failed";
  failure_reason: string | null;
  medications: OcrMedication[];
  guide: {
    medication_guide: { drugs: GuideDrug[] };
    lifestyle_guide: LifestyleGuide;
    source_refs: SourceRef[];
  } | null;
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
