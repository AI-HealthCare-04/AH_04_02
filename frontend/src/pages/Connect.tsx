import { useEffect, useState } from "react";
import { Phone, User, AlertCircle } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import NavBar from "../components/NavBar";
import InvitePatientPanel, { buildSmsHref } from "../components/InvitePatientPanel";
import {
  createInvitation,
  listInvitations,
  type InvitationSummary,
} from "../api/care";
import { getPatientCaregivers, unlinkCaregiverPatient, type Caregiver } from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentUserName, useGuardedPatientId } from "../lib/session";

type RelationType = "guardian" | "caregiver" | "life_support_worker" | "social_worker";

const RELATION_LABEL: Record<RelationType, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

export default function Connect() {
  const patientId = useGuardedPatientId();
  // 보호자류 로그인이면(값이 있으면) "환자 연결하기" 패널을 추가로 보여준다.
  const caregiverId = getCurrentCaregiverId();

  const [phone, setPhone] = useState("");
  const [relationType, setRelationType] = useState<RelationType>("guardian");
  const [inviteMethod, setInviteMethod] = useState<"sms" | "url" | "qr">("sms");
  const [inviteUrl, setInviteUrl] = useState("");
  const [urlCopied, setUrlCopied] = useState(false);
  const [sending, setSending] = useState(false);

  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [invitations, setInvitations] = useState<InvitationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadConnections = async (pid: number) => {
    try {
      const [caregiverList, invitationList] = await Promise.all([
        getPatientCaregivers(pid),
        listInvitations(pid),
      ]);
      setCaregivers(caregiverList);
      setInvitations(invitationList.filter((inv) => inv.status === "pending"));
    } catch {
      setError("연결 정보를 불러오지 못했어요.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (patientId == null) return;
    loadConnections(patientId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  const handleInvite = async () => {
    if (patientId == null) return;
    setSending(true);
    setError("");
    try {
      const created = await createInvitation({
        patient_id: patientId,
        relation_type: relationType,
        invited_phone: phone || undefined,
      });
      setInviteUrl(window.location.origin + created.invite_url);
      await loadConnections(patientId);
    } catch {
      setError("초대를 보내지 못했어요.");
    } finally {
      setSending(false);
    }
  };

  const handleUnlink = async (caregiverId: number) => {
    if (patientId == null) return;
    try {
      await unlinkCaregiverPatient(caregiverId, patientId);
      await loadConnections(patientId);
    } catch {
      setError("연결 해제에 실패했어요.");
    }
  };

  const copyUrl = () => {
    navigator.clipboard?.writeText(inviteUrl);
    setUrlCopied(true);
    setTimeout(() => setUrlCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#FAF6F1]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">환자 연결관리</h1>
        <p className="text-[14px] text-[#8A7E75] mb-7">복약 관리를 함께할 사람을 초대하고 관리하세요.</p>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[#D94F4F]/8 border border-[#D94F4F]/20 mb-5">
            <AlertCircle className="w-4 h-4 text-[#D94F4F] shrink-0" />
            <p className="text-[13px] text-[#D94F4F]">{error}</p>
          </div>
        )}

        {/* 환자 연결하기 (보호자류 로그인일 때만) */}
        {caregiverId != null && (
          <div className="mb-6">
            <InvitePatientPanel
              caregiverId={caregiverId}
              onCreated={() => patientId != null && loadConnections(patientId)}
            />
          </div>
        )}

        {/* 초대하기 (이미 담당 중인 환자에 다른 보호자·요양보호사를 추가로 초대) */}
        <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
          <h2 className="text-[16px] font-black text-[#1E1A17] mb-4">초대하기</h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            {(Object.keys(RELATION_LABEL) as RelationType[]).map((key) => (
              <button
                key={key}
                onClick={() => setRelationType(key)}
                className={`py-2.5 rounded-xl text-[13px] font-bold transition-all ${
                  relationType === key ? "bg-[#C1653D] text-white" : "bg-[#F4F0EA] text-[#8A7E75]"
                }`}
              >
                {RELATION_LABEL[key]}
              </button>
            ))}
          </div>

          <div className="flex gap-2 mb-4 p-1 rounded-xl bg-[#F4F0EA]">
            {[
              { key: "sms" as const, label: "💬 문자" },
              { key: "url" as const, label: "🔗 URL" },
              { key: "qr" as const, label: "📷 QR" },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setInviteMethod(key)}
                className={`flex-1 py-2.5 rounded-lg text-[13px] font-bold transition-all ${
                  inviteMethod === key ? "bg-white text-[#1E1A17] shadow-sm" : "text-[#8A7E75]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {inviteMethod === "sms" && (
            <div className="space-y-3">
              <div className="relative">
                <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8A7E75]" />
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="전화번호 (010-0000-0000)"
                  className="w-full pl-11 pr-4 py-3.5 rounded-xl border border-[rgba(30,26,23,0.12)] bg-[#FAF6F1] text-[15px] outline-none"
                />
              </div>
              {inviteUrl && (
                <div className="rounded-xl px-4 py-3 bg-[#FAF6F1] border border-[rgba(30,26,23,0.08)]">
                  <p className="text-[12px] font-bold text-[#8A7E75] mb-1">생성된 초대 링크</p>
                  <p className="text-[13px] break-all text-[#1E1A17]">{inviteUrl}</p>
                </div>
              )}
              {!inviteUrl ? (
                <button
                  onClick={handleInvite}
                  disabled={sending}
                  className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
                >
                  {sending ? "전송 중..." : "초대 만들기"}
                </button>
              ) : (
                <a
                  href={buildSmsHref(phone, inviteUrl)}
                  className={`block w-full py-3.5 rounded-full text-center text-white font-bold text-[16px] bg-[#C1653D] ${
                    phone.trim() ? "" : "opacity-60 pointer-events-none"
                  }`}
                >
                  문자 앱으로 보내기
                </a>
              )}
            </div>
          )}

          {inviteMethod === "url" && (
            <div className="space-y-3">
              <p className="text-[13px] text-[#8A7E75]">초대 링크를 만들고 복사해서 전달하세요.</p>
              {!inviteUrl ? (
                <button
                  onClick={handleInvite}
                  disabled={sending}
                  className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
                >
                  {sending ? "생성 중..." : "초대 링크 만들기"}
                </button>
              ) : (
                <div className="flex items-center gap-2 px-4 py-3.5 rounded-xl bg-[#FAF6F1] border border-[rgba(30,26,23,0.10)]">
                  <span className="flex-1 text-[13px] font-mono truncate text-[#1E1A17]">{inviteUrl}</span>
                  <button
                    onClick={copyUrl}
                    className={`shrink-0 px-4 py-2 rounded-full text-[13px] font-bold ${
                      urlCopied ? "bg-[#8FAE8B]/20 text-[#4A7A47]" : "bg-[#C1653D]/15 text-[#C1653D]"
                    }`}
                  >
                    {urlCopied ? "복사됨 ✓" : "복사"}
                  </button>
                </div>
              )}
            </div>
          )}

          {inviteMethod === "qr" && (
            <div className="flex flex-col items-center py-4 gap-4">
              {!inviteUrl ? (
                <button
                  onClick={handleInvite}
                  disabled={sending}
                  className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
                >
                  {sending ? "생성 중..." : "QR용 초대 만들기"}
                </button>
              ) : (
                <>
                  <p className="text-[13px] text-center text-[#8A7E75]">
                    이 QR을 스캔하면 초대 링크로 이동해요.
                  </p>
                  <div className="p-4 rounded-2xl bg-white border-2 border-[rgba(30,26,23,0.08)]">
                    <QRCodeSVG value={inviteUrl} size={160} />
                  </div>
                  <p className="text-[12px] font-mono break-all text-center text-[#1E1A17]">{inviteUrl}</p>
                </>
              )}
            </div>
          )}
        </div>

        {/* 대기중인 초대 */}
        {invitations.length > 0 && (
          <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-[rgba(30,26,23,0.06)]">
              <h2 className="text-[15px] font-black text-[#1E1A17]">대기중인 초대 ({invitations.length}건)</h2>
            </div>
            {invitations.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between px-6 py-3.5 border-b border-[#F4F0EA] last:border-0">
                <span className="text-[14px] text-[#1E1A17]">
                  {RELATION_LABEL[inv.relation_type as RelationType] ?? inv.relation_type}
                  {inv.invited_phone ? ` · ${inv.invited_phone}` : ""}
                </span>
                <span className="px-3 py-1 rounded-full text-[12px] font-bold bg-[#F4F0EA] text-[#8A7E75]">대기중</span>
              </div>
            ))}
          </div>
        )}

        {/* 연결된 사람 */}
        <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-[rgba(30,26,23,0.06)]">
            <h2 className="text-[15px] font-black text-[#1E1A17]">연결된 사람 ({caregivers.length}명)</h2>
          </div>
          {loading ? (
            <p className="px-6 py-8 text-center text-[14px] text-[#8A7E75]">불러오는 중이에요...</p>
          ) : caregivers.length === 0 ? (
            <div className="py-14 text-center">
              <User className="w-9 h-9 mx-auto mb-3 text-[#8A7E75] opacity-30" />
              <p className="text-[14px] text-[#8A7E75]">아직 연결된 사람이 없어요</p>
            </div>
          ) : (
            caregivers.map((c) => (
              <div key={c.id} className="flex items-center justify-between px-6 py-4 border-b border-[#F4F0EA] last:border-0">
                <div>
                  <p className="text-[14px] font-bold text-[#1E1A17]">{c.name}</p>
                  <p className="text-[13px] text-[#8A7E75]">
                    {RELATION_LABEL[c.relation_type as RelationType] ?? c.relation_type}
                  </p>
                </div>
                <button
                  onClick={() => handleUnlink(c.id)}
                  className="px-4 py-2 rounded-full text-[12px] font-bold border border-[#C1653D]/35 text-[#C1653D]"
                >
                  연결 해제
                </button>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
