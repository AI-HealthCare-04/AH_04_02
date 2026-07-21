import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { refreshAccessToken } from "../api/auth";
import { getCaregiverPatients } from "../api/monitoring";

/**
 * 로그인이 없어서 "지금 보고 있는 환자/보호자가 누구인지"를 localStorage로 관리합니다.
 * Login.tsx에서 보호자·환자 선택 시 이 값들을 저장합니다.
 */
export function getCurrentPatientId(): number {
  return Number(localStorage.getItem("patient_id") ?? 1);
}

export function getCurrentCaregiverId(): number | null {
  const value = localStorage.getItem("caregiver_id");
  return value ? Number(value) : null;
}

/** [2026-07-19 추가] 로그인/가입 시점에 저장해두는 실제 사용자 이름 — NavBar가 화면마다
 * "김건강"으로 하드코딩돼있던 문제 수정용. Login.tsx/SignUp.tsx에서 저장한다. */
export function getCurrentUserName(): string {
  return localStorage.getItem("user_name") ?? "";
}

/** [7/14] access_token 존재 여부로 로그인 상태를 판단 — monitoringClient.ts의 401
 * 인터셉터가 이 토큰을 검사하는 것과 동일한 기준. 비로그인 상태에서 인증 필요한
 * API를 호출하면 401 → 강제로 /login 리다이렉트되는 걸 막을 때 이걸로 먼저 가드한다. */
export function isLoggedIn(): boolean {
  return !!localStorage.getItem("access_token");
}

/**
 * [2026-07-21 추가] "다른 사용자로 전환"(MyPage.tsx) — 네이버 등에서처럼 이 기기에서
 * 로그인했던 계정을 기억해뒀다가 클릭 한 번으로 다시 로그인할 수 있게 함.
 * [2026-07-22 수정] 처음엔 access_token(60분)을 그대로 저장해뒀다가 재사용하는 방식이라
 * 만료되면 그냥 로그인 화면으로 튕겨나갔다 — refresh_token(14일)도 같이 저장해두고
 * switchToRecentAccount()가 전환 시점에 새 access_token을 스스로 받아오게 바꿨다.
 */
export interface RecentAccount {
  identifier: string; // 로그인에 쓴 이메일/전화번호 — 계정 식별 및 표시용
  name: string;
  accessToken: string;
  // [2026-07-22 추가] access_token 만료 후 재발급용. 재사용 방지로 쓸 때마다 새로 발급되니
  // switchToRecentAccount()가 매번 이 값도 최신 것으로 갱신해서 다시 저장한다.
  refreshToken: string;
  // [2026-07-22 추가] 계정 전환 목록에 "환자 본인/보호자/기관" 표시용.
  role: "patient" | "guardian" | "organization";
  // [2026-07-22 수정] 케어하는 환자가 아직 없는 보호자는 로그인 시점엔 patientId가 없다 —
  // 이 경우까지 저장 대상에서 빠지면 "체크했는데 목록에 안 뜬다" 버그가 된다.
  patientId?: number;
  caregiverId?: number;
}

const RECENT_ACCOUNTS_KEY = "recent_accounts";
const MAX_RECENT_ACCOUNTS = 5;

export function getRecentAccounts(): RecentAccount[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_ACCOUNTS_KEY) ?? "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

/** 로그인 성공 직후(Login.tsx) 호출 — 같은 계정이 이미 있으면 맨 앞으로 갱신, 5개까지만 유지. */
export function saveRecentAccount(account: RecentAccount): void {
  const next = [account, ...getRecentAccounts().filter((a) => a.identifier !== account.identifier)].slice(
    0,
    MAX_RECENT_ACCOUNTS
  );
  localStorage.setItem(RECENT_ACCOUNTS_KEY, JSON.stringify(next));
}

export function removeRecentAccount(identifier: string): void {
  localStorage.setItem(
    RECENT_ACCOUNTS_KEY,
    JSON.stringify(getRecentAccounts().filter((a) => a.identifier !== identifier))
  );
}

/** 목록에서 계정을 클릭했을 때 — 비밀번호 없이 그 계정의 세션으로 바로 전환한다.
 * [2026-07-22 수정] access_token(60분)이 만료됐을 수 있으니 refresh_token(14일)으로 새
 * access_token을 받아온 뒤 저장한다 — refresh_token은 재사용 방지로 매번 새로 발급되므로
 * (rotation) 이 계정 항목도 새 토큰들로 갱신해서 다음 전환 때도 계속 쓸 수 있게 한다.
 * refresh_token 자체가 만료·무효화됐으면(오래돼서, 혹은 갱신 중 갱신 실패로 값이 어긋나서)
 * 여기서 예외를 던진다 — 호출부(Login.tsx)가 이 계정을 목록에서 지우고 안내해야 한다. */
