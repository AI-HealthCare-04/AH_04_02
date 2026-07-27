import { C } from "../theme";

// [2026-07-25 추가] "불러오는 중이에요..." 정적 텍스트가 화면이 멈춘 것처럼 보인다는
// 피드백 — 어느 계정(환자/보호자/기관)이든 데이터를 불러오는 동안 보이는 텍스트는 전부
// 이걸로 통일한다. 텍스트 아래에 주황색 점 3개가 튀는 걸 보여준다(inline-flex라
// <p> 안에 넣어도 안전). 색은 각 페이지 wrapper의 글자색과 무관하게 항상 주황 고정.
export default function LoadingDots({ label = "불러오는 중이에요" }: { label?: string }) {
  return (
    <span className="inline-flex flex-col items-center gap-2">
      <span className="text-[20px] font-semibold">{label}</span>
      <span className="inline-flex items-end gap-1.5 h-3">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="loading-dot w-2 h-2 rounded-full"
            style={{ background: C.terracotta, animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
    </span>
  );
}
