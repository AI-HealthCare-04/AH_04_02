import type { CSSProperties } from "react";

// [2026-07-28 추가] "불러오는 중이에요" 텍스트 한 줄이 실제 콘텐츠보다 훨씬 짧아서,
// 로딩이 끝나는 순간 레이아웃이 아래로 크게 점프하던 문제 — 실제 콘텐츠와 비슷한
// 높이의 자리표시자를 보여줘서 그 점프를 없앤다. 폭/높이/모양은 className으로 페이지마다 맞춘다.
export default function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <div className={`animate-pulse rounded-xl ${className}`} style={{ background: "rgba(30,26,23,0.08)", ...style }} />;
}
