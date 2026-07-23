import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { FileText } from "lucide-react";
import NavBar from "../components/NavBar";
import { createManualRecord } from "../api/records";
import { getCurrentCaregiverId, getCurrentPatientId, getCurrentUserName } from "../lib/session";
import { C } from "../theme";

const REASONS = [
  "이미지가 흐리거나 초점이 맞지 않은 경우",
  "처방전 일부가 잘려 나간 경우",
  "조명이 너무 어둡거나 반사가 심한 경우",
  "처방전이 구겨지거나 접혀 있는 경우",
];

export default function OcrError() {
  const navigate = useNavigate();
  const location = useLocation();
  const reason = (location.state as { reason?: string } | null)?.reason;
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const startManualEntry = async () => {
    setCreating(true);
    setError("");
    try {
      const record = await createManualRecord(getCurrentPatientId(), getCurrentCaregiverId() ?? undefined);
      navigate(`/records/${record.record_id}/review`);
    } catch {
      setError("직접 입력을 시작하지 못했어요. 잠시 후 다시 시도해 주세요.");
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <div className="flex-1 flex flex-col items-center justify-center px-8 py-16">
      <div className="w-full max-w-md text-center">
        <div
          className="w-24 h-24 rounded-3xl flex items-center justify-center mx-auto mb-7"
          style={{ background: `${C.terracotta}10` }}
        >
          <FileText className="w-12 h-12" style={{ color: `${C.terracotta}70` }} />
        </div>
        <h1 className="text-[28px] font-black mb-3" style={{ color: C.dark }}>처방전을 인식하지 못했어요</h1>
        <p className="text-[15px] leading-relaxed mb-8" style={{ color: C.muted }}>
          {reason ?? "사진이 흐리거나 잘린 경우 인식이 어려울 수 있어요."}
          <br />아래 방법으로 다시 시도해보세요.
        </p>
        <div className="rounded-2xl p-5 mb-8 text-left" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          <p className="text-[12px] font-black mb-3 uppercase tracking-widest" style={{ color: C.muted }}>실패 가능 원인</p>
          {REASONS.map((r) => (
            <div key={r} className="flex items-start gap-2.5 mb-2.5 last:mb-0">
              <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: C.terracottaLight }} />
              <p className="text-[13px]" style={{ color: C.dark }}>{r}</p>
            </div>
          ))}
        </div>
        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        <div className="flex flex-col gap-3">
          <button
            onClick={() => navigate("/upload")}
            className="w-full py-4 rounded-full text-white font-bold text-[17px] hover:opacity-85 transition-opacity"
            style={{ background: C.terracotta }}
          >
            다시 업로드하기
          </button>
          <button
            onClick={startManualEntry}
            disabled={creating}
            className="w-full py-4 rounded-full font-bold text-[17px] border-2 transition-colors hover:bg-black/[0.02] disabled:opacity-50"
            style={{ borderColor: "rgba(30,26,23,0.2)", color: C.dark }}
          >
            {creating ? "준비하는 중..." : "직접 입력하기"}
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}
