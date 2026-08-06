import { createPortal } from "react-dom";
import type { LucideIcon } from "lucide-react";
import { C } from "../theme";

/**
 * [2026-07-30 추가] 인라인 에러 텍스트로는 놓치기 쉬운 안내(예: "이미 연결된 사용자입니다")를
 * 화면 중앙 팝업으로 확실히 보여준다. PrescriptionImageViewer.tsx의 포탈 모달과 동일한
 * 패턴(document.body에 portal + 배경 클릭으로 닫기)을 재사용한다.
 *
 * [2026-08-03 추가] title/icon은 선택 — 완료 안내처럼 제목+본문으로 나눠 보여주고 싶을 때만
 * 쓴다. 안 넘기면 기존처럼 message 한 줄짜리 안내(예: 에러 메시지)로 그대로 동작한다.
 */
export default function InfoModal({
  open,
  title,
  message,
  icon: Icon,
  iconColor = C.terracotta,
  onClose,
}: {
  open: boolean;
  title?: string;
  message: string;
  icon?: LucideIcon;
  iconColor?: string;
  onClose: () => void;
}) {
  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-5"
      style={{ background: "rgba(30,26,23,0.45)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl p-7 text-center"
        style={{ background: C.surface, boxShadow: C.shadowDropdown }}
        onClick={(e) => e.stopPropagation()}
      >
        {Icon && (
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: `${iconColor}15` }}
          >
            <Icon className="w-6 h-6" style={{ color: iconColor }} />
          </div>
        )}
        {title && (
          <p className="text-[17px] font-black mb-2" style={{ color: C.dark }}>
            {title}
          </p>
        )}
        <p
          className={
            title
              ? "text-[14px] leading-relaxed mb-6 whitespace-pre-line"
              : "text-[15px] font-bold leading-relaxed mb-5 whitespace-pre-line"
          }
          style={{ color: title ? C.muted : C.dark }}
        >
          {message}
        </p>
        <button
          onClick={onClose}
          className="w-full py-3 rounded-full text-white font-bold text-[15px]"
          style={{ background: C.terracotta }}
        >
          확인
        </button>
      </div>
    </div>,
    document.body
  );
}
