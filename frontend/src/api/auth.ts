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
