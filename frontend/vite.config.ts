import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // [7/13] cloudflared quick tunnel은 매번 랜덤 서브도메인이 나와서 특정 도메인을
    // 하드코딩할 수 없다 — trycloudflare.com 서브도메인 전체만 허용(전체 허용은 아님).
    allowedHosts: ['.trycloudflare.com'],
    // [7/13] 팀원 공유용 터널(cloudflared 등)에서 백엔드를 직접 인터넷에 노출하지 않고,
    // 프론트(같은 origin)를 통해서만 접근하게 하는 선택적 프록시. VITE_MONITORING_API_URL을
    // "/api"로 두면 monitoringClient가 이 경로로 호출하고, 여기서 실제 백엔드(localhost:8000)로
    // 서버 사이드에서만 전달한다 — 기본 로컬 개발(VITE_MONITORING_API_URL 미설정)엔 영향 없음.
    proxy: {
      '/api': {
        // Docker Compose 안에서는 "localhost"가 프론트 컨테이너 자신을 가리켜서 백엔드에
        // 못 닿는다 — VITE_PROXY_TARGET으로 서비스명(backend:8000)을 넘겨받는다.
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
