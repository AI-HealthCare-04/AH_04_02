import { monitoringClient } from "./monitoringClient";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  caregiver_id: number;
  name: string;
  role: "caregiver" | "patient";
}

export async function login(identifier: string, password: string) {
  // [7/10] 백엔드 LoginRequest는 email이 아니라 identifier(이메일 또는 전화번호) 필드를 받음 —
  // {email, password}로 보내면 422(Field required: identifier)가 난다.
  const { data } = await monitoringClient.post<LoginResponse>("/auth/login", { identifier, password });
  return data;
}

// ── 비밀번호 재설정 [2026-07-15] 3단계: request(임시번호 발송) → verify(임시번호 확인,
// reset_token 발급) → confirm(새 비밀번호 설정). 백엔드는 REQ-039(PR #48)에서 구현됨. ──
export async function requestPasswordReset(identifier: string) {
  const { data } = await monitoringClient.post<{ message: string }>("/auth/password-reset/request", { identifier });
  return data;
}

export async function verifyPasswordReset(identifier: string, code: string) {
  const { data } = await monitoringClient.post<{ reset_token: string }>("/auth/password-reset/verify", {
    identifier,
    code,
  });
  return data;
}

export async function confirmPasswordReset(resetToken: string, newPassword: string) {
  const { data } = await monitoringClient.post<{ message: string }>("/auth/password-reset/confirm", {
    reset_token: resetToken,
    new_password: newPassword,
  });
  return data;
}
