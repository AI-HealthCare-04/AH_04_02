import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { User, AlertCircle, RotateCw, Trash2 } from "lucide-react";
import NavBar from "../components/NavBar";
import InvitePatientPanel from "../components/InvitePatientPanel";
import {
  acceptInvitationAsCaregiver,
  approveRevocation,
  createInvitation,
  deleteInvitation,
  listInvitations,
  listPendingRevocations,
  listReceivedInvitations,
  listRelationNotices,
  listSentPatientInvitations,
  markRelationNoticeRead,
  rejectInvitationAsCaregiver,
  type InvitationSummary,
  type PendingRevocation,
  type ReceivedInvitation,
  type RelationNotice,
  type SentPatientInvitation,
} from "../api/care";
import {
  getCaregiverPatients,
  getCaregivers,
  getPatientCaregivers,
  unlinkCaregiverPatient,
  type Caregiver,
  type Patient,
} from "../api/monitoring";
import { copyTextToClipboard } from "../lib/clipboard";
import { getCurrentCaregiverId, getCurrentPatientId, getCurrentUserName } from "../lib/session";

type RelationType = "guardian" | "caregiver" | "life_support_worker" | "social_worker";

const RELATION_LABEL: Record<RelationType, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

// [2026-07-24 추가] event별로 다른 문구를 만든다 — patient_name과 counterpart_name이 같으면
// (환자 본인이 처리한 경우) 굳이 이름을 두 번 반복하지 않는다.
function describeRelationNotice(notice: RelationNotice): string {
  const same = notice.counterpart_name === notice.patient_name;
  switch (notice.event) {
    case "linked":
      return `${notice.counterpart_name}님과 연결됐어요`;
    case "unlinked":
      return `${notice.counterpart_name}님과의 연결이 해제됐어요`;
    case "revocation_approved":
      return same
        ? `${notice.patient_name}님과의 연결 해제 요청이 승인됐어요`
        : `${notice.patient_name}님과의 연결 해제 요청이 승인됐어요 (${notice.counterpart_name}님이 처리)`;
    case "revocation_rejected":
      return same
        ? `${notice.patient_name}님과의 연결 해제 요청이 거부됐어요`
        : `${notice.patient_name}님과의 연결 해제 요청이 거부됐어요 (${notice.counterpart_name}님이 처리)`;
    default:
      return `${notice.patient_name}님과의 연결에 변경이 있었어요`;
  }
}

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
  const [inviteId, setInviteId] = useState<number | null>(null);
  const [inviteUrl, setInviteUrl] = useState("");
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deletingInvitationId, setDeletingInvitationId] = useState<number | null>(null);
  const [actingInvitationId, setActingInvitationId] = useState<number | null>(null);
  const [inviteUrlInput, setInviteUrlInput] = useState("");
  const [inviteUrlError, setInviteUrlError] = useState("");
  // [2026-07-23 추가] "받은 해제 요청" — 기관이 사유를 남기고 연결 해제를 요청하면, 환자
  // 본인이나 그 환자와 연결된 다른 보호자가 여기서 승인/거부한다(역할에 따라 백엔드가
  // 알아서 필터링해 주므로 프론트는 역할 분기 없이 같은 목록을 그대로 쓴다).
  const [pendingRevocations, setPendingRevocations] = useState<PendingRevocation[]>([]);
  const [actingRevocationId, setActingRevocationId] = useState<number | null>(null);
  // [2026-07-23 추가, 2026-07-24 확장] "관계 알림" — 연결(초대 수락)/해제(즉시 해제, 해제
  // 요청 승인·거부 결과) 등 상대에게 생긴 일을 여기서 확인한다. 승인 시 그 환자에 대한
  // 접근권을 잃을 수 있어 별도 알림함으로 확인한다.
  const [relationNotices, setRelationNotices] = useState<RelationNotice[]>([]);
  const [dismissingNoticeId, setDismissingNoticeId] = useState<number | null>(null);
  // [2026-07-23 추가] 보호자/기관 쪽에도 "내가 보낸 초대"와 "연결된 환자" 목록을 보여준다 —
  // 지금까진 이 화면(caregiverId != null 쪽)에 둘 다 없어서, 초대를 보내도 확인할 방법이 없고
  // 연결 해제도 PatientManagement.tsx에서만 가능했다.
  const [sentInvitations, setSentInvitations] = useState<SentPatientInvitation[]>([]);
  const [connectedPatients, setConnectedPatients] = useState<Patient[]>([]);
  const [myCaregiver, setMyCaregiver] = useState<Caregiver | null>(null);
  const [deletingSentInvitationId, setDeletingSentInvitationId] = useState<number | null>(null);
  const [unlinkingPatientId, setUnlinkingPatientId] = useState<number | null>(null);

  const loadCaregiverSideData = async () => {
    if (caregiverId == null) return;
    try {
      const [sent, patients, myProfile] = await Promise.all([
        listSentPatientInvitations(caregiverId),
        getCaregiverPatients(caregiverId),
        getCaregivers(),
      ]);
      setSentInvitations(sent);
      setConnectedPatients(patients);
      setMyCaregiver(myProfile[0] ?? null);
    } catch {
      setError("연결 정보를 불러오지 못했어요.");
    }
  };

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

  const loadPendingRevocations = () => {
    listPendingRevocations()
      .then(setPendingRevocations)
      .catch(() => {});
  };

  const loadRelationNotices = () => {
    listRelationNotices()
      .then((notices) => setRelationNotices(notices.filter((n) => n.read_at == null)))
      .catch(() => {});
  };

  const handleDismissNotice = async (noticeId: number) => {
    if (dismissingNoticeId !== null) return;
    setDismissingNoticeId(noticeId);
    try {
      await markRelationNoticeRead(noticeId);
      setRelationNotices((prev) => prev.filter((n) => n.id !== noticeId));
    } catch {
      setError("알림을 확인 처리하지 못했어요.");
    } finally {
      setDismissingNoticeId(null);
    }
  };

  useEffect(() => {
    loadPendingRevocations();
    loadRelationNotices();
    if (caregiverId != null) {
      setLoading(false);
      loadReceivedInvitations();
      loadCaregiverSideData();
      return;
    }
    if (patientId == null) {
      setLoading(false);
      return;
    }
    loadConnections(patientId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caregiverId, patientId]);

  const handleRevocationDecision = async (trustId: number, approve: boolean) => {
    if (actingRevocationId !== null) return;
    setActingRevocationId(trustId);
    setError("");
    try {
      await approveRevocation(trustId, approve);
      setPendingRevocations((prev) => prev.filter((r) => r.trust_id !== trustId));
      if (approve && patientId != null) await loadConnections(patientId);
    } catch {
      setError(approve ? "승인 처리에 실패했어요." : "거부 처리에 실패했어요.");
    } finally {
      setActingRevocationId(null);
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
      setInviteId(created.id);
      setInviteUrl(window.location.origin + created.invite_url);
      await loadConnections(patientId);
    } catch {
      setError("초대를 만들지 못했어요.");
    } finally {
      setCreatingInvite(false);
    }
  };

  // [2026-07-24 추가] 기존 초대 링크를 무효화하고 새 코드를 발급한다.
  const handleRegenerateInvite = async () => {
    if (patientId == null || creatingInvite) return;
    setCreatingInvite(true);
    setError("");
    try {
      if (inviteId != null) {
        await deleteInvitation(inviteId);
      }
      const created = await createInvitation({
        patient_id: patientId,
        relation_type: relationType,
        invited_phone: invitedPhone.trim() || undefined,
      });
      setInviteId(created.id);
      setInviteUrl(window.location.origin + created.invite_url);
      setCopied(false);
      await loadConnections(patientId);
    } catch {
      setError("초대를 다시 만들지 못했어요.");
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

  const handleDeleteSentInvitation = async (invitationId: number) => {
    if (deletingSentInvitationId !== null) return;
    if (!window.confirm("대기중인 초대를 삭제할까요? 이미 보낸 초대 링크도 사용할 수 없게 돼요.")) return;
    setDeletingSentInvitationId(invitationId);
    setError("");
    try {
      await deleteInvitation(invitationId);
      setSentInvitations((prev) => prev.filter((inv) => inv.id !== invitationId));
    } catch {
      setError("초대를 삭제하지 못했어요.");
    } finally {
      setDeletingSentInvitationId(null);
    }
  };

  // [2026-07-23 추가] 기관 계정은 사유를 남기고 승인을 받아야 하므로 별도 화면으로
  // 이동시킨다(PatientManagement.tsx의 remove()와 동일한 정책).
  const handleUnlinkPatient = async (targetPatientId: number) => {
    if (caregiverId == null) return;
    if (myCaregiver?.relation_type === "organization") {
      navigate(`/patients/${targetPatientId}/disconnect`);
      return;
    }
    if (!window.confirm("이 환자와의 연결을 해제할까요? 환자 계정과 기록은 삭제되지 않아요.")) return;
    setUnlinkingPatientId(targetPatientId);
    setError("");
    try {
      await unlinkCaregiverPatient(caregiverId, targetPatientId);
      setConnectedPatients((prev) => prev.filter((p) => p.id !== targetPatientId));
      if (localStorage.getItem("patient_id") === String(targetPatientId)) {
        localStorage.removeItem("patient_id");
      }
    } catch {
      setError("연결을 해제하지 못했어요.");
    } finally {
      setUnlinkingPatientId(null);
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
    <div className="min-h-screen bg-[#F2E8D8]">
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

        {/* [2026-07-23 추가, 2026-07-24 확장] 관계 알림 — 연결/해제/해제 요청 처리 결과를
            역할(환자/보호자/기관) 무관하게 상대에게 보여준다. */}
        {relationNotices.length > 0 && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
            <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">알림</h2>
            <div className="space-y-3 mt-3">
              {relationNotices.map((notice) => (
                <div key={notice.id} className="px-4 py-3.5 rounded-xl bg-[#F2E8D8] flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[14px] font-bold text-[#1E1A17]">
                      {describeRelationNotice(notice)}
                    </p>
                    <p className="text-[12px] text-[#8A7E75] mt-1">
                      {new Date(notice.created_at).toLocaleDateString("ko-KR")}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDismissNotice(notice.id)}
                    disabled={dismissingNoticeId === notice.id}
                    className="px-3 py-1.5 rounded-full text-[12px] font-bold border border-[rgba(30,26,23,0.15)] text-[#1E1A17] disabled:opacity-50 shrink-0"
                  >
                    확인
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* [2026-07-23 추가] 받은 해제 요청 — 기관이 사유를 남기고 연결 해제를 요청하면
            여기서 승인/거부한다. 역할(환자/보호자) 무관하게 같은 목록을 그대로 쓴다. */}
        {pendingRevocations.length > 0 && (
          <div className="bg-[#F9F4EB] border border-[#D94F4F]/25 rounded-2xl p-6 mb-6">
            <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">받은 해제 요청</h2>
            <p className="text-[13px] text-[#8A7E75] mb-4">
              연결을 끊으려는 사유를 확인하고 승인하거나 거부하세요. 2주 안에 응답하지 않으면 요청자가 직접 확정할 수 있어요.
            </p>
            <div className="space-y-3">
              {pendingRevocations.map((rev) => (
                <div key={rev.trust_id} className="px-4 py-3.5 rounded-xl bg-[#F2E8D8]">
                  <p className="text-[14px] font-bold text-[#1E1A17]">
                    {rev.caregiver_name}님이 {rev.patient_name}님과의 연결을 끊으려고 해요
                  </p>
                  {rev.reason && (
                    <p className="text-[13px] text-[#8A7E75] mt-1">사유: {rev.reason}</p>
                  )}
                  {rev.deadline && (
                    <p className="text-[12px] text-[#8A7E75] mt-1">
                      {new Date(rev.deadline).toLocaleDateString("ko-KR")}까지 응답하지 않으면 자동으로 처리돼요.
                    </p>
                  )}
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleRevocationDecision(rev.trust_id, false)}
                      disabled={actingRevocationId === rev.trust_id}
                      className="px-4 py-2 rounded-full text-[13px] font-bold border border-[rgba(30,26,23,0.15)] text-[#1E1A17] disabled:opacity-50"
                    >
                      거부
                    </button>
                    <button
                      onClick={() => handleRevocationDecision(rev.trust_id, true)}
                      disabled={actingRevocationId === rev.trust_id}
                      className="px-4 py-2 rounded-full text-[13px] font-bold text-white bg-[#D94F4F] disabled:opacity-50"
                    >
                      승인(연결 해제)
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 환자 연결하기 (보호자류 로그인일 때만) */}
        {caregiverId != null && (
          <div className="mb-6">
            <InvitePatientPanel
              caregiverId={caregiverId}
              onCreated={() => {
                loadReceivedInvitations();
                loadCaregiverSideData();
              }}
            />
          </div>
        )}

        {caregiverId != null && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
            <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">받은 초대</h2>
            <p className="text-[13px] text-[#8A7E75] mb-4">
              환자가 전화번호로 보낸 초대는 여기에서 바로 수락하거나 거절할 수 있어요.
            </p>

            {receivedInvitations.length > 0 ? (
              <div className="space-y-2 mb-4">
                {receivedInvitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl bg-[#F2E8D8] flex-wrap"
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
              <p className="px-4 py-4 rounded-xl bg-[#F2E8D8] text-[14px] text-[#8A7E75] mb-4">
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

        {/* [2026-07-23 추가] 초대중인 내역 — 내가(보호자/기관) 보낸 환자 초대 중 대기중인 것 */}
        {caregiverId != null && sentInvitations.length > 0 && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-[rgba(30,26,23,0.06)]">
              <h2 className="text-[15px] font-black text-[#1E1A17]">초대중인 내역 ({sentInvitations.length}건)</h2>
            </div>
            {sentInvitations.map((inv) => (
              <div key={inv.id} className="flex items-center justify-between px-6 py-3.5 border-b border-[#F4F0EA] last:border-0">
                <span className="text-[14px] text-[#1E1A17]">
                  환자 초대{inv.invited_phone ? ` · ${inv.invited_phone}` : ""}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-3 py-1 rounded-full text-[12px] font-bold bg-[#F4F0EA] text-[#8A7E75]">대기중</span>
                  <button
                    onClick={() => handleDeleteSentInvitation(inv.id)}
                    disabled={deletingSentInvitationId === inv.id}
                    aria-label="초대중인 내역 삭제"
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

        {/* [2026-07-23 추가] 연결된 환자 리스트 — 이 계정이 케어하는 환자 전체 */}
        {caregiverId != null && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden mb-6">
            <div className="px-6 py-4 border-b border-[rgba(30,26,23,0.06)]">
              <h2 className="text-[15px] font-black text-[#1E1A17]">연결된 환자 ({connectedPatients.length}명)</h2>
            </div>
            {connectedPatients.length === 0 ? (
              <div className="py-14 text-center">
                <User className="w-9 h-9 mx-auto mb-3 text-[#8A7E75] opacity-30" />
                <p className="text-[14px] text-[#8A7E75]">아직 연결된 환자가 없어요</p>
              </div>
            ) : (
              connectedPatients.map((p) => (
                <div key={p.id} className="flex items-center justify-between px-6 py-4 border-b border-[#F4F0EA] last:border-0">
                  <p className="text-[14px] font-bold text-[#1E1A17]">{p.name}</p>
                  <button
                    onClick={() => handleUnlinkPatient(p.id)}
                    disabled={unlinkingPatientId === p.id}
                    className="px-4 py-2 rounded-full text-[12px] font-bold border border-[#C1653D]/35 text-[#C1653D] disabled:opacity-50"
                  >
                    연결 해제
                  </button>
                </div>
              ))
            )}
          </div>
        )}

        {/* 보호자·지원인력 초대하기 (환자 로그인일 때만) */}
        {caregiverId == null && patientId != null && (
          <>
            <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
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

            <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
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
                        : "border-[rgba(30,26,23,0.12)] bg-[#F2E8D8] text-[#8A7E75]"
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
                className="w-full px-4 py-3.5 rounded-xl border border-[rgba(30,26,23,0.12)] bg-[#F2E8D8] text-[15px] outline-none mb-3"
              />

              <button
                onClick={handleCreateInvite}
                disabled={creatingInvite}
                className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
              >
                {creatingInvite ? "생성 중..." : "초대 링크 만들기"}
              </button>

              {inviteUrl && (
                <div className="flex items-center gap-2 px-4 py-3.5 mt-4 rounded-xl bg-[#F2E8D8] border border-[rgba(30,26,23,0.10)]">
                  <span className="flex-1 text-[13px] font-mono truncate text-[#1E1A17]">{inviteUrl}</span>
                  <button
                    onClick={handleRegenerateInvite}
                    disabled={creatingInvite}
                    aria-label="초대 링크 재발급"
                    className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-[#C1653D]/15 text-[#C1653D] disabled:opacity-50"
                  >
                    <RotateCw className="w-4 h-4" />
                  </button>
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
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden mb-6">
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
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden">
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
