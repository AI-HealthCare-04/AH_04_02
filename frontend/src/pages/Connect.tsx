import { useEffect, useState } from "react";
import { Phone, User, AlertCircle } from "lucide-react";
import NavBar from "../components/NavBar";
import {
  createInvitation,
  listInvitations,
  type InvitationSummary,
} from "../api/care";
import { getPatientCaregivers, unlinkCaregiverPatient, type Caregiver } from "../api/monitoring";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";

type RelationType = "guardian" | "caregiver" | "life_support_worker" | "social_worker";

const RELATION_LABEL: Record<RelationType, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

// 장식용 가짜 QR — 실제 QR 생성 라이브러리 없이 시각 효과만 (기존 Figma 디자인 그대로)
function FakeQR() {
  const cells = Array.from({ length: 441 }, (_, i) => (i * 7 + Math.floor(i / 21)) % 3 === 0);
  return (
    <div
      className="grid gap-[1.5px] p-2.5 bg-white rounded-xl"
      style={{ gridTemplateColumns: "repeat(21, 1fr)", width: 160, height: 160 }}
    >
      {cells.map((on, i) => (
        <div key={i} className={on ? "bg-[#1E1A17] rounded-[1px]" : ""} />
      ))}
    </div>
  );
}

export default function Connect() {
  const patientId = useGuardedPatientId();

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
      setPhone("");
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
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">보호자·요양보호사 연결 관리</h1>
        <p className="text-[14px] text-[#8A7E75] mb-7">복약 관리를 함께할 사람을 초대하고 관리하세요.</p>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[#D94F4F]/8 border border-[#D94F4F]/20 mb-5">
            <AlertCircle className="w-4 h-4 text-[#D94F4F] shrink-0" />
            <p className="text-[13px] text-[#D94F4F]">{error}</p>
          </div>
        )}

        {/* 초대하기 */}
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
                  <p className="text-[11px] text-[#8A7E75] mt-1">
                    실제 문자 발송 기능은 아직 없어요 — 이 링크를 직접 전달해 주세요.
                  </p>
                </div>
              )}
              <button
                onClick={handleInvite}
                disabled={sending}
                className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
              >
                {sending ? "전송 중..." : "초대 만들기"}
              </button>
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
                    QR은 지금 시각효과용 이미지예요 — 아래 링크를 스캐너에 직접 입력해 확인하세요.
                  </p>
                  <div className="p-4 rounded-2xl bg-[#FAF6F1] border-2 border-[rgba(30,26,23,0.08)]">
                    <FakeQR />
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
