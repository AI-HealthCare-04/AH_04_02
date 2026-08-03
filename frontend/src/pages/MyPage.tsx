import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, IdCard, Pill, Bell, Inbox, ClipboardList, BarChart3, Users, Settings, Stethoscope } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import NavBar from "../components/NavBar";
import { getCaregivers, getPatients, type Caregiver, type Patient } from "../api/monitoring";
import { computeAge, GENDER_LABEL } from "../lib/age";
import { getCurrentCaregiverId, getCurrentPatientId, isLoggedIn } from "../lib/session";
import { C } from "../theme";

interface MenuItem {
  label: string;
  icon: LucideIcon;
  to: string;
}

export default function MyPage() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const patientId = getCurrentPatientId();
  const [caregiver, setCaregiver] = useState<Caregiver | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        if (caregiverId) {
          const list = await getCaregivers();
          setCaregiver(list.find((c) => c.id === caregiverId) ?? null);
        }
        const patients = await getPatients();
        setPatient(patients.find((p) => p.id === patientId) ?? null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [caregiverId, patientId]);

  const caregiverDisplayName =
    caregiver?.relation_type === "organization" && caregiver.manager_name?.trim()
      ? caregiver.manager_name.trim()
      : caregiver?.name;
  const displayName = caregiverDisplayName ?? (patient ? patient.name : "사용자");
  const roleLabel = caregiver
    ? { text: `보호자 (${relationLabel(caregiver.relation_type)})`, bg: `${C.terracottaLight}20`, color: C.terracotta }
    : { text: "복약관리 대상자", bg: `${C.success}20`, color: "#4A7A47" };
  // [2026-07-24 추가] 환자 본인 프로필에 성별·나이 표시 — 회원가입 때 받은 생년월일로
  // 만 나이를 계산한다. 보호자 계정엔 해당 없는 정보라 caregiver가 없을 때만 만든다.
  const patientAge = patient ? computeAge(patient.birth_date) : null;
  const patientGenderLabel = patient?.gender ? (GENDER_LABEL[patient.gender] ?? patient.gender) : null;
  const patientMeta = !caregiver
    ? [patientGenderLabel, patientAge != null ? `만 ${patientAge}세` : null].filter(Boolean).join(" · ")
    : "";

  const patientMenu: MenuItem[] = [
    { label: "내 정보", icon: IdCard, to: "/mypage/info" },
    { label: "복약 알림", icon: Pill, to: "/schedule" },
    { label: "알림 설정", icon: Bell, to: "/notification" },
    { label: "알림함", icon: Inbox, to: "/notifications" },
    { label: "처방전 목록", icon: ClipboardList, to: "/records" },
    { label: "모니터링", icon: BarChart3, to: "/monitoring" },
    { label: "연결관리", icon: Users, to: "/connect" },
    { label: "설정", icon: Settings, to: "/settings" },
  ];
  const caregiverMenu: MenuItem[] = [
    { label: "내 정보", icon: IdCard, to: "/mypage/info" },
    { label: "환자 관리", icon: Stethoscope, to: "/patients" },
    { label: "알림함", icon: Inbox, to: "/notifications" },
    { label: "모니터링", icon: BarChart3, to: "/monitoring" },
    { label: "연결관리", icon: Users, to: "/connect" },
    { label: "설정", icon: Settings, to: "/settings" },
  ];
  const menu = caregiverId ? caregiverMenu : patientMenu;

  const switchUser = () => {
    if (!window.confirm("다른 사용자로 전환할까요? 지금 화면에서 로그아웃돼요.")) return;
    localStorage.removeItem("patient_id");
    localStorage.removeItem("caregiver_id");
    navigate("/login");
  };

  const logout = () => {
    if (!window.confirm("로그아웃할까요?")) return;
    localStorage.removeItem("access_token");
    localStorage.removeItem("patient_id");
    localStorage.removeItem("caregiver_id");
    localStorage.removeItem("user_name");
    navigate("/");
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn={isLoggedIn()} userName={displayName} />
      <main className="max-w-xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black mb-7" style={{ color: C.dark }}>마이페이지</h1>

        <div className="rounded-2xl p-6 mb-6" style={{ background: C.surface, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
          <div className="flex items-center gap-4 mb-1">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-xl font-black shrink-0"
              style={{ background: C.terracotta }}
            >
              {displayName[0]}
            </div>
            <div>
              <p className="text-[19px] font-black" style={{ color: C.dark }}>{loading ? "..." : displayName}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span
                  className="inline-block px-3 py-1 rounded-full text-[12px] font-bold"
                  style={{ background: roleLabel.bg, color: roleLabel.color }}
                >
                  {roleLabel.text}
                </span>
                {patientMeta && (
                  <span className="text-[13px] font-semibold" style={{ color: C.muted }}>
                    {patientMeta}
                  </span>
                )}
              </div>
            </div>
          </div>
          {patient?.note && !caregiver && (
            <p className="text-[13px] mt-4 pt-4" style={{ color: C.muted, borderTop: "1px solid rgba(30,26,23,0.08)" }}>
              {patient.note}
            </p>
          )}
        </div>

        <div className="rounded-2xl overflow-hidden mb-8" style={{ background: C.surface, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
          {menu.map(({ label, icon: Icon, to }) => (
            <button
              key={label}
              onClick={() => navigate(to)}
              className="w-full flex items-center justify-between px-6 py-4 hover:bg-black/[0.03] transition-colors border-b last:border-b-0"
              style={{ borderColor: "rgba(30,26,23,0.08)" }}
            >
              <div className="flex items-center gap-3">
                {/* [2026-07-27 변경] 색깔 이모지 → lucide 아이콘. 고령 사용자 기준 대비를
                    높이기 위해 옅은 톤 배경 대신 브랜드색(터라코타) 배경 + 흰 아이콘으로 통일. */}
                <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: C.terracotta }}>
                  <Icon className="w-[18px] h-[18px]" style={{ color: C.white }} strokeWidth={2.2} />
                </div>
                <span className="text-[15px] font-semibold" style={{ color: C.dark }}>{label}</span>
              </div>
              <ChevronRight className="w-4 h-4" style={{ color: C.muted }} />
            </button>
          ))}
        </div>

        <button
          onClick={switchUser}
          className="w-full py-3.5 rounded-full border-2 font-bold text-[15px] transition-colors hover:bg-black/[0.03]"
          style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
        >
          다른 사용자로 전환
        </button>
        <button
          onClick={logout}
          className="w-full py-3 mt-2 font-bold text-[14px] transition-opacity hover:opacity-70"
          style={{ color: C.muted }}
        >
          로그아웃
        </button>
      </main>
    </div>
  );
}

function relationLabel(relationType: string) {
  const map: Record<string, string> = {
    guardian: "보호자",
    organization: "지원인력",
    caregiver: "돌봄제공자",
    life_support_worker: "생활지원사",
    social_worker: "사회복지사",
  };
  return map[relationType] ?? relationType;
}
