import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { forgetSwitchAccount, switchAccount } from "../api/auth";
import { getCaregiverPatients } from "../api/monitoring";

/**
 * 로그인이 없어서 "지금 보고 있는 환자/보호자가 누구인지"를 localStorage로 관리합니다.
 * Login.tsx에서 보호자·환자 선택 시 이 값들을 저장합니다.
 */
/** [2026-07-23 수정] localStorage에 patient_id가 없으면 1번 환자로 조용히 폴백하던
 * 걸 제거했다 — 이 저장소의 최초 커밋 때부터 있던 스캐폴딩이었는데, 이 폴백을 거치지
 * 않는 화면(Records/MonitoringDayLogs/Chat/MedGuideList/DrugDetail 등)에서 patient_id가
 * 없으면 엉뚱한 1번 환자 데이터를 그대로 보여주는 문제가 있었다. 반환 타입을
 * `number | null`로 바꿔 호출부가 컴파일 타임에 null 처리를 하도록 강제한다. */
export function getCurrentPatientId(): number | null {
  const value = localStorage.getItem("patient_id");
  return value ? Number(value) : null;
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
 * [2026-07-22 재설계 — 팀원 리뷰(fkmc10101-hub) 지적 반영, HIGH] 처음엔 access_token(60분)
 * 뿐 아니라 refresh_token(14일)까지 이 객체에 담아 localStorage에 그대로 저장했다 — XSS
 * 한 번으로 저장된 계정 전부의 refresh_token(14일)이 털릴 수 있는 회귀였다. 이제 이
 * 객체는 화면 표시용 정보만 담고(누구인지 보여주는 데는 필요하지만 그 자체로는 아무
 * 권한도 없음), 실제 재로그인 능력은 서버의 httpOnly 쿠키(switch_{role}_{subject_id})에만
 * 있다 — switchAccount()/forgetSwitchAccount()가 role+subject_id만 넘겨 그 쿠키를
 * 간접적으로 다룬다.
 */
export interface RecentAccount {
  identifier: string; // 로그인에 쓴 이메일/전화번호 — 계정 식별 및 표시용
  name: string;
  // [2026-07-22 추가] 계정 전환 목록에 "환자 본인/보호자/기관" 표시용.
  role: "patient" | "guardian" | "organization";
  // [2026-07-22 수정] 케어하는 환자가 아직 없는 보호자는 로그인 시점엔 patientId가 없다 —
  // 이 경우까지 저장 대상에서 빠지면 "체크했는데 목록에 안 뜬다" 버그가 된다.
  patientId?: number;
  caregiverId?: number;
}

/** switchAccount/forgetSwitchAccount가 서버에 넘길 "어느 계정인지"만 가리키는 슬롯
 * 식별자 — role은 서버 쪽 role("caregiver"/"patient")과 맞춰야 하므로 guardian/organization을
 * "caregiver"로 합친다(둘 다 Caregiver 테이블이므로 서버 입장에선 동일한 role이다). */
function toServerSlot(account: RecentAccount): { role: "caregiver" | "patient"; subjectId: number } | null {
  if (account.role === "patient") {
    return account.patientId != null ? { role: "patient", subjectId: account.patientId } : null;
  }
  return account.caregiverId != null ? { role: "caregiver", subjectId: account.caregiverId } : null;
}

const RECENT_ACCOUNTS_KEY = "recent_accounts";
const MAX_RECENT_ACCOUNTS = 5;

/** [2026-07-22 추가, 팀원 리뷰 반영 — MEDIUM] 전화번호가 이제 역할당 유니크라 같은
 * identifier(전화번호)로 환자 본인/보호자/기관 계정을 각각 가질 수 있다 — identifier만으로
 * 구분하면 같은 전화번호의 서로 다른 역할 계정이 이 목록에서 서로를 덮어썼다. 실제 계정을
 * 가리키는 id(역할별 patientId/caregiverId)로 구분한다. 이 필드들이 아직 없는 아주 오래된
 * 저장값(기능 추가 이전)만 identifier로 폴백한다. */
function accountKey(account: RecentAccount): string {
  if (account.role === "patient" && account.patientId != null) return `patient:${account.patientId}`;
  if (account.caregiverId != null) return `${account.role ?? "guardian"}:${account.caregiverId}`;
  return `identifier:${account.identifier}`;
}

/** [2026-07-22 추가, 팀원 리뷰(fkmc10101-hub) 지적 반영] 이 PR 이전 버전(PR#66)이 저장해둔
 * 항목엔 accessToken/refreshToken이 그대로 남아있을 수 있다 — 이 함수 자체는 그 필드를
 * 더 이상 안 쓰지만, 필드가 여전히 localStorage에 남아있으면 XSS로 읽힐 수 있는 건
 * 마찬가지다. 읽을 때마다 지우고, 지운 값을 즉시 다시 저장해 자체 치유(self-heal)한다. */
function stripLegacyTokenFields(raw: unknown[]): RecentAccount[] {
  return raw.map((entry) => {
    if (entry && typeof entry === "object") {
      const { accessToken: _accessToken, refreshToken: _refreshToken, ...rest } = entry as Record<string, unknown>;
      return rest as unknown as RecentAccount;
    }
    return entry as RecentAccount;
  });
}

export function getRecentAccounts(): RecentAccount[] {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENT_ACCOUNTS_KEY) ?? "[]");
    if (!Array.isArray(raw)) return [];
    const hadLegacyFields = raw.some((entry) => entry && ("accessToken" in entry || "refreshToken" in entry));
    const cleaned = stripLegacyTokenFields(raw);
    if (hadLegacyFields) localStorage.setItem(RECENT_ACCOUNTS_KEY, JSON.stringify(cleaned));
    return cleaned;
  } catch {
    return [];
  }
}

