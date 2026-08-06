import { monitoringClient } from "./monitoringClient";

// [2026-07-28 추가] 백엔드(core/push.py, care_router.py)는 이미 완성돼 있었다 — 여기서는
// 프론트에 없던 "이 기기를 구독시키는" 절반만 새로 붙인다.

/** VAPID_PUBLIC_KEY가 서버에 없으면 null — 이때는 구독 자체를 시도하면 안 된다. */
async function getVapidPublicKey(): Promise<string | null> {
  const { data } = await monitoringClient.get<{ public_key: string | null }>("/push/vapid-public-key");
  return data.public_key;
}

/** VAPID 공개키(base64url) → pushManager.subscribe()가 요구하는 Uint8Array로 변환하는 표준 보일러플레이트. */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const output = new Uint8Array(new ArrayBuffer(rawData.length));
  for (let i = 0; i < rawData.length; i++) output[i] = rawData.charCodeAt(i);
  return output;
}

export function isPushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** 이 기기(브라우저)가 지금 구독 중인지 — 권한 요청 없이 조회만 한다. */
export async function getDevicePushSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return null;
  return registration.pushManager.getSubscription();
}

/** 알림 권한 요청 → 서비스워커 구독 생성 → 백엔드에 등록까지 한 번에. */
export async function subscribeDevicePush(): Promise<void> {
  if (!isPushSupported()) {
    throw new Error("이 브라우저는 푸시 알림을 지원하지 않아요.");
  }
  const publicKey = await getVapidPublicKey();
  if (!publicKey) {
    throw new Error("서버에 알림 발송 설정이 아직 안 됐어요.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("알림 권한이 허용되지 않았어요.");
  }

  const registration = await navigator.serviceWorker.ready;
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }));

  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error("구독 정보를 만들지 못했어요.");
  }
  await monitoringClient.post("/push-subscriptions", {
    endpoint: json.endpoint,
    p256dh: json.keys.p256dh,
    auth: json.keys.auth,
  });
}

/** 구독 해지 — 기기(브라우저) 쪽 구독과 서버에 등록된 구독 둘 다 지운다. */
export async function unsubscribeDevicePush(): Promise<void> {
  const subscription = await getDevicePushSubscription();
  if (!subscription) return;
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  await monitoringClient.delete("/push-subscriptions", { params: { endpoint } });
}
