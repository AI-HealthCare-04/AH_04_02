import { dedupeInFlight } from "../lib/dedupeInFlight";
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
  gender: "male" | "female" | null;
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
  // [2026-07-22 추가] 환자 관리 테이블(PatientManagement.tsx) 전용 — GET /caregivers/{id}/patients만
  // 채워 보내고, 다른 곳(회원가입 응답 등)에서는 항상 기본값(null/"none")으로 온다.
  diagnoses: string | null;
  medication_status: "active" | "paused" | "none";
  // [2026-07-23 추가] 환자 관리 테이블 "오늘 상태" 동그라미용 — GET /caregivers/{id}/patients만 채움
  today_status: "ok" | "missed";
  // [2026-07-30 추가] "환자 단위"가 아니라 "이 보호자·이 환자 관계 단위" 값 — GET
  // /caregivers/{id}/patients만 채움. 다른 곳에서는 항상 기본값(true)으로 온다.
  notifications_enabled: boolean;
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
// [2026-07-30 추가] 한 페이지에서 NavBar 배지·PatientContextBanner·useGuardedPatientId 등
// 여러 컴포넌트가 동시에 이 함수를 호출해 같은 GET이 한 순간에 몰리면 일부가
// net::ERR_ABORTED로 실패하는 걸 재현 확인했다 — 진행 중인 요청을 캐시해 동시 호출은
// 실제 네트워크 요청 하나만 공유하게 한다(끝나면 즉시 비워 다음 호출은 새로 나간다).
let inFlight: Promise<Patient[]> | null = null;
let inFlightCaregiverId: number | null = null;

export async function getCaregiverPatients(caregiverId: number) {
  if (inFlight && inFlightCaregiverId === caregiverId) return inFlight;
  inFlightCaregiverId = caregiverId;
  inFlight = monitoringClient
    .get<Patient[]>(`/monitoring/caregivers/${caregiverId}/patients`)
    .then((res) => res.data)
    .finally(() => {
      inFlight = null;
      inFlightCaregiverId = null;
    });
  return inFlight;
}

/** [2026-07-30 추가] 여러 환자를 관리하는 보호자·기관이 (본인, 이 환자) 관계 단위로
 * 알림 수신 여부를 끄고 켠다 — NotificationSetting(환자 단위, 모든 보호자가 공유하는
 * "복약 알림"/"돌봄 알림" 설정)과는 별개다. */
