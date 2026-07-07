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
