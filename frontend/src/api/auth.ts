import { monitoringClient } from "./monitoringClient";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  caregiver_id: number;
  name: string;
}

export async function login(email: string, password: string) {
  const { data } = await monitoringClient.post<LoginResponse>("/auth/login", { email, password });
  return data;
}
