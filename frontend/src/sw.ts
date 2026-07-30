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

// ── 알림 클릭 — 이미 열린 탭이 있으면 그 탭을 그 화면으로 이동시키고, 없으면 새 탭을 연다 ──
// [2026-07-30 수정] "복용했어요"/"건너뛸게요" 액션 버튼을 눌렀으면(event.action) 대시보드를
// action 쿼리로 열어서, 앱이 뜨는 순간(또는 이미 열려있던 탭이 이동하는 순간)
// Dashboard.tsx가 그 자리에서 실제 체크 API를 호출하게 한다 — 서비스워커는 로그인 토큰에
// 접근할 수 없어(localStorage 미접근) 여기서 직접 API를 부르지 않고, 이미 인증 로직을
// 갖춘 앱 페이지에 위임한다.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = (event.notification.data as { url?: string; scheduleId?: number } | undefined) ?? {};
  const url =
    event.action && data.scheduleId != null
      ? `/dashboard?highlight=${data.scheduleId}&action=${event.action}`
      : data.url ?? "/";

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
