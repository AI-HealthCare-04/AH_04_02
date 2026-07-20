import { monitoringClient } from "./monitoringClient";

// ── 타입 정의 (monitoring_router.py 응답 형태 그대로) ──

// [2026-07-19 추가] "missed"는 사용자가 직접 누르는 상태가 아니라, 백엔드 스케줄러
// (core/scheduler.py)가 정시를 훌쩍 넘기고도 체크가 없으면 자동으로 판정하는 상태다.
export type IntakeStatus = "taken" | "pending" | "skipped" | "missed";

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
  phone: string | null;
  email: string | null;
  birth_date: string | null;
  push_enabled: boolean;
  sms_enabled: boolean;
  email_opt_in: boolean;
  created_at: string;
  breakfast_time: string | null;
  breakfast_regular: boolean | null;
  lunch_time: string | null;
  lunch_regular: boolean | null;
  dinner_time: string | null;
  dinner_regular: boolean | null;
}

export interface Caregiver {
  id: number;
  name: string;
  relation_type: string;
  phone: string | null;
  email: string | null;
  birth_date: string | null;
  push_enabled: boolean;
  sms_enabled: boolean;
  email_opt_in: boolean;
  org_name: string | null;
  org_type: string | null;
  business_reg_no: string | null;
  manager_name: string | null;
  manager_phone: string | null;
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
 * [7/9 추가] confirmedByCaregiverId를 넘기면 "보호자가 대신 체크"로 기록됩니다 (생략하면 본인).
 */
export async function checkIntake(
  scheduleId: string,
  status: "taken" | "skipped",
  confirmedByCaregiverId?: number
) {
  const { data } = await monitoringClient.post(`/monitoring/schedules/${scheduleId}/check`, {
    status,
    confirmed_by_caregiver_id: confirmedByCaregiverId,
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

/** [7/8 추가] 회원가입(SignUp.tsx) — 새 보호자/요양보호사/단체 프로필 생성 */
export async function createCaregiver(payload: {
  name: string;
  relation_type: string;
  phone?: string;
  email?: string;
  birth_date?: string;
  password?: string;
  push_enabled?: boolean;
  sms_enabled?: boolean;
  email_opt_in?: boolean;
  org_name?: string;
  org_type?: string;
  business_reg_no?: string;
  manager_name?: string;
  manager_phone?: string;
}) {
  const { data } = await monitoringClient.post<Caregiver>("/monitoring/caregivers", payload);
  return data;
}

/**
 * [7/8 추가] 반대 방향 — 이 환자를 케어하는 보호자 전체 목록 (Connect.tsx '연결된 사람' 표)
 */
export async function getPatientCaregivers(patientId: number) {
  const { data } = await monitoringClient.get<Caregiver[]>(
    `/monitoring/patients/${patientId}/caregivers`
  );
  return data;
}

/**
 * [7/8 추가] 보호자-환자 연결 해제 ("연결 해제" 버튼)
 */
export async function unlinkCaregiverPatient(caregiverId: number, patientId: number) {
  const { data } = await monitoringClient.delete(
    `/monitoring/caregivers/${caregiverId}/patients/${patientId}`
  );
  return data;
}

export async function linkCaregiverPatient(caregiverId: number, patientId: number) {
  const { data } = await monitoringClient.post(
    `/monitoring/caregivers/${caregiverId}/patients/${patientId}`
  );
  return data;
}

/**
 * [7/8 추가] 환자 목록 (환자관리 화면)
 */
export async function getPatients() {
  const { data } = await monitoringClient.get<Patient[]>("/monitoring/patients");
  return data;
}

export async function createPatient(payload: {
  name: string;
  note?: string;
  phone?: string;
  email?: string;
  birth_date?: string;
  password?: string;
  push_enabled?: boolean;
  sms_enabled?: boolean;
  email_opt_in?: boolean;
}) {
  const { data } = await monitoringClient.post<Patient>("/monitoring/patients", payload);
  return data;
}

export async function updatePatient(
  patientId: number,
  payload: { name?: string; note?: string; phone?: string; email?: string; birth_date?: string }
) {
  const { data } = await monitoringClient.patch<Patient>(
    `/monitoring/patients/${patientId}`,
    payload
  );
  return data;
}

export async function deletePatient(patientId: number) {
  const { data } = await monitoringClient.delete(`/monitoring/patients/${patientId}`);
  return data;
}

/** [2026-07-16 추가] 회원가입 직후 자가진단(식사 시간) 설문 저장 */
export async function updateMealTimes(
  patientId: number,
  payload: {
    breakfast_time?: string;
    breakfast_regular?: boolean;
    lunch_time?: string;
    lunch_regular?: boolean;
    dinner_time?: string;
    dinner_regular?: boolean;
  }
) {
  const { data } = await monitoringClient.put<Patient>(
    `/monitoring/patients/${patientId}/meal-times`,
    payload
  );
  return data;
}

/**
 * 복약 일정 생성
 */
export async function createSchedule(payload: {
  patient_id: number;
  drug_name: string;
  time_slot: string;
  dose_timing?: string | null;
  caregiver_alert?: boolean;
  memo?: string;
}) {
  const { data } = await monitoringClient.post("/monitoring/schedules", payload);
  return data;
}

/**
 * [7/8 추가] 복약 일정 목록 (복약일정 관리 화면)
 */
export interface Schedule {
  id: number;
  patient_id: number;
  drug_name: string;
  time_slot: string;
  dose_timing: string | null;
  caregiver_alert: boolean;
  memo: string | null;
  active: boolean;
  created_at: string;
}

export async function getSchedules(patientId: number, activeOnly = false) {
  const { data } = await monitoringClient.get<Schedule[]>("/monitoring/schedules", {
    params: { patient_id: patientId, active_only: activeOnly },
  });
  return data;
}

export async function updateSchedule(
  scheduleId: number,
  payload: {
    drug_name?: string;
    time_slot?: string;
    dose_timing?: string | null;
    caregiver_alert?: boolean;
    memo?: string;
    active?: boolean;
  }
) {
  const { data } = await monitoringClient.patch<Schedule>(
    `/monitoring/schedules/${scheduleId}`,
    payload
  );
  return data;
}

/**
 * [7/8 추가] '새 일정 추가' 모달의 "약물 선택" 드롭다운 — 이 환자에게 실제로 존재하는 약 이름 목록
 */
export async function getKnownDrugs(patientId: number) {
  const { data } = await monitoringClient.get<string[]>(
    `/monitoring/patients/${patientId}/known-drugs`
  );
  return data;
}

export async function deleteSchedule(scheduleId: number) {
  const { data } = await monitoringClient.delete(`/monitoring/schedules/${scheduleId}`);
  return data;
}

/**
 * [7/8 추가] 모니터링대시보드(보호자용) 캘린더·이행률 계산용 원본 로그.
 * 별도 집계 endpoint 없이 최근 N일 로그를 그대로 받아 프론트에서 계산합니다.
 */
export interface MedicationLogEntry {
  // [2026-07-19 변경] "missed" 항목은 실제 체크 기록이 아니라 NotificationLog에서
  // 합성된 가상 행이라 id가 숫자 PK가 아니고 "missed:12" 형태 문자열이다.
  id: string;
  schedule_id: number;
  drug_name: string;
  time_slot: string;
  status: "taken" | "skipped" | "missed";
  checked_at: string;
  confirmed_by_type: "patient" | "caregiver" | "system";
  confirmed_by_name: string;
}

export async function getLogs(patientId: number, days = 30) {
  const { data } = await monitoringClient.get<MedicationLogEntry[]>("/monitoring/logs", {
    params: { patient_id: patientId, days },
  });
  return data;
}
