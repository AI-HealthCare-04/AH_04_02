import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { User, AlertCircle, Trash2 } from "lucide-react";
import NavBar from "../components/NavBar";
import InvitePatientPanel from "../components/InvitePatientPanel";
import {
  acceptInvitationAsCaregiver,
  createInvitation,
  deleteInvitation,
  listInvitations,
  listReceivedInvitations,
  rejectInvitationAsCaregiver,
  type InvitationSummary,
  type ReceivedInvitation,
} from "../api/care";
import { getPatientCaregivers, unlinkCaregiverPatient, type Caregiver } from "../api/monitoring";
import { copyTextToClipboard } from "../lib/clipboard";
import { getCurrentCaregiverId, getCurrentPatientId, getCurrentUserName } from "../lib/session";

type RelationType = "guardian" | "caregiver" | "life_support_worker" | "social_worker";

const RELATION_LABEL: Record<RelationType, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

function extractInviteToken(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/\/invite\/([^/?#\s]+)/);
  if (match) return match[1];
  if (!trimmed.includes("/") && !trimmed.includes(" ")) return trimmed;
  return null;
}

export default function Connect() {
  const navigate = useNavigate();
  // 보호자류 로그인이면(값이 있으면) "환자 연결하기" 패널을 추가로 보여준다.
  const caregiverId = getCurrentCaregiverId();
  const patientId = caregiverId == null ? getCurrentPatientId() : null;

  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [invitations, setInvitations] = useState<InvitationSummary[]>([]);
  const [receivedInvitations, setReceivedInvitations] = useState<ReceivedInvitation[]>([]);
  const [loading, setLoading] = useState(caregiverId == null);
  const [error, setError] = useState("");
  const [relationType, setRelationType] = useState<RelationType>("guardian");
  const [invitedPhone, setInvitedPhone] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deletingInvitationId, setDeletingInvitationId] = useState<number | null>(null);
  const [actingInvitationId, setActingInvitationId] = useState<number | null>(null);
  const [inviteUrlInput, setInviteUrlInput] = useState("");
  const [inviteUrlError, setInviteUrlError] = useState("");

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

  const loadReceivedInvitations = async () => {
    if (caregiverId == null) return;
    try {
      setReceivedInvitations(await listReceivedInvitations(caregiverId));
    } catch {
      setError("받은 초대를 불러오지 못했어요.");
    }
  };

  useEffect(() => {
    if (caregiverId != null) {
      setLoading(false);
      loadReceivedInvitations();
      return;
    }
    if (patientId == null) {
      setLoading(false);
      return;
    }
    loadConnections(patientId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId, patientId]);

  const handleUnlink = async (caregiverId: number) => {
    if (patientId == null) return;
    try {
      await unlinkCaregiverPatient(caregiverId, patientId);
      await loadConnections(patientId);
    } catch {
      setError("연결 해제에 실패했어요.");
    }
  };

  const handleCreateInvite = async () => {
    if (patientId == null) return;
    setCreatingInvite(true);
    setError("");
    setInviteUrl("");
    try {
      const created = await createInvitation({
        patient_id: patientId,
        relation_type: relationType,
        invited_phone: invitedPhone.trim() || undefined,
      });
      setInviteUrl(window.location.origin + created.invite_url);
      await loadConnections(patientId);
    } catch {
      setError("초대를 만들지 못했어요.");
    } finally {
      setCreatingInvite(false);
    }
  };

  const handleCopyInviteUrl = async () => {
    if (!inviteUrl) return;
    const copied = await copyTextToClipboard(inviteUrl);
    if (!copied) {
      setError("초대 링크를 복사하지 못했어요. 링크를 길게 눌러 직접 복사해 주세요.");
      return;
    }
    setError("");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeleteInvitation = async (invitationId: number) => {
    if (patientId == null || deletingInvitationId !== null) return;
    if (!window.confirm("대기중인 초대를 삭제할까요? 이미 보낸 초대 링크도 사용할 수 없게 돼요.")) return;
    setDeletingInvitationId(invitationId);
    setError("");
    try {
      await deleteInvitation(invitationId);
      await loadConnections(patientId);
    } catch {
      setError("초대를 삭제하지 못했어요.");
    } finally {
      setDeletingInvitationId(null);
    }
  };

  const handleAcceptReceived = async (invitationId: number) => {
    if (actingInvitationId !== null) return;
    setActingInvitationId(invitationId);
    setError("");
    try {
      await acceptInvitationAsCaregiver(invitationId);
      setReceivedInvitations((prev) => prev.filter((inv) => inv.id !== invitationId));
    } catch {
      setError("초대 수락에 실패했어요.");
    } finally {
      setActingInvitationId(null);
    }
  };

  const handleRejectReceived = async (invitationId: number) => {
    if (actingInvitationId !== null) return;
    setActingInvitationId(invitationId);
    setError("");
    try {
      await rejectInvitationAsCaregiver(invitationId);
      setReceivedInvitations((prev) => prev.filter((inv) => inv.id !== invitationId));
    } catch {
      setError("초대 거절에 실패했어요.");
    } finally {
      setActingInvitationId(null);
    }
  };

  const handleOpenInviteUrl = () => {
    const token = extractInviteToken(inviteUrlInput);
    if (!token) {
      setInviteUrlError("올바른 초대 링크 또는 코드를 입력해 주세요.");
      return;
    }
    navigate(`/invite/${token}`);
  };

  return (
    <div className="min-h-screen bg-[#FAF6F1]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">연결관리</h1>
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
              onCreated={() => loadReceivedInvitations()}
            />
          </div>
        )}

        {caregiverId != null && (
          <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
            <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">받은 초대</h2>
            <p className="text-[13px] text-[#8A7E75] mb-4">
              환자가 전화번호로 보낸 초대는 여기에서 바로 수락하거나 거절할 수 있어요.
            </p>

            {receivedInvitations.length > 0 ? (
              <div className="space-y-2 mb-4">
                {receivedInvitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-[#FAF6F1] flex-wrap"
                  >
                    <div>
                      <p className="text-[14px] font-bold text-[#1E1A17]">
                        {inv.patient_name}님이 {RELATION_LABEL[inv.relation_type as RelationType] ?? inv.relation_type}로 초대했어요
                      </p>
                      {inv.expires_at && (
                        <p className="text-[12px] text-[#8A7E75]">
                          {new Date(inv.expires_at).toLocaleDateString("ko-KR")}까지 유효
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => handleRejectReceived(inv.id)}
                        disabled={actingInvitationId === inv.id}
                        className="px-4 py-2 rounded-full text-[13px] font-bold border border-[rgba(30,26,23,0.15)] text-[#1E1A17] disabled:opacity-50"
                      >
                        거절
                      </button>
                      <button
                        onClick={() => handleAcceptReceived(inv.id)}
                        disabled={actingInvitationId === inv.id}
                        className="px-4 py-2 rounded-full text-[13px] font-bold text-white bg-[#C1653D] disabled:opacity-50"
                      >
                        수락
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-4 py-4 rounded-xl bg-[#FAF6F1] text-[14px] text-[#8A7E75] mb-4">
                아직 받은 초대가 없어요.
              </p>
            )}

            <div className="flex gap-2 flex-wrap">
              <input
                value={inviteUrlInput}
                onChange={(event) => {
                  setInviteUrlInput(event.target.value);
                  setInviteUrlError("");
                }}
                placeholder="초대 링크나 코드를 붙여넣으세요"
                className="flex-1 min-w-[200px] px-4 py-3 rounded-xl border border-[rgba(30,26,23,0.15)] bg-white text-[14px] outline-none"
              />
              <button
                onClick={handleOpenInviteUrl}
                className="px-5 py-3 rounded-full font-bold text-[14px] shrink-0 bg-[#C1653D]/15 text-[#C1653D]"
              >
                확인
              </button>
            </div>
            {inviteUrlError && (
              <p className="text-[12px] mt-2 text-[#D94F4F]">{inviteUrlError}</p>
            )}
          </div>
        )}

        {/* 보호자·지원인력 초대하기 (환자 로그인일 때만) */}
        {caregiverId == null && patientId != null && (
          <>
            <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
              <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">받은 초대 수락하기</h2>
              <p className="text-[13px] text-[#8A7E75] mb-4">
                보호자나 지원인력에게 받은 초대 링크 또는 코드를 입력하세요.
              </p>
              <div className="flex gap-2 flex-wrap">
                <input
                  value={inviteUrlInput}
                  onChange={(event) => {
                    setInviteUrlInput(event.target.value);
                    setInviteUrlError("");
                  }}
                  placeholder="초대 링크나 코드를 붙여넣으세요"
                  className="flex-1 min-w-[200px] px-4 py-3 rounded-xl border border-[rgba(30,26,23,0.15)] bg-white text-[14px] outline-none"
                />
                <button
                  onClick={handleOpenInviteUrl}
                  className="px-5 py-3 rounded-full font-bold text-[14px] shrink-0 bg-[#C1653D]/15 text-[#C1653D]"
                >
                  확인
                </button>
              </div>
              {inviteUrlError && (
                <p className="text-[12px] mt-2 text-[#D94F4F]">{inviteUrlError}</p>
              )}
            </div>

            <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
              <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">보호자·지원인력 초대하기</h2>
              <p className="text-[13px] text-[#8A7E75] mb-4">
                함께 복약을 확인할 사람에게 초대 링크를 보내세요.
              </p>

              <div className="grid grid-cols-2 gap-2 mb-4">
                {(Object.keys(RELATION_LABEL) as RelationType[]).map((type) => (
                  <button
                    key={type}
                    onClick={() => setRelationType(type)}
                    className={`py-2.5 rounded-xl text-[13px] font-bold border transition-all ${
                      relationType === type
                        ? "border-[#C1653D] bg-[#C1653D]/10 text-[#C1653D]"
                        : "border-[rgba(30,26,23,0.12)] bg-[#FAF6F1] text-[#8A7E75]"
                    }`}
                  >
                    {RELATION_LABEL[type]}
                  </button>
                ))}
              </div>

              <input
                value={invitedPhone}
                onChange={(event) => setInvitedPhone(event.target.value)}
                placeholder="초대받을 사람 전화번호 (선택)"
                className="w-full px-4 py-3.5 rounded-xl border border-[rgba(30,26,23,0.12)] bg-[#FAF6F1] text-[15px] outline-none mb-3"
              />

              <button
                onClick={handleCreateInvite}
                disabled={creatingInvite}
                className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
              >
                {creatingInvite ? "생성 중..." : "초대 링크 만들기"}
              </button>

              {inviteUrl && (
                <div className="flex items-center gap-2 px-4 py-3.5 mt-4 rounded-xl bg-[#FAF6F1] border border-[rgba(30,26,23,0.10)]">
                  <span className="flex-1 text-[13px] font-mono truncate text-[#1E1A17]">{inviteUrl}</span>
                  <button
                    onClick={handleCopyInviteUrl}
                    className={`shrink-0 px-4 py-2 rounded-full text-[13px] font-bold ${
                      copied ? "bg-[#8FAE8B]/20 text-[#4A7A47]" : "bg-[#C1653D]/15 text-[#C1653D]"
                    }`}
                  >
                    {copied ? "복사됨" : "복사"}
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {/* 대기중인 초대 */}
        {caregiverId == null && invitations.length > 0 && (
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
                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-3 py-1 rounded-full text-[12px] font-bold bg-[#F4F0EA] text-[#8A7E75]">대기중</span>
                  <button
                    onClick={() => handleDeleteInvitation(inv.id)}
                    disabled={deletingInvitationId === inv.id}
                    aria-label="대기중인 초대 삭제"
                    className="w-8 h-8 rounded-lg flex items-center justify-center disabled:opacity-50"
                    style={{ background: "rgba(217,79,79,0.10)" }}
                  >
                    <Trash2 className="w-4 h-4 text-[#D94F4F]" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 연결된 사람 */}
        {caregiverId == null && (
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
        )}
      </main>
    </div>
  );
}
