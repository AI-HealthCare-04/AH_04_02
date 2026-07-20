import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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
