import type { LucideIcon } from "lucide-react";
import { useId } from "react";
import { C } from "../theme";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

// [2026-07-27 변경] 아이콘 칩을 단색 터라코타 원 대신, 약콩이 마스코트와 같은 대각선
// 두 톤 초록(clipPath 하이라이트)으로 통일 — 콩 캐릭터 등장 이후 "밝고 귀여운" 톤이
// 빈 상태 화면에도 이어지도록. 버튼 등 나머지 강조색은 그대로 터라코타를 씀.
export default function EmptyState({ icon: Icon, title, description, actionLabel, onAction }: EmptyStateProps) {
  const clipId = useId();
  return (
    <div className="rounded-2xl p-10 text-center" style={{ background: C.surface, boxShadow: C.shadowCard }}>
      <div className="w-12 h-12 mx-auto mb-4 relative flex items-center justify-center">
        <svg viewBox="0 0 48 48" className="absolute inset-0 w-full h-full">
          <defs>
            <clipPath id={clipId}>
              <circle cx="24" cy="24" r="23" />
            </clipPath>
          </defs>
          <circle cx="24" cy="24" r="23" fill="#8FAE5C" stroke="#1E1A17" strokeWidth="1.4" />
          <g clipPath={`url(#${clipId})`}>
            <rect x="0" y="0" width="30" height="48" fill="#C8DA6F" transform="rotate(-36 17 24)" />
          </g>
        </svg>
        <Icon className="w-6 h-6 relative" style={{ color: C.white }} strokeWidth={2.2} />
      </div>
      <p className="text-[15px] font-bold mb-1" style={{ color: C.dark }}>{title}</p>
      {description && (
        <p className="text-[13px] mb-4" style={{ color: C.muted }}>{description}</p>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-1 px-6 py-3 rounded-full font-bold text-[14px] text-white"
          style={{ background: C.terracotta }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
