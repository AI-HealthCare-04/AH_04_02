import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { C } from "../theme";

export default function Select() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen" style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}>
      <NavBar />
      <main className="mx-auto max-w-[900px] px-6 py-10 sm:py-[60px]">
        <div className="mb-10 sm:mb-12 text-center">
          <h1 className="text-[24px] sm:text-[28px] font-bold mb-3" style={{ color: C.dark }}>어떤 방식으로 이용하시나요?</h1>
          <p className="text-[15px]" style={{ color: C.muted }}>선택에 따라 화면 글씨 크기와 입력 방식이 달라집니다.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 mb-10 sm:mb-12">
          <div
            className="flex-1 rounded-2xl border-2 px-6 py-7 sm:px-7 sm:py-9 cursor-pointer transition-all"
            style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)" }}
            onClick={() => navigate("/upload")}
          >
            <div className="text-[40px] mb-4">👴</div>
            <h2 className="text-[18px] font-bold mb-2" style={{ color: C.dark }}>어르신 본인이 직접 이용</h2>
            <p className="text-[13px] font-semibold mb-3" style={{ color: C.terracotta }}>큰 글씨 모드</p>
            <p className="text-[14px] leading-relaxed mb-4" style={{ color: C.muted }}>버튼과 글씨를 크게 보여드리고, 핵심 중심으로 안내해요.</p>
            <div className="flex flex-wrap gap-2">
              <span className="text-[12px] px-2.5 py-[3px] rounded-full" style={{ background: C.bubbleBg, color: C.terracotta }}>대화형 목록</span>
              <span className="text-[12px] px-2.5 py-[3px] rounded-full" style={{ background: C.bubbleBg, color: C.terracotta }}>자동경력채우기</span>
            </div>
          </div>
          <div
            className="flex-1 rounded-2xl border-2 px-6 py-7 sm:px-7 sm:py-9 cursor-pointer transition-all"
            style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)" }}
            onClick={() => navigate("/connect")}
          >
            <div className="text-[40px] mb-4">👨‍👩‍👧</div>
            <h2 className="text-[18px] font-bold mb-2" style={{ color: C.dark }}>보호자·요양보호사가 대신 이용</h2>
            <p className="text-[13px] font-semibold mb-3" style={{ color: C.terracotta }}>일반 모드 + 대리 입력</p>
            <p className="text-[14px] leading-relaxed mb-4" style={{ color: C.muted }}>업로드/입력은 보호자/요양보호사가 진행하고 어르신이 확인하기 쉽게 정리해요.</p>
            <div className="flex flex-wrap gap-2">
              <span className="text-[12px] px-2.5 py-[3px] rounded-full" style={{ background: C.bubbleBg, color: C.terracotta }}>대리입력 표시</span>
              <span className="text-[12px] px-2.5 py-[3px] rounded-full" style={{ background: C.bubbleBg, color: C.terracotta }}>어르신 연결 등록</span>
            </div>
          </div>
        </div>
        <div className="flex justify-center">
          <button
            className="px-8 py-3 text-[15px] rounded-[10px] border-[1.5px] cursor-pointer"
            style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)", color: C.muted }}
            onClick={() => navigate("/")}
          >이전</button>
        </div>
      </main>
    </div>
  );
}
