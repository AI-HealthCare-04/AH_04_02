import { useNavigate } from "react-router-dom";
import { C } from "../theme";

/**
 * [7/8 추가] 등록되지 않은 경로로 들어왔을 때 안내 화면.
 * 이게 없으면 매칭되는 <Route>가 없어 그냥 흰 화면만 뜨는데, 그 상태로는
 * 어떤 링크가 잘못됐는지 파악하기 어려워서 최소한의 안내 + 홈 이동 버튼을 둡니다.
 */
export default function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6" style={{ background: C.ivory }}>
      <p className="text-[15px] mb-2" style={{ color: C.muted }}>페이지를 찾을 수 없어요</p>
      <p className="text-[13px] mb-7" style={{ color: C.muted }}>주소가 잘못됐거나 아직 연결되지 않은 화면이에요.</p>
      <button
        onClick={() => navigate("/")}
        className="px-6 py-3 rounded-full font-bold text-[14px] text-white"
        style={{ background: C.terracotta }}
      >
        홈으로 가기
      </button>
    </div>
  );
}
