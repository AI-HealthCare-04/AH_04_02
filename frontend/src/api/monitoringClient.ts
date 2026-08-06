import axios from "axios";

/**
 * [7/6] schedule_v6 백엔드 전용 클라이언트.
 *
 * 기존 api/client.ts는 Docker+Nginx+MySQL 구조(baseURL: "/api") 기준으로 만든 것이고,
 * 지금 실제로 쓰는 백엔드는 그냥 `uvicorn main:app`으로 로컬 8000번에 직접 뜨는 구조라
 * baseURL이 다릅니다. 두 백엔드가 완전히 다른 것이니 클라이언트도 분리해뒀어요.
 */
export const monitoringClient = axios.create({
  baseURL: import.meta.env.VITE_MONITORING_API_URL || "http://localhost:8000",
  timeout: 10000,
  // [2026-07-22 추가, 팀원 리뷰 반영 — HIGH 재설계] 계정 전환 기능이 이제 httpOnly 쿠키
  // (switch_{role}_{subject_id})로 재로그인 능력을 다룬다 — 백엔드는 이미 CORS
  // allow_credentials=True + 특정 오리진 allowlist라 이 설정만 있으면 된다. 이게 없으면
  // 브라우저가 cross-origin 응답의 Set-Cookie를 조용히 버려서 로그인해도 전환 쿠키가
  // 전혀 저장되지 않는다.
  withCredentials: true,
});

// [7/10] 로그인이 켜지면서(issue #21) 일부 엔드포인트가 토큰을 요구하게 됨 — 호출부마다
// 헤더를 붙이는 대신 여기 한 곳에서 있으면 자동으로 붙인다(monitoring/care/chat/records/auth
// 전부 이 인스턴스를 공유하므로 이 한 곳 수정으로 전부 커버됨).
monitoringClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// [2026-07-26 추가] access_token은 60분짜리라 이것만 보고 401을 내면 사용자가 앱을 열어둔
// 채 1시간만 지나도 로그인 화면으로 튕겨나갔다 — "로그인이 너무 빨리 풀린다"는 지적.
// 실제로는 로그인 시 httpOnly refresh_token 쿠키(14일)가 이미 심어져 있고 POST
// /auth/token/refresh가 그걸로 새 access_token을 내주는데, 프론트 어디에서도 이걸 호출하지
// 않아서 완전히 죽은 채로 있었다 — 그래서 아래에서 이 한 곳(모든 API가 공유하는
// 인터셉터)에 붙인다. 401이 나면 조용히 갱신해서 원래 요청을 한 번 재시도하고, 갱신마저
// 실패할 때만(refresh_token도 만료·무효) 실제로 로그아웃 처리한다.
interface RefreshTokenResponse {
  access_token: string;
  name: string;
  role: "caregiver" | "patient";
  caregiver_id: number; // [백엔드 그대로] role이 patient여도 이 필드에 subject_id가 옴
}

// 여러 요청이 동시에 401을 맞아도 refresh_token 쿠키 회전은 한 번만 — 두 번째 요청부터는
// 진행 중인 갱신에 그냥 올라탄다(안 그러면 먼저 회전한 쪽이 이기고 나머지는 이미 revoke된
// refresh_token으로 갱신을 시도해 오히려 로그아웃돼버린다).
let refreshPromise: Promise<string> | null = null;

function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = monitoringClient
      .post<RefreshTokenResponse>("/auth/token/refresh", {})
      .then(({ data }) => {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user_name", data.name);
        if (data.role === "patient") localStorage.setItem("patient_id", String(data.caregiver_id));
        else localStorage.setItem("caregiver_id", String(data.caregiver_id));
        return data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// 로그인/전환/갱신 요청 자체가 401이면 갱신을 또 시도할 게 아니라 바로 실패 처리해야 한다
// (안 그러면 비밀번호 오류에도 "갱신 시도 → 또 401" 한 바퀴를 더 돈다).
const NO_REFRESH_RETRY_PATHS = new Set(["/auth/login", "/auth/token/refresh", "/auth/switch"]);

monitoringClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    const canRetry =
      error.response?.status === 401 &&
      original &&
      !original._retry &&
      !NO_REFRESH_RETRY_PATHS.has(original.url ?? "") &&
      !!localStorage.getItem("access_token"); // 애초에 로그인한 적 없으면 갱신해봤자 소용없음

    if (canRetry) {
      original._retry = true;
      try {
        const token = await refreshAccessToken();
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
        return monitoringClient(original);
      } catch {
        // 갱신 실패 — 아래에서 로그아웃 처리
      }
    }

    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("caregiver_id");
      // [2026-07-22 추가] 예전엔 아무 설명 없이 로그인 화면으로만 돌려보내서, 특히
      // "저장된 계정" 목록에서 만료된 토큰으로 전환을 시도했을 때 사용자 입장에선
      // "눌러도 아무 반응이 없는" 버그처럼 보였다 — Login.tsx가 마운트 시 이 값을
      // 읽어 이유를 보여주고 지운다.
      sessionStorage.setItem("login_notice", "로그인이 만료됐어요. 다시 로그인해주세요.");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
