import axios from "axios";

/**
 * [7/6] schedule_v6 백엔드 전용 클라이언트.
 *
 * 기존 api/client.ts는 Docker+Nginx+MySQL 구조(baseURL: "/api") 기준으로 만든 것이고,
 * 지금 실제로 쓰는 백엔드는 그냥 `uvicorn main:app`으로 로컬 8000번에 직접 뜨는 구조라
 * baseURL이 다릅니다. 두 백엔드가 완전히 다른 것이니 클라이언트도 분리해뒀어요.
 *
 * 로그인이 아직 없어서(main.py에 auth_router 미등록) Authorization 헤더는 안 붙입니다.
 * 나중에 로그인이 켜지면 client.ts처럼 인터셉터로 JWT 첨부하는 코드를 추가하면 됩니다.
 */
export const monitoringClient = axios.create({
  baseURL: import.meta.env.VITE_MONITORING_API_URL || "http://localhost:8000",
  timeout: 10000,
});