export async function updateCaregiverPatientNotifications(
  caregiverId: number,
  patientId: number,
  enabled: boolean
) {
  const { data } = await monitoringClient.patch<{ notifications_enabled: boolean }>(
    `/monitoring/caregivers/${caregiverId}/patients/${patientId}/notifications`,
    { enabled }
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

/** [2026-07-22 추가] "내 정보"(MyInfo.tsx) — 회원가입 때 받은 보호자/기관 정보 수정 */
export async function updateCaregiver(
  caregiverId: number,
  payload: {
    name?: string;
    phone?: string;
    email?: string;
    birth_date?: string;
    push_enabled?: boolean;
    sms_enabled?: boolean;
    email_opt_in?: boolean;
    org_name?: string;
    org_type?: string;
    business_reg_no?: string;
    manager_name?: string;
    manager_phone?: string;
  }
) {
  const { data } = await monitoringClient.patch<Caregiver>(
    `/monitoring/caregivers/${caregiverId}`,
    payload
  );
  return data;
}

/** [2026-07-23 추가] 회원가입(SignUp.tsx) — 이메일/전화번호 입력 필드에서 포커스를 잃을 때
 * 중복 여부를 미리 알려주기 위한 조회 전용 호출(계정을 만들지 않음). */
export async function checkPatientDuplicate(params: { email?: string; phone?: string }) {
  const { data } = await monitoringClient.get<{ email_taken: boolean; phone_taken: boolean }>(
    "/monitoring/patients/check-duplicate",
    { params }
  );
  return data;
}

export async function checkCaregiverDuplicate(params: {
  relation_type: "guardian" | "organization";
  email?: string;
  phone?: string;
}) {
  const { data } = await monitoringClient.get<{ email_taken: boolean; phone_taken: boolean }>(
    "/monitoring/caregivers/check-duplicate",
    { params }
  );
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
// [2026-07-23 수정] 기관(organization) 계정이 끊을 때는 reason이 필수 — 서버가 즉시 끊는
// 대신 환자/보호자 승인 대기(status="revocation_pending")로 돌린다. 개인 보호자·환자
// 본인은 reason 없이 호출하면 기존처럼 즉시 처리된다.
export async function unlinkCaregiverPatient(caregiverId: number, patientId: number, reason?: string) {
  const { data } = await monitoringClient.delete(
    `/monitoring/caregivers/${caregiverId}/patients/${patientId}`,
    { params: reason ? { reason } : undefined }
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
  gender?: "male" | "female";
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
  payload: {
    name?: string;
    note?: string;
    phone?: string;
    email?: string;
    birth_date?: string;
    gender?: "male" | "female";
    push_enabled?: boolean;
    sms_enabled?: boolean;
    email_opt_in?: boolean;
  }
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
  // [2026-07-24 추가] 이 일정 알림을 받을 caregiver id 목록 — 안 보내거나 빈 배열([])이면
  // 백엔드가 연결된 caregiver 전원에게 보낸다(비었다는 것만으로는 "아직 안 골랐다"와
  // "일부러 0명"을 구분할 수 없어서). "정말 아무에게도 안 보낸다"를 표현하려면
  // caregiver_alert도 false로 같이 보내야 한다 — Schedule.tsx는 체크박스를 모두 해제하면
  // 실제로 그렇게 두 값을 함께 보낸다.
  alert_caregiver_ids?: number[];
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
  // [2026-07-24 추가] 이 일정의 알림을 실제로 받는 caregiver id 목록 — 명시적으로 고른
  // 적 없으면 서버가 연결된 caregiver 전원을 그대로 채워서 돌려준다(실제 발송 대상과
  // 항상 일치, core/schedule_alerts.py.effective_alert_caregiver_ids 참고).
  alert_caregiver_ids: number[];
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
    alert_caregiver_ids?: number[];
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

// [2026-07-23 추가] 알림함(웹 인박스) — NotificationLog 원본을 그대로 노출한다.
export interface NotificationLogEntry {
  id: number;
  schedule_id: number;
  drug_name: string;
  time_slot: string;
  due_date: string;
  kind: "reminder" | "missed";
  status: "pending" | "sent" | "suppressed" | "failed";
  fired_at: string;
  // [2026-07-30 추가] null이면 알림함에 한 번도 표시된 적 없음(안 읽음).
  acknowledged_at: string | null;
}

// [2026-08-03 추가] NavBar(뱃지)와 이 API를 쓰는 화면(예: Notifications.tsx 목록)이 같은
// 페이지에서 동시에 마운트되면 같은 patientId로 이 함수를 동시에 호출한다 — getCaregiverPatients와
// 동일하게 진행 중인 요청을 공유해 중복 네트워크 호출을 없앤다.
export const getNotifications = dedupeInFlight(
  async (patientId: number, days = 30) => {
    const { data } = await monitoringClient.get<NotificationLogEntry[]>(
      `/monitoring/patients/${patientId}/notifications`,
      { params: { days } }
    );
    return data;
  },
  (patientId, days = 30) => `${patientId}:${days}`
);

/** [2026-07-30 추가] 알림함이 복약 알림 목록을 화면에 띄우는 시점에 호출 — 그 시점까지
 * 안 읽었던 것 전부를 "표시함"으로 처리한다(개별 클릭 대상이 없는 단순 로그라 목록
 * 노출 자체를 읽음 기준으로 삼음). */
export async function acknowledgeNotifications(patientId: number) {
  await monitoringClient.post(`/monitoring/patients/${patientId}/notifications/acknowledge`);
}

export async function deleteNotification(patientId: number, notificationId: number) {
  await monitoringClient.delete(`/monitoring/patients/${patientId}/notifications/${notificationId}`);
}

export async function deleteNotifications(patientId: number, notificationIds: number[]) {
  const { data } = await monitoringClient.post<{ deleted: number }>(
    `/monitoring/patients/${patientId}/notifications/delete`,
    { notification_ids: notificationIds }
  );
  return data;
}

export async function clearAcknowledgedNotifications(patientId: number) {
  const { data } = await monitoringClient.delete<{ deleted: number }>(
    `/monitoring/patients/${patientId}/notifications`
  );
  return data;
}
