import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CalendarClock, ChevronLeft, ClipboardList, LayoutDashboard, Plus, Search, X } from "lucide-react";
import NavBar from "../components/NavBar";
import InvitePatientPanel from "../components/InvitePatientPanel";
import { getCaregiverPatients, unlinkCaregiverPatient, type Patient } from "../api/monitoring";
import {
  acceptInvitationAsCaregiver,
  listReceivedInvitations,
  rejectInvitationAsCaregiver,
  type ReceivedInvitation,
} from "../api/care";
import { getCurrentCaregiverId, getCurrentUserName } from "../lib/session";
import { C } from "../theme";

const RELATION_LABEL: Record<string, string> = {
  guardian: "보호자",
  caregiver: "요양보호사",
  life_support_worker: "생활지원사",
  social_worker: "사회복지사",
};

/** [2026-07-22 추가] 환자가 문자·카톡 등으로 보낸 초대 링크를 붙여넣었을 때 토큰만
 * 뽑아낸다 — 전체 URL이든 토큰만이든 둘 다 받아준다. */
function extractInviteToken(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const match = trimmed.match(/\/invite\/([^/?#\s]+)/);
  if (match) return match[1];
  if (!trimmed.includes("/") && !trimmed.includes(" ")) return trimmed;
  return null;
}

export default function PatientManagement() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showInvite, setShowInvite] = useState(false);

  // [2026-07-22 추가] "받은 초대" — 환자가 전화번호를 지정해 나에게 보낸 초대를 링크 없이
  // 바로 확인·수락/거절할 수 있게 한다.
  const [receivedInvitations, setReceivedInvitations] = useState<ReceivedInvitation[]>([]);
  const [actingInvitationId, setActingInvitationId] = useState<number | null>(null);
  const [inviteUrlInput, setInviteUrlInput] = useState("");
  const [inviteUrlError, setInviteUrlError] = useState("");

  const load = async () => {
    if (!caregiverId) {
      setError("로그인 정보를 확인할 수 없어요.");
      setLoading(false);
      return;
    }
    try {
      setPatients(await getCaregiverPatients(caregiverId));
    } catch {
      setError("환자 목록을 불러오지 못했어요.");
    } finally {
      setLoading(false);
    }
  };

  const loadReceivedInvitations = async () => {
    if (!caregiverId) return;
    try {
      setReceivedInvitations(await listReceivedInvitations(caregiverId));
    } catch {
      // [의도적] 부가 목록이라 실패해도 메인 환자 목록 화면을 막지 않는다.
    }
  };

  useEffect(() => {
    load();
    loadReceivedInvitations();
  }, []);

  const handleAcceptReceived = async (id: number) => {
    setActingInvitationId(id);
    try {
      await acceptInvitationAsCaregiver(id);
      setReceivedInvitations((prev) => prev.filter((inv) => inv.id !== id));
      await load();
    } catch {
      setError("초대 수락에 실패했어요.");
    } finally {
      setActingInvitationId(null);
    }
  };

  const handleRejectReceived = async (id: number) => {
    setActingInvitationId(id);
    try {
      await rejectInvitationAsCaregiver(id);
      setReceivedInvitations((prev) => prev.filter((inv) => inv.id !== id));
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

  // 케어하는 환자가 아직 없으면(첫 로그인 온보딩) 연결 패널을 바로 펼쳐 보여준다.
  useEffect(() => {
    if (!loading && patients.length === 0) setShowInvite(true);
  }, [loading, patients.length]);

  const filtered = patients.filter((p) => !search || p.name.includes(search));

  const openPatientMenu = (id: number, path: string) => {
    localStorage.setItem("patient_id", String(id));
    navigate(path);
  };

  const remove = async (id: number) => {
    if (!caregiverId) return;
    if (!window.confirm("이 환자와의 연결을 해제할까요? 환자 계정과 기록은 삭제되지 않아요.")) return;
    try {
      await unlinkCaregiverPatient(caregiverId, id);
      await load();
      if (localStorage.getItem("patient_id") === String(id)) {
        localStorage.removeItem("patient_id");
      }
    } catch {
      setError("연결을 해제하지 못했어요.");
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-3xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/mypage")}
          className="flex items-center gap-1 text-[13px] font-bold mb-4 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 마이페이지
        </button>

        <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
          <div>
            <h1 className="text-[26px] font-black" style={{ color: C.dark }}>환자 관리</h1>
            <p className="text-[14px] mt-1" style={{ color: C.muted }}>연결된 환자 {patients.length}명을 관리하세요.</p>
          </div>
          <button
            onClick={() => setShowInvite((v) => !v)}
            className="flex items-center gap-2 px-5 py-3 rounded-full text-white font-bold text-[14px]"
            style={{ background: C.terracotta }}
          >
            <Plus className="w-4 h-4" /> 환자 연결
          </button>
        </div>

        {/* [2026-07-22 추가] "받은 초대" — 환자가 전화번호로 보낸 초대를 여기서 바로 확인하고,
            전화번호를 지정하지 않은(공유용) 초대는 링크/코드를 붙여넣어 확인한다. */}
        <div className="rounded-2xl p-6 mb-6" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          <h2 className="text-[16px] font-black mb-1" style={{ color: C.dark }}>받은 초대</h2>
          <p className="text-[13px] mb-4" style={{ color: C.muted }}>
            환자가 전화번호로 보낸 초대는 여기 자동으로 뜨고, 그 외 링크는 아래에 붙여넣어 확인하세요.
          </p>

          {receivedInvitations.length > 0 && (
            <div className="space-y-2 mb-4">
              {receivedInvitations.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl flex-wrap"
                  style={{ background: C.ivory }}
                >
                  <div>
                    <p className="text-[14px] font-bold" style={{ color: C.dark }}>
                      {inv.patient_name}님이 {RELATION_LABEL[inv.relation_type] ?? inv.relation_type}로 초대했어요
                    </p>
                    {inv.expires_at && (
                      <p className="text-[12px]" style={{ color: C.muted }}>
                        {new Date(inv.expires_at).toLocaleDateString("ko-KR")}까지 유효
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleRejectReceived(inv.id)}
                      disabled={actingInvitationId === inv.id}
                      className="px-4 py-2 rounded-full text-[13px] font-bold border-2 disabled:opacity-50"
                      style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
                    >
                      거절
                    </button>
                    <button
                      onClick={() => handleAcceptReceived(inv.id)}
                      disabled={actingInvitationId === inv.id}
                      className="px-4 py-2 rounded-full text-[13px] font-bold text-white disabled:opacity-50"
                      style={{ background: C.terracotta }}
                    >
                      수락
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            <input
              value={inviteUrlInput}
              onChange={(e) => {
                setInviteUrlInput(e.target.value);
                setInviteUrlError("");
              }}
              placeholder="환자에게 받은 초대 링크나 코드를 붙여넣으세요"
              className="flex-1 min-w-[200px] px-4 py-3 rounded-xl border text-[14px] outline-none"
              style={{ borderColor: "rgba(30,26,23,0.15)" }}
            />
            <button
              onClick={handleOpenInviteUrl}
              className="px-5 py-3 rounded-full font-bold text-[14px] shrink-0"
              style={{ background: `${C.terracotta}15`, color: C.terracotta }}
            >
              확인
            </button>
          </div>
          {inviteUrlError && (
            <p className="text-[12px] mt-2" style={{ color: "#D94F4F" }}>{inviteUrlError}</p>
          )}
        </div>

        {showInvite && caregiverId && (
          <div className="mb-6">
            <InvitePatientPanel caregiverId={caregiverId} onCreated={load} />
          </div>
        )}

        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: C.muted }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="이름 검색"
            className="w-full pl-11 pr-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)" }}
          />
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          {loading ? (
            <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
          ) : filtered.length === 0 ? (
            <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>
              {patients.length === 0 ? "등록된 환자가 없어요." : "검색 결과가 없어요."}
            </p>
          ) : (
            filtered.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between gap-4 px-6 py-4 border-b last:border-0"
                style={{ borderColor: "rgba(30,26,23,0.06)" }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-11 h-11 rounded-2xl flex items-center justify-center text-white text-[16px] font-black shrink-0"
                    style={{ background: C.terracotta }}
                  >
                    {p.name[0]}
                  </div>
                  <div>
                    <p className="text-[15px] font-bold" style={{ color: C.dark }}>{p.name}</p>
                    <p className="text-[13px]" style={{ color: C.muted }}>{p.note || "특이사항 없음"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
                  <button
                    onClick={() => openPatientMenu(p.id, "/schedule")}
                    className="px-4 py-2 rounded-full text-[13px] font-bold"
                    style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                  >
                    <CalendarClock className="inline w-3.5 h-3.5 mr-1" /> 복약일정
                  </button>
                  <button
                    onClick={() => openPatientMenu(p.id, "/notification")}
                    className="px-4 py-2 rounded-full text-[13px] font-bold"
                    style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                  >
                    <Bell className="inline w-3.5 h-3.5 mr-1" /> 알림설정
                  </button>
                  <button
                    onClick={() => openPatientMenu(p.id, "/records")}
                    className="px-4 py-2 rounded-full text-[13px] font-bold"
                    style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                  >
                    <ClipboardList className="inline w-3.5 h-3.5 mr-1" /> 등록내역
                  </button>
                  <button
                    onClick={() => openPatientMenu(p.id, "/monitoring")}
                    className="px-4 py-2 rounded-full text-[13px] font-bold"
                    style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                  >
                    <LayoutDashboard className="inline w-3.5 h-3.5 mr-1" /> 모니터링
                  </button>
                  <button
                    onClick={() => remove(p.id)}
                    aria-label="환자 연결 해제"
                    className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-black/5"
                    style={{ color: C.muted }}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
