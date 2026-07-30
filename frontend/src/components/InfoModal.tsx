import { createPortal } from "react-dom";
import { C } from "../theme";

/**
 * [2026-07-30 추가] 인라인 에러 텍스트로는 놓치기 쉬운 안내(예: "이미 연결된 사용자입니다")를
 * 화면 중앙 팝업으로 확실히 보여준다. PrescriptionImageViewer.tsx의 포탈 모달과 동일한
 * 패턴(document.body에 portal + 배경 클릭으로 닫기)을 재사용한다.
 */
export default function InfoModal({
  open,
  message,
  onClose,
}: {
  open: boolean;
  message: string;
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
        className="w-full max-w-sm rounded-2xl p-6 text-center"
        style={{ background: C.surface, boxShadow: C.shadowDropdown }}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-[15px] font-bold mb-5" style={{ color: C.dark }}>
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
