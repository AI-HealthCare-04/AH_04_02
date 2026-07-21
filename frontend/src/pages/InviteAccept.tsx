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
  patient: "환자",
};

/** "2025.07.09 오전 10:00" 형식 — Figma 목업(App.figma-export.tsx.bak) 참고 */
function formatExpiry(iso: string): string {
  const d = new Date(iso);
  const date = `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
  const time = d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit", hour12: true });
  return `${date} ${time}`;
}

export default function InviteAccept() {
  const navigate = useNavigate();
  const { token } = useParams<{ token: string }>();

  const [invite, setInvite] = useState<InvitationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [caregiverName, setCaregiverName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [decided, setDecided] = useState<"accepted" | "rejected" | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // 보호자→환자 초대(REQ-037): 수락자가 실제 환자 계정을 만드는 흐름
  const isPatientInvite = invite?.relation_type === "patient";
  // [2026-07-22 추가] "환자→보호자 초대"(Connect.tsx)는 대부분 환자 본인이 직접 보내서
  // inviter_name(보호자 초대자)이 없다 — 그 경우 환자 자신의 이름을 "초대한 사람"으로 보여준다.
  const inviterDisplayName = invite?.inviter_name ?? invite?.patient_name;

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
    if (!token) return;

    if (isPatientInvite) {
      if (!caregiverName.trim()) return;
      setSubmitting(true);
      try {
        const result = await acceptInvitation(token, {
          patient_name: caregiverName.trim(),
          patient_email: email.trim() || undefined,
          patient_password: password.trim() || undefined,
          patient_phone: phone.trim() || undefined,
        });
        // 환자 본인 계정을 만든 것이므로 patient_id만 저장한다(보호자 계정 아님).
        localStorage.setItem("patient_id", String(result.patient_id));
        setDecided("accepted");
      } catch {
        setError("가입 처리에 실패했어요. 입력한 정보를 확인해 주세요.");
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!caregiverName.trim()) return;
    if (invite?.phone_verification_required && !phone.trim()) return;
    setSubmitting(true);
    try {
      const result = await acceptInvitation(token, {
        caregiver_name: caregiverName.trim(),
        phone: phone.trim() || undefined,
      });
      localStorage.setItem("caregiver_id", String(result.caregiver_id));
      localStorage.setItem("patient_id", String(result.patient_id));
      setDecided("accepted");
    } catch {
      setError(
        invite?.phone_verification_required
          ? "수락 처리에 실패했어요. 초대받은 전화번호를 정확히 입력했는지 확인해 주세요."
          : "수락 처리에 실패했어요."
      );
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
                ? isPatientInvite
                  ? "계정이 만들어졌어요. 이제 복약 관리를 시작할 수 있어요."
                  : `이제 ${invite?.patient_name ?? ""}님의 복약 관리를 함께할 수 있어요.`
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
                {isPatientInvite
                  ? "환자 연결 초대"
                  : `${RELATION_LABEL[invite.relation_type] ?? invite.relation_type} 초대`}
              </p>
              <h1 className="text-[24px] font-black text-[#1E1A17] mb-7 leading-snug">
                {isPatientInvite ? (
                  <>
                    복약 관리를 함께할<br />
                    계정을 만들어요
                  </>
                ) : (
                  <>
                    {inviterDisplayName}님이<br />
                    {RELATION_LABEL[invite.relation_type] ?? invite.relation_type}로 초대했어요
                  </>
                )}
              </h1>

              <div className="rounded-2xl p-5 mb-6 bg-[#F4F0EA] text-left space-y-2.5">
                <div className="flex justify-between text-[13px]">
                  <span className="text-[#8A7E75]">초대한 사람</span>
                  <span className="font-bold text-[#1E1A17]">{inviterDisplayName}</span>
                </div>
                {/* [2026-07-22 추가] "관계"/"초대 만료"는 환자→보호자 초대에만 표시 —
                    보호자→환자 초대는 아직 계정이 없는 사람에게 보내는 가입 초대라
                    관계·만료 개념이 덜 중요해서 Figma 목업에도 안 나온다. */}
                {!isPatientInvite && (
                  <>
                    <div className="flex justify-between text-[13px]">
                      <span className="text-[#8A7E75]">관계</span>
                      <span className="font-bold text-[#1E1A17]">
                        {RELATION_LABEL[invite.relation_type] ?? invite.relation_type}
                      </span>
                    </div>
                    <div className="flex justify-between text-[13px]">
                      <span className="text-[#8A7E75]">초대 만료</span>
                      <span className="font-bold text-[#1E1A17]">{formatExpiry(invite.expires_at)}</span>
                    </div>
                  </>
                )}
              </div>

              {isPatientInvite ? (
                <>
                  <input
                    value={caregiverName}
                    onChange={(e) => setCaregiverName(e.target.value)}
                    placeholder="이름을 입력해 주세요"
                    className="w-full px-4 py-3.5 mb-3 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                  />
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    type="email"
                    placeholder="이메일 (로그인 아이디) — 선택"
                    className="w-full px-4 py-3.5 mb-3 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                  />
                  <input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    type="password"
                    placeholder="비밀번호 — 선택"
                    className="w-full px-4 py-3.5 mb-3 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                  />
                  <input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="전화번호 (010-0000-0000) — 선택"
                    className="w-full px-4 py-3.5 mb-5 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                  />
                </>
              ) : (
                <>
                  <input
                    value={caregiverName}
                    onChange={(e) => setCaregiverName(e.target.value)}
                    placeholder="본인 이름을 입력해 주세요"
                    className="w-full px-4 py-3.5 mb-5 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                  />
                  {invite.phone_verification_required && (
                    <>
                      <input
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="초대받은 전화번호를 입력해 주세요"
                        className="w-full px-4 py-3.5 mb-2 rounded-xl border border-[rgba(30,26,23,0.12)] text-[15px] outline-none"
                      />
                      <p className="text-[12px] text-[#8A7E75] mb-5 text-left">
                        이 초대는 특정 전화번호로 발송됐어요. 본인 확인을 위해 그 번호를 입력해 주세요.
                      </p>
                    </>
                  )}
                </>
              )}
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
                  disabled={submitting || !caregiverName.trim() || (invite.phone_verification_required && !phone.trim())}
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
