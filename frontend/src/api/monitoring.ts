import { monitoringClient } from "./monitoringClient";

// ── 타입 정의 (monitoring_router.py 응답 형태 그대로) ──

export type IntakeStatus = "taken" | "pending" | "skipped";

export interface Medication {
  id: string;
  name: string;
  time: string;
  note: string;
  status: IntakeStatus;
}

export interface Patient {
  id: number;
  name: string;
  note: string | null;
  created_at: string;
}

export interface Caregiver {
  id: number;
  name: string;
  relation_type: string;
  created_at: string;
}

// ── API 함수 ──

/**
 * 오늘자 복약 목록 조회 (Dashboard.tsx의 Medication[] 형태 그대로 반환됨)
 */
export async function getTodayMedications(patientId: number) {
  const { data } = await monitoringClient.get<Medication[]>("/monitoring/today", {
    params: { patient_id: patientId },
  });
  return data;
}

/**
 * 복약 체크 — "복용했어요"/"건너뛸게요" 버튼
 */
export async function checkIntake(scheduleId: string, status: "taken" | "skipped") {
  const { data } = await monitoringClient.post(`/monitoring/schedules/${scheduleId}/check`, {
    status,
  });
  return data;
}

/**
 * 오늘자 체크 취소 — "아직이요" 버튼 (pending으로 되돌리기)
 */
export async function clearIntake(scheduleId: string) {
  const { data } = await monitoringClient.delete(`/monitoring/schedules/${scheduleId}/check`);
  return data;
}

/**
 * 특정 보호자가 케어하는 환자 목록
 * (로그인이 없어서 지금은 caregiver_id를 localStorage 등에서 직접 관리)
 */
export async function getCaregiverPatients(caregiverId: number) {
  const { data } = await monitoringClient.get<Patient[]>(
    `/monitoring/caregivers/${caregiverId}/patients`
  );
  return data;
}

/**
 * 전체 보호자 목록 (로그인 화면 대신 임시로 고를 때 사용)
 */
export async function getCaregivers() {
  const { data } = await monitoringClient.get<Caregiver[]>("/monitoring/caregivers");
  return data;
}

/**
 * 복약 일정 생성
 */
export async function createSchedule(payload: {
  patient_id: number;
  drug_name: string;
  time_slot: string;
  memo?: string;
}) {
  const { data } = await monitoringClient.post("/monitoring/schedules", payload);
  return data;
}
