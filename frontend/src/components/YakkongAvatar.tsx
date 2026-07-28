import yakkongMascot from "../assets/yakkong-mascot.png";
import { C } from "../theme";

// [2026-07-28 변경] 챗봇 "약콩이" 아이콘 — 직접 그린 SVG 대신, 무료 라이선스 아이콘
// 사이트에서 받은 완두콩 PNG를 그대로 사용한다(사용자 요청). 배경은 흰 원으로 둬서
// 이미지의 투명 배경 위에서도 또렷하게 보이게 함.
// 출처(Magnific · Flaticon) 표기는 Settings.tsx(화면·챗봇 설정)에 남겨뒀다.
export default function YakkongAvatar({ size = 36 }: { size?: number }) {
  return (
    <div
      className="rounded-full flex items-center justify-center shrink-0"
      style={{ width: size, height: size, background: C.white, border: "1px solid rgba(30,26,23,0.08)" }}
    >
      <img src={yakkongMascot} alt="약콩이" style={{ width: size * 0.78, height: size * 0.78 }} />
    </div>
  );
}
