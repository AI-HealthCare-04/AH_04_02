import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Heart, Check, X } from "lucide-react";
import NavBar from "../components/NavBar";
import { acceptInvitation, getInvitation, rejectInvitation, type InvitationInfo } from "../api/care";

const RELATION_LABEL: Record<string, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

export default function InviteAccept() {
  const navigate = useNavigate();
  const { token } = useParams<{ token: string }>();

  const [invite, setInvite] = useState<InvitationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [caregiverName, setCaregiverName] = useState("");
  const [decided, setDecided] = useState<"accepted" | "rejected" | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) return;
    getInvitation(token)
      .then((data) => {
        setInvite(data);
        if (data.status !== "pending") {
          setDecided(data.status === "accepted" ? "accepted" : "rejected");
        }
      })
      .catch(() => setError("유효하지 않거나 만료된 초대예요."))
      .finally(() => setLoading(false));
  }, [token]);

  const handleAccept = async () => {
    if (!token || !caregiverName.trim()) return;
    setSubmitting(true);
    try {
      const result = await acceptInvitation(token, { caregiver_name: caregiverName.trim() });
      localStorage.setItem("caregiver_id", String(result.caregiver_id));
      localStorage.setItem("patient_id", String(result.patient_id));
      setDecided("accepted");
    } catch {
      setError("수락 처리에 실패했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!token) return;
    setSubmitting(true);
    try {
      await rejectInvitation(token);
      setDecided("rejected");
    } catch {
      setError("거절 처리에 실패했어요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF6F1]">
      <NavBar />
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        {loading ? (
          <p className="text-[14px] text-[#8A7E75]">불러오는 중이에요...</p>
        ) : error && !invite ? (
          <div className="rounded-3xl p-10 w-full max-w-md text-center bg-white shadow-lg">
            <p className="text-[15px] text-[#D94F4F]">{error}</p>
          </div>
        ) : decided ? (
          <div className="rounded-3xl p-10 w-full max-w-md text-center bg-white shadow-lg">
            <div
              className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-5 ${
                decided === "accepted" ? "bg-[#8FAE8B]/20" : "bg-[rgba(30,26,23,0.06)]"
              }`}
            >
              {decided === "accepted" ? (
                <Check className="w-8 h-8 text-[#8FAE8B]" />
              ) : (
                <X className="w-8 h-8 text-[#8A7E75]" />
              )}
            </div>
            <h2 className="text-[22px] font-black text-[#1E1A17] mb-2">
              {decided === "accepted" ? "초대를 수락했어요!" : "초대를 거절했어요"}
            </h2>
            <p className="text-[14px] text-[#8A7E75] mb-6">
              {decided === "accepted"
                ? `이제 ${invite?.patient_name ?? ""}님의 복약 관리를 함께할 수 있어요.`
                : "언제든지 다시 초대받을 수 있어요."}
            </p>
            {decided === "accepted" && (
              <button
                onClick={() => navigate("/dashboard")}
                className="w-full py-3.5 rounded-full text-white font-bold text-[15px] bg-[#C1653D]"
              >
                대시보드로 이동
              </button>
            )}
          </div>
        ) : (
          invite && (
            <div className="rounded-3xl p-8 sm:p-10 w-full max-w-md bg-white shadow-lg text-center">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6 bg-[#C1653D]/12">
                <Heart className="w-8 h-8 text-[#C1653D]" />
              </div>
              <p className="text-[13px] font-bold text-[#8A7E75] mb-2">
                {RELATION_LABEL[invite.relation_type] ?? invite.relation_type} 초대
              </p>
              <h1 className="text-[24px] font-black text-[#1E1A17] mb-7 leading-snug">
                {invite.patient_name}님을<br />
                {RELATION_LABEL[invite.relation_type] ?? invite.relation_type}로 돌보게 돼요
              </h1>

              <div className="rounded-2xl p-5 mb-6 bg-[#F4F0EA] text-left space-y-2.5">
                <div className="flex justify-between text-[13px]">
                  <span className="text-[#8A7E75]">대상자</span>
                  <span className="font-bold text-[#1E1A17]">{invite.patient_name}</span>
                </div>
                {invite.inviter_name && (
                  <div className="flex justify-between text-[13px]">
                    <span className="text-[#8A7E75]">초대한 사람</span>
                    <span className="font-bold text-[#1E1A17]">{invite.inviter_name}</span>
                  </div>
                )}
              </div>

              <input
                value={caregiverName}
                onChange={(e) => setCaregiverName(e.target.value)}
                placeholder="본인 이름을 입력해 주세요"
                className="w-full px-4 py-3.5 mb-5 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
              />
              {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

              <div className="flex gap-3">
                <button
                  onClick={handleReject}
                  disabled={submitting}
                  className="flex-1 py-3.5 rounded-full font-bold text-[15px] border-2 border-[rgba(30,26,23,0.15)] text-[#1E1A17] disabled:opacity-60"
                >
                  거절
                </button>
                <button
                  onClick={handleAccept}
                  disabled={submitting || !caregiverName.trim()}
                  className="flex-1 py-3.5 rounded-full font-bold text-[15px] text-white bg-[#C1653D] disabled:opacity-50"
                >
                  수락
                </button>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
