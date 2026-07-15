import { useLocation, useNavigate } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import { isLoggedIn } from "../lib/session";
import { C } from "../theme";

/** [2026-07-14 추가] 어느 화면에서든 챗봇으로 바로 갈 수 있는 우측 하단 플로팅 버튼.
 * 챗봇 화면 자체와 비로그인 상태(/chat이 인증을 요구해 401→로그인 리다이렉트되므로)에서는 숨긴다. */
export default function ChatFab() {
  const navigate = useNavigate();
  const location = useLocation();

  if (location.pathname === "/chat" || !isLoggedIn()) return null;

  return (
    <button
      onClick={() => navigate("/chat")}
      aria-label="챗봇 열기"
      className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center transition-transform hover:scale-105"
      style={{ background: C.terracotta, boxShadow: "0 4px 16px rgba(30,26,23,0.25)" }}
    >
      <MessageCircle className="w-7 h-7" color={C.white} strokeWidth={2} />
    </button>
  );
}
