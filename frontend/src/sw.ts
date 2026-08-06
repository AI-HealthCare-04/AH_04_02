/// <reference lib="webworker" />
import { clientsClaim } from "workbox-core";
import { precacheAndRoute } from "workbox-precaching";

declare let self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);

// registerType: 'autoUpdate'가 새 버전을 감지하면 이 메시지를 보낸다 — 즉시 활성화해서
// "탭을 전부 닫기 전까진 옛 버전이 계속 보이는" 대기 상태를 없앤다.
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
clientsClaim();

// ── Web Push 수신 ──
// 백엔드(core/push.py)가 보내는 payload는 {title, body, url} + 복약 알림이면 schedule_id도
// 같이 온다. schedule_id가 있으면 "복용했어요"/"건너뛸게요" 액션 버튼을 붙인다 — 안드로이드/
// 데스크톱 Chrome 계열만 지원(iOS Safari는 알림 액션 버튼 자체를 지원 안 해서, 그 경우
// schedule_id가 있어도 버튼 없이 기존처럼 탭하면 앱만 열린다. 플랫폼 한계).
self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload: { title?: string; body?: string; url?: string; schedule_id?: number };
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "건강동행", body: event.data.text() };
  }
  const { title = "건강동행", body = "", url = "/", schedule_id } = payload;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/pwa-192.png",
      badge: "/pwa-192.png",
      data: { url, scheduleId: schedule_id },
      ...(schedule_id != null
        ? {
            actions: [
              { action: "taken", title: "복용했어요" },
              { action: "skipped", title: "건너뛸게요" },
            ],
          }
        : {}),
    })
  );
});

// ── 이미 열린 탭이 있으면 그 탭을 그 화면으로 이동시키고, 없으면 새 탭을 연다 ──
function openOrFocus(url: string) {
  return self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
    const target = new URL(url, self.location.origin);
    for (const client of clientList) {
      const clientUrl = new URL(client.url);
      if (clientUrl.origin === target.origin && "focus" in client) {
        if ("navigate" in client) (client as WindowClient).navigate(target.href);
        return client.focus();
      }
    }
    return self.clients.openWindow(target.href);
  });
}

// [2026-07-30 추가] monitoringClient.ts와 동일한 baseURL 규칙 — 이 파일도 vite-plugin-pwa의
// injectManifest로 앱과 같은 Vite 빌드를 타서 import.meta.env가 그대로 치환된다.
const API_BASE = import.meta.env.VITE_MONITORING_API_URL || "http://localhost:8000";

// [2026-07-30 추가] 서비스워커는 localStorage(access_token)에 접근할 수 없지만, 로그인 시
// 심어둔 httpOnly refresh_token 쿠키(monitoringClient.ts와 동일, 14일)는 credentials:"include"
// fetch면 브라우저가 자동으로 실어준다 — 이 쿠키만으로 새 access_token을 매번 새로 받아서
// 쓴다(따로 토큰을 저장/캐싱하지 않음, 만료 걱정 없음).
async function fetchFreshAccessToken(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/auth/token/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) return null;
    const data: { access_token?: string } = await res.json();
    return data.access_token ?? null;
  } catch {
    return null;
  }
}

// [2026-07-30 추가] 알림의 "복용했어요"/"건너뛸게요" 버튼 — 앱을 열지 않고 서비스워커에서
// 바로 처리한다. 로그아웃된 기기 등으로 실패하면 false를 반환하고, 호출부가 기존처럼
// 앱을 열어서 처리하도록 폴백한다.
async function checkScheduleInBackground(scheduleId: number, status: "taken" | "skipped"): Promise<boolean> {
  const token = await fetchFreshAccessToken();
  if (!token) return false;
  try {
    const res = await fetch(`${API_BASE}/monitoring/schedules/${scheduleId}/check`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ status }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = (event.notification.data as { url?: string; scheduleId?: number } | undefined) ?? {};

  if ((event.action === "taken" || event.action === "skipped") && data.scheduleId != null) {
    const scheduleId = data.scheduleId;
    const status = event.action;
    event.waitUntil(
      // ponytail: showNotification()은 Promise<void>, openOrFocus()는
      // Promise<WindowClient | null>라 .then() 콜백의 반환 타입이 갈려 tsc가 통합을
      // 못 했다 — async IIFE로 감싸 두 분기 다 반환값 없이 await만 하면 항상
      // Promise<void>로 통일된다.
      (async () => {
        const ok = await checkScheduleInBackground(scheduleId, status);
        if (ok) {
          // 앱을 안 열었으니, 처리됐다는 걸 알 수 있게 알림을 하나 더 띄운다.
          await self.registration.showNotification("처리 완료", {
            body: status === "taken" ? "복용 처리했어요." : "건너뛰기로 처리했어요.",
            icon: "/pwa-192.png",
            tag: `med-check-${scheduleId}`,
          });
          return;
        }
        // 실패(로그아웃·네트워크 오류 등) 시엔 기존 방식대로 앱을 열어서 직접 처리하게 한다.
        await openOrFocus(`/dashboard?highlight=${scheduleId}&action=${status}`);
      })()
    );
    return;
  }

  event.waitUntil(openOrFocus(data.url ?? "/"));
});