export async function switchToRecentAccount(account: RecentAccount): Promise<void> {
  const refreshed = await refreshAccessToken(account.refreshToken);
  localStorage.setItem("access_token", refreshed.access_token);
  localStorage.setItem("user_name", refreshed.name);
  // [2026-07-22 수정] 케어하는 환자가 없는 보호자는 patientId가 없다 — 억지로 지우거나
  // "0"을 넣지 않고 그대로 둔다(Login.tsx가 이 값 유무로 /patients vs /dashboard를 정한다).
  if (account.patientId) localStorage.setItem("patient_id", String(account.patientId));
  else localStorage.removeItem("patient_id");
  if (account.caregiverId) localStorage.setItem("caregiver_id", String(account.caregiverId));
  else localStorage.removeItem("caregiver_id");

  saveRecentAccount({ ...account, accessToken: refreshed.access_token, refreshToken: refreshed.refresh_token });
}

/** [2026-07-21 추가] "아이디 저장" 체크박스 — 비밀번호/토큰 없이 이메일·전화번호 입력칸만
 * 다음에 미리 채워둔다("자동 로그인"보다 약한, 그냥 타이핑 한 번 줄여주는 기능). */
const REMEMBERED_IDENTIFIER_KEY = "remembered_identifier";

export function getRememberedIdentifier(): string {
  return localStorage.getItem(REMEMBERED_IDENTIFIER_KEY) ?? "";
}

export function setRememberedIdentifier(identifier: string): void {
  localStorage.setItem(REMEMBERED_IDENTIFIER_KEY, identifier);
}

export function clearRememberedIdentifier(): void {
  localStorage.removeItem(REMEMBERED_IDENTIFIER_KEY);
}

/** [2026-07-14 추가] 마이페이지 글자 크기 설정 — 컴포넌트 대부분이 rem이 아닌 고정 px로
 * 스타일링되어 있어 :root font-size만으로는 전체 화면에 적용되지 않는다. 대신 브라우저의
 * `zoom` 배율을 그대로 써서 폰트뿐 아니라 여백·아이콘까지 통째로 축소/확대한다. */
export type FontScale = "small" | "medium" | "large";
const FONT_SCALE_KEY = "font_scale";
const FONT_SCALE_ZOOM: Record<FontScale, string> = { small: "0.9", medium: "1", large: "1.15" };

export function getFontScale(): FontScale {
  const value = localStorage.getItem(FONT_SCALE_KEY);
  return value === "small" || value === "large" ? value : "medium";
}

export function applyFontScale(scale: FontScale): void {
  localStorage.setItem(FONT_SCALE_KEY, scale);
  (document.documentElement.style as CSSStyleDeclaration & { zoom?: string }).zoom = FONT_SCALE_ZOOM[scale];
}

/**
 * [7/14] Dashboard/Schedule/Notification/Connect/Check처럼 "환자 본인 로그인"과
 * "보호자 로그인"이 화면을 공유하는 곳에서, 보호자가 localStorage에 남은 옛/잘못된
 * patient_id로 엉뚱한 환자 화면에 들어가는 걸 막는다.
 * - 환자 본인 로그인이면 검증 없이 자기 자신의 id를 그대로 씀.
 * - 보호자인데 케어하는 환자가 없으면 → /patients(환자 등록)로 보냄.
 * - 케어하는 환자가 1명뿐이면 자동으로 그 환자로 진행(선택 화면 없이 바로 진입).
 * - 2명 이상인데 localStorage의 patient_id가 그중 하나가 아니면(=아직 명시적으로
 *   고른 적 없음) → /patients(환자 선택)로 보내 반드시 먼저 고르게 한다.
 * 반환값이 null이면 아직 검증 중(보호자 케이스)이거나 리다이렉트된 것 — 화면은
 * 데이터를 가져오기 전에 이 값이 채워질 때까지 기다려야 한다.
 */
export function useGuardedPatientId(): number | null {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const [patientId, setPatientId] = useState<number | null>(caregiverId ? null : getCurrentPatientId());

  useEffect(() => {
    if (!caregiverId) return;
    let cancelled = false;
    getCaregiverPatients(caregiverId)
      .then((patients) => {
        if (cancelled) return;
        if (patients.length === 0) {
          navigate("/patients", { replace: true });
          return;
        }
        // [주의] getCurrentPatientId()는 값이 없으면 1로 폴백하는데, 그 1이 우연히
        // 이 보호자의 진짜 환자 목록에 있으면 "이미 명시적으로 골랐다"고 오판하게
        // 된다 — 그래서 여기서는 폴백 없이 localStorage 원값만 그대로 확인한다.
        const stored = localStorage.getItem("patient_id");
        const current = stored ? Number(stored) : null;
        if (current !== null && patients.some((p) => p.id === current)) {
          setPatientId(current);
        } else if (patients.length === 1) {
          localStorage.setItem("patient_id", String(patients[0].id));
          setPatientId(patients[0].id);
        } else {
          navigate("/patients", { replace: true });
        }
      })
      .catch(() => navigate("/patients", { replace: true }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId]);

  return patientId;
}