/** 로그인 성공 직후(Login.tsx) 호출 — 같은 계정이 이미 있으면 맨 앞으로 갱신, 5개까지만 유지. */
export function saveRecentAccount(account: RecentAccount): void {
  const key = accountKey(account);
  const next = [account, ...getRecentAccounts().filter((a) => accountKey(a) !== key)].slice(0, MAX_RECENT_ACCOUNTS);
  localStorage.setItem(RECENT_ACCOUNTS_KEY, JSON.stringify(next));
}

/** [2026-07-22 수정] localStorage에서 지우는 것뿐 아니라, 서버에 심어둔 전환용 httpOnly
 * 쿠키도 같이 지워달라고 요청한다(fire-and-forget — 실패해도 목록에서는 어차피 지운다). */
export function removeRecentAccount(account: RecentAccount): void {
  const key = accountKey(account);
  localStorage.setItem(
    RECENT_ACCOUNTS_KEY,
    JSON.stringify(getRecentAccounts().filter((a) => accountKey(a) !== key))
  );
  const slot = toServerSlot(account);
  if (slot) forgetSwitchAccount(slot.role, slot.subjectId).catch(() => {});
}

/** 목록에서 계정을 클릭했을 때 — 비밀번호 없이 그 계정의 세션으로 바로 전환한다.
 * [2026-07-22 재설계 — 팀원 리뷰 반영, HIGH] refresh_token을 이 함수(또는 localStorage)가
 * 직접 다루지 않는다 — role+subject_id만 서버에 넘기면, 서버가 그 계정 전용 httpOnly
 * 쿠키를 직접 읽어 검증·회전하고 새 access_token만 돌려준다. 그 쿠키가 없거나 만료·
 * 무효화됐으면 여기서 예외를 던진다 — 호출부(Login.tsx)가 이 계정을 목록에서 지우고
 * 안내해야 한다. */
export async function switchToRecentAccount(account: RecentAccount): Promise<void> {
  const slot = toServerSlot(account);
  if (!slot) throw new Error("전환할 수 없는 계정이에요.");
  const result = await switchAccount(slot.role, slot.subjectId);
  localStorage.setItem("access_token", result.access_token);
  localStorage.setItem("user_name", result.name);
  // [2026-07-22 수정] 케어하는 환자가 없는 보호자는 patientId가 없다 — 억지로 지우거나
  // "0"을 넣지 않고 그대로 둔다(Login.tsx가 이 값 유무로 /patients vs /dashboard를 정한다).
  if (account.patientId) localStorage.setItem("patient_id", String(account.patientId));
  else localStorage.removeItem("patient_id");
  if (account.caregiverId) localStorage.setItem("caregiver_id", String(account.caregiverId));
  else localStorage.removeItem("caregiver_id");

  saveRecentAccount({ ...account, name: result.name });
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
 *
 * [2026-07-23 추가] `silent: true`를 주면 환자를 특정할 수 없어도(케어하는 환자가 0명이거나
 * 아직 고르지 않은 2명 이상) `/patients`로 강제 이동시키지 않고 그냥 null을 반환한다.
 * Settings.tsx처럼 화면 일부만 환자 단위 데이터(챗봇 이름)이고 나머지(글자 크기)는
 * 환자와 무관해서, 환자가 아직 안 정해졌다고 화면 전체를 떠나보내면 안 되는 경우에 쓴다.
 */
export function useGuardedPatientId(options?: { silent?: boolean }): number | null {
  const silent = options?.silent ?? false;
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
          if (!silent) navigate("/patients", { replace: true });
          return;
        }
        const stored = localStorage.getItem("patient_id");
        const current = stored ? Number(stored) : null;
        if (current !== null && patients.some((p) => p.id === current)) {
          setPatientId(current);
        } else if (patients.length === 1) {
          localStorage.setItem("patient_id", String(patients[0].id));
          setPatientId(patients[0].id);
        } else if (!silent) {
          navigate("/patients", { replace: true });
        }
      })
      .catch(() => {
        if (cancelled) return;
        if (!silent) navigate("/patients", { replace: true });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId, silent]);

  return patientId;
}
