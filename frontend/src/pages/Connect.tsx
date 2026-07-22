import { useEffect, useState } from "react";
import { User, AlertCircle } from "lucide-react";
import NavBar from "../components/NavBar";
import InvitePatientPanel from "../components/InvitePatientPanel";
import { listInvitations, type InvitationSummary } from "../api/care";
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

  const handleUnlink = async (caregiverId: number) => {
    if (patientId == null) return;
    try {
      await unlinkCaregiverPatient(caregiverId, patientId);
      await loadConnections(patientId);
    } catch {
      setError("연결 해제에 실패했어요.");
    }
  };

  return (
    <div className="min-h-screen bg-[#F2E8D8]">
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

        {/* 대기중인 초대 — [2026-07-21 회의 반영] "초대하기"(환자→보호자류 초대 생성) UI는
            삭제됐다. 이 목록은 삭제 이전에 이미 생성된 대기중 초대만 보여준다(신규 생성 불가). */}
        {invitations.length > 0 && (
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
                <span className="px-3 py-1 rounded-full text-[12px] font-bold bg-[#F4F0EA] text-[#8A7E75]">대기중</span>
              </div>
            ))}
          </div>
        )}

        {/* 연결된 사람 */}
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
      </main>
    </div>
  );
}
