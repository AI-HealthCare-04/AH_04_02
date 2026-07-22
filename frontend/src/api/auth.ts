import { monitoringClient } from "./monitoringClient";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  caregiver_id: number;
  name: string;
  role: "caregiver" | "patient";
  // [2026-07-22 추가] role === "caregiver"일 때만 값이 있음 — 계정 전환 목록의 역할 표시에 씀
  relation_type: "guardian" | "organization" | null;
  // [2026-07-22 추가, 이후 재설계로 제거 — 팀원 리뷰(fkmc10101-hub) 반영, HIGH] refresh_token을
  // 응답 body로 내려서 localStorage에 저장하던 방식은 XSS 한 번으로 14일짜리 토큰이
  // 전부 털릴 수 있는 회귀였다 — 이제 이 값은 응답에 없다. "저장된 계정" 전환은
  // switchAccount()가 httpOnly 쿠키 기반으로 처리한다.
}

export interface SwitchAccountResult {
  access_token: string;
  name: string;
  role: "caregiver" | "patient";
  relation_type: "guardian" | "organization" | null;
}

export async function login(identifier: string, password: string, rememberDevice = false) {
  // [7/10] 백엔드 LoginRequest는 email이 아니라 identifier(이메일 또는 전화번호) 필드를 받음 —
  // {email, password}로 보내면 422(Field required: identifier)가 난다.
  // [2026-07-22 추가] rememberDevice=true면 서버가 이 계정 전용 전환용 httpOnly 쿠키를
  // 심는다 — "이 기기에서 자동 로그인" 체크박스에 대응.
  const { data } = await monitoringClient.post<LoginResponse>("/auth/login", {
    identifier,
    password,
    remember_device: rememberDevice,
  });
  return data;
}

/** [2026-07-22 추가, 재설계 — 팀원 리뷰 반영, HIGH] "저장된 계정" 전환 전용 — role/subjectId는
 * 비밀이 아니라 "어느 계정인지"만 가리키는 값이다. 실제 재로그인 능력은 서버가 role/subjectId로
 * 이름 붙인 httpOnly 쿠키에만 있고, 프론트는 그 값을 절대 보지 않는다(withCredentials로
 * 쿠키만 자동 전송). 쿠키가 없거나 만료·무효화됐으면 401 — 호출부가 처리해야 한다. */
export async function switchAccount(role: "caregiver" | "patient", subjectId: number) {
  const { data } = await monitoringClient.post<SwitchAccountResult>("/auth/switch", { role, subject_id: subjectId });
  return data;
}

/** [2026-07-22 추가] "저장된 계정" 목록에서 제거되거나 "자동 로그인" 체크를 끌 때 —
 * 이 브라우저에 심어둔 전환 쿠키를 지워달라고 서버에 요청한다. */
export async function forgetSwitchAccount(role: "caregiver" | "patient", subjectId: number) {
  await monitoringClient.post("/auth/switch/forget", { role, subject_id: subjectId });
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
