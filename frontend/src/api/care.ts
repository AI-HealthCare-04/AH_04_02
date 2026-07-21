import { monitoringClient } from "./monitoringClient";

// ── 1. 자가진단 (Assessment) ──

export type Level = "normal" | "mild" | "severe";
export type CareLevel = "independent" | "guardian_check" | "third_party_needed";

export interface AssessmentResult {
  id: number;
  patient_id: number;
  cognitive_level: Level;
  mobility_level: Level;
  vision_level: Level;
  medication_awareness: boolean;
  medication_willingness: boolean;
  care_level: CareLevel;
  reason: string;
  evaluated_at: string;
}

export async function createAssessment(payload: {
  patient_id: number;
  cognitive_level: Level;
  mobility_level: Level;
  vision_level: Level;
  medication_awareness: boolean;
  medication_willingness: boolean;
}) {
  const { data } = await monitoringClient.post<AssessmentResult>("/assessments", payload);
  return data;
}

export async function getLatestAssessment(patientId: number) {
  const { data } = await monitoringClient.get<AssessmentResult | null>("/assessments/latest", {
    params: { patient_id: patientId },
  });
  return data;
}

// ── 2. 보호자 초대 (Invitation) ──

export interface InvitationCreated {
  token: string;
  invite_url: string;
}

export interface InvitationInfo {
  status: "pending" | "accepted" | "rejected" | "expired";
  relation_type: string;
  patient_name: string;
  inviter_name: string | null;
  // [2026-07-15] 초대가 특정 전화번호를 지정했으면 true — 수락 시 본인 전화번호 입력을 요구해야 함(REQ-003)
  phone_verification_required: boolean;
  // [2026-07-22 추가] InviteAccept.tsx의 "초대 만료" 표시용
  expires_at: string;
}

export async function createInvitation(payload: {
  // 보호자→환자 초대(relation_type="patient")는 아직 환자 계정이 없어 patient_id 없이 보낸다.
  patient_id?: number;
  relation_type: string;
  invited_phone?: string;
  inviter_caregiver_id?: number;
}) {
  const { data } = await monitoringClient.post<InvitationCreated>("/invitations", payload);
  return data;
}

export async function getInvitation(token: string) {
  const { data } = await monitoringClient.get<InvitationInfo>(`/invitations/${token}`);
  return data;
}

export async function acceptInvitation(
  token: string,
  payload: {
    // relation_type != "patient" (환자→보호자 초대) 수락용
    caregiver_name?: string;
    caregiver_id?: number;
    phone?: string;
    // relation_type == "patient" (보호자→환자 초대) 수락용 — 실제 환자 계정 가입 정보
    patient_name?: string;
    patient_email?: string;
    patient_password?: string;
    patient_phone?: string;
  }
) {
  const { data } = await monitoringClient.post(`/invitations/${token}/accept`, payload);
  return data;
}

export async function rejectInvitation(token: string) {
  const { data } = await monitoringClient.post(`/invitations/${token}/reject`);
  return data;
}

export interface InvitationSummary {
  id: number;
  patient_id: number;
  relation_type: string;
  invited_phone: string | null;
  status: string;
  created_at: string;
}

export async function listInvitations(patientId: number) {
  const { data } = await monitoringClient.get<InvitationSummary[]>(
    `/patients/${patientId}/invitations`
  );
  return data;
}

// ── 3. 알림 설정 (NotificationSetting) ──

export interface NotificationSettings {
  patient_id: number;
  medication_reminder_enabled: boolean;
  care_alert_enabled: boolean;
  all_push_enabled: boolean;
  chatbot_name: string;
  updated_at: string;
}

export async function getNotificationSettings(patientId: number) {
  const { data } = await monitoringClient.get<NotificationSettings>("/notification-settings", {
    params: { patient_id: patientId },
  });
  return data;
}

export async function updateNotificationSettings(
  patientId: number,
  payload: Partial<
    Pick<
      NotificationSettings,
      "medication_reminder_enabled" | "care_alert_enabled" | "all_push_enabled" | "chatbot_name"
    >
  >
) {
  const { data } = await monitoringClient.put<NotificationSettings>(
    "/notification-settings",
    payload,
    { params: { patient_id: patientId } }
  );
  return data;
}
