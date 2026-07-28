import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // [2026-07-28 추가] Web Push(알림 클릭 시 특정 화면 열기)를 받으려면 서비스워커에
      // push/notificationclick 핸들러가 있어야 하는데, 기본 generateSW 전략은 캐싱 코드만
      // 자동 생성하고 커스텀 이벤트 리스너를 못 끼워넣는다 — src/sw.ts를 직접 작성하고
      // injectManifest 전략으로 그 프리캐시 목록만 주입받는 방식으로 바꿨다.
      // skipWaiting/clientsClaim은 이제 sw.ts 안에서 직접 처리한다(이 옵션은 generateSW 전용).
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectManifest: {
        // 알림 아이콘 등 정적 파일까지 프리캐시 목록에 다 넣을 필요는 없다 — 기본값이면 충분.
      },
      devOptions: {
        // 개발 서버(vite dev)에서도 실제 서비스워커가 등록돼야 로컬에서 push 구독/수신을
        // 테스트할 수 있다 — 기본값(false)이면 dev 모드에서 서비스워커 자체가 안 뜬다.
        enabled: true,
        type: 'module',
      },
      manifest: {
        name: '건강동행',
        short_name: '건강동행',
        description: '복약 안내 서비스 건강동행',
        theme_color: '#C1653D',
        background_color: '#FAF6F1',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    // [7/13] cloudflared quick tunnel은 매번 랜덤 서브도메인이 나와서 특정 도메인을
    // 하드코딩할 수 없다 — trycloudflare.com 서브도메인 전체만 허용(전체 허용은 아님).
    allowedHosts: ['.trycloudflare.com', 'yakcong.duckdns.org'],
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
