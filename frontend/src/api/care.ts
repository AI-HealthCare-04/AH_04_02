import { monitoringClient } from "./monitoringClient";

// ── 1. 보호자 초대 (Invitation) ──

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
  // [2026-07-22 추가] InviteAccept.tsx의 "초대 만료" 표시용 — DB 컬럼 자체가 nullable이라
  // 이 컬럼이 생기기 전에 만들어진 pending 초대는 null일 수 있다.
  expires_at: string | null;
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
    // [2026-07-23 추가] 이미 로그인된 환자 계정으로 수락할 때 — 새 계정을 만들지 않고 이 id를 그대로 연결
    patient_id?: number;
  }
) {
  const { data } = await monitoringClient.post(`/invitations/${token}/accept`, payload);
  return data;
}

export async function rejectInvitation(token: string) {
  const { data } = await monitoringClient.post(`/invitations/${token}/reject`);
  return data;
}

export async function deleteInvitation(invitationId: number) {
  const { data } = await monitoringClient.delete(`/invitations/${invitationId}`);
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

// [2026-07-22 추가] "받은 초대" — 환자가 전화번호를 지정해 보낸 초대를 링크 없이 확인/수락하는
// 보호자·기관용 흐름(PatientManagement.tsx). InvitationSummary와 달리 patient_id/invited_phone이
// 없다 — 이건 "내가 보낸" 목록이 아니라 "나에게 온" 목록이라 다른 사람의 patient_id를 노출하지 않는다.
export interface ReceivedInvitation {
  id: number;
  relation_type: string;
  patient_name: string;
  created_at: string;
  expires_at: string | null;
}

export async function listReceivedInvitations(caregiverId: number) {
  const { data } = await monitoringClient.get<ReceivedInvitation[]>(
    `/caregivers/${caregiverId}/pending-invitations`
  );
  return data;
}

export async function acceptInvitationAsCaregiver(invitationId: number) {
  const { data } = await monitoringClient.post(`/invitations/${invitationId}/accept-as-caregiver`);
  return data;
}

export async function rejectInvitationAsCaregiver(invitationId: number) {
  const { data } = await monitoringClient.post(`/invitations/${invitationId}/reject-as-caregiver`);
  return data;
}

// ── 2. 돌봄관계 해제 승인 (Trust Relation Revocation) ──
// [2026-07-23 추가] 기관(organization) 계정이 연결을 끊을 때는 사유를 남기고 환자/보호자의
// 승인을 기다려야 한다(monitoringClient.unlinkCaregiverPatient가 reason을 보내면 서버가
// 바로 끊는 대신 대기 상태로 전환). 이 두 함수는 그 대기 요청을 받는 쪽(환자/보호자)이
// 확인·승인/거부하는 데 쓴다.

export interface PendingRevocation {
  trust_id: number;
  patient_id: number;
  patient_name: string;
  caregiver_id: number;
  caregiver_name: string;
  reason: string | null;
  requested_at: string | null;
  requested_by_role: string;
  deadline: string | null;
  can_finalize: boolean;
}

export async function listPendingRevocations() {
  const { data } = await monitoringClient.get<PendingRevocation[]>("/trust/relations/pending");
  return data;
}

export async function approveRevocation(trustId: number, approve: boolean) {
  const { data } = await monitoringClient.post(`/trust/relations/${trustId}/revocation-approval`, {
    approve,
  });
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
