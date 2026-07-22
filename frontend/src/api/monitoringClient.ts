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
});

// [7/10] 로그인이 켜지면서(issue #21) 일부 엔드포인트가 토큰을 요구하게 됨 — 호출부마다
// 헤더를 붙이는 대신 여기 한 곳에서 있으면 자동으로 붙인다(monitoring/care/chat/records/auth
// 전부 이 인스턴스를 공유하므로 이 한 곳 수정으로 전부 커버됨).
monitoringClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 토큰이 없거나 만료돼 401이 나면 로그인 상태를 지우고 로그인 화면으로 보낸다.
monitoringClient.interceptors.response.use(
  (response) => response,
  (error) => {
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
