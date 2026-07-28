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
// 백엔드(core/push.py)가 보내는 payload는 항상 {title, body, url} 형태의 JSON 문자열이다.
self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload: { title?: string; body?: string; url?: string };
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "건강동행", body: event.data.text() };
  }
  const { title = "건강동행", body = "", url = "/" } = payload;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/pwa-192.png",
      badge: "/pwa-192.png",
      data: { url },
    })
  );
});

// ── 알림 클릭 — 이미 열린 탭이 있으면 그 탭을 그 화면으로 이동시키고, 없으면 새 탭을 연다 ──
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data as { url?: string } | undefined)?.url ?? "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      const target = new URL(url, self.location.origin);
      for (const client of clientList) {
        const clientUrl = new URL(client.url);
        if (clientUrl.origin === target.origin && "focus" in client) {
          if ("navigate" in client) (client as WindowClient).navigate(target.href);
          return client.focus();
        }
      }
      return self.clients.openWindow(target.href);
    })
  );
});
