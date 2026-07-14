// 건강동행 공용 디자인 토큰 — NavBar.tsx/Chat.tsx에 흩어져 있던 hex 값을 한 곳으로 모았습니다.
// 앞으로 새 화면 만들 때 색상은 여기서 가져다 쓰세요.
//
// ⚠️ 정리하면서 통일한 값 (기존에 파일마다 다르게 쓰던 것들, 눈에 띄지 않을 정도로 미세한 차이):
//   - 진한 텍스트: NavBar #1E1A17 vs Chat #2A2A2A → #1E1A17로 통일
//   - 보조 텍스트: NavBar #8A7E75 vs Chat #888888 → #8A7E75로 통일

export const C = {
  terracotta: "#C1653D",
  terracottaLight: "#E08A5B",
  ivory: "#FAF6F1",
  white: "#FFFFFF",
  dark: "#1E1A17",
  muted: "#8A7E75",
  bubbleBg: "#F4F0EA",
  success: "#8FAE8B",
  successText: "#4A7A47", // success(#8FAE8B)는 작은 텍스트엔 대비가 약해서, 흰 배경 위 텍스트는 이 진한 초록을 씀
  danger: "#D94F4F",
  warningBg: "rgba(224, 138, 91, 0.10)",
  warningBorder: "rgba(224, 138, 91, 0.25)",
  warningText: "#7A4B28",
} as const;
