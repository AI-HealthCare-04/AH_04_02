import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CalendarClock, ChevronLeft, ClipboardList, LayoutDashboard, Search, X } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import { getCaregiverPatients, getCaregivers, unlinkCaregiverPatient, type Caregiver, type Patient } from "../api/monitoring";
import { computeAge, GENDER_LABEL } from "../lib/age";
import { getCurrentCaregiverId, getCurrentUserName, isLoggedIn } from "../lib/session";
import { C } from "../theme";

const STATUS_META: Record<Patient["medication_status"], { label: string; bg: string; color: string }> = {
  active: { label: "복약중", bg: `${C.success}30`, color: C.successText },
  paused: { label: "중단", bg: "rgba(30,26,23,0.08)", color: C.muted },
  none: { label: "-", bg: "rgba(30,26,23,0.04)", color: C.muted },
};

export default function PatientManagement() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  // [2026-07-22 추가] 환자 관리 테이블 필터(Figma 목업) — 상태/나이 범위.
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "paused">("all");
  const [minAge, setMinAge] = useState("");
  const [maxAge, setMaxAge] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // [2026-07-23 추가] 기관(organization) 계정인지 확인 — 기관이 연결을 끊을 땐 사유 입력과
  // 상대 승인이 필요하다(REQ-004 확장).
  const [myCaregiver, setMyCaregiver] = useState<Caregiver | null>(null);

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

  useEffect(() => {
    load();
    if (caregiverId) {
      getCaregivers()
        .then((list) => setMyCaregiver(list[0] ?? null))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = patients.filter((p) => {
    if (search && !p.name.includes(search)) return false;
    if (statusFilter !== "all" && p.medication_status !== statusFilter) return false;
    const age = computeAge(p.birth_date);
    if (minAge.trim() && (age === null || age < Number(minAge))) return false;
    if (maxAge.trim() && (age === null || age > Number(maxAge))) return false;
    return true;
  });

  const resetFilters = () => {
    setSearch("");
    setStatusFilter("all");
    setMinAge("");
    setMaxAge("");
  };

  const openPatientMenu = (id: number, path: string) => {
    localStorage.setItem("patient_id", String(id));
    navigate(path);
  };

  const remove = async (id: number) => {
    if (!caregiverId) return;
    setError("");

    // [2026-07-23 수정] window.prompt()는 브라우저 네이티브 팝업이라 한글(IME) 입력이
    // 제대로 안 되는 문제가 있었다 — 사유 입력은 전용 화면(DisconnectPatient.tsx)에서
    // 일반 React 입력창으로 받는다. 기관은 사유 없이 일방적으로 연결을 끊을 수 없다 —
    // 환자가 스스로 관리하지 못하는 상황에서 기관이 손을 떼는 걸 막기 위해, 사유를
    // 남기고 환자·다른 보호자의 승인을 받아야 실제로 끊긴다(2주 안에 응답 없으면 자동 확정).
    if (myCaregiver?.relation_type === "organization") {
      navigate(`/patients/${id}/disconnect`);
      return;
    }
    if (!window.confirm("이 환자와의 연결을 해제할까요? 환자 계정과 기록은 삭제되지 않아요.")) {
      return;
    }

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
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-6xl mx-auto px-6 sm:px-8 py-10">
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
            <p className="text-[14px] mt-1" style={{ color: C.muted }}>연결된 환자 {patients.length}명의 복약 현황을 관리하세요.</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-6">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: C.muted }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="이름 검색"
              className="w-full pl-11 pr-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
              style={{ borderColor: "rgba(30,26,23,0.15)" }}
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "all" | "active" | "paused")}
            className="px-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
          >
            <option value="all">전체</option>
            <option value="active">복약중</option>
            <option value="paused">중단</option>
          </select>
          <input
            value={minAge}
            onChange={(e) => setMinAge(e.target.value.replace(/\D/g, ""))}
            placeholder="최소 나이"
            inputMode="numeric"
            className="w-24 px-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)" }}
          />
          <input
            value={maxAge}
            onChange={(e) => setMaxAge(e.target.value.replace(/\D/g, ""))}
            placeholder="최대 나이"
            inputMode="numeric"
            className="w-24 px-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)" }}
          />
          <button
            onClick={resetFilters}
            className="px-5 py-3 rounded-xl font-bold text-[14px] shrink-0"
            style={{ background: "rgba(30,26,23,0.05)", color: C.dark }}
          >
            초기화
          </button>
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        <div className="rounded-2xl overflow-hidden overflow-x-auto" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          {loading ? (
            <div className="p-6 space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-4 w-28" />
                </div>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>
              {patients.length === 0 ? "등록된 환자가 없어요." : "검색 결과가 없어요."}
            </p>
          ) : (
            <table className="w-full text-left" style={{ minWidth: 760 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(30,26,23,0.08)" }}>
                  {["ID", "이름", "나이", "성별", "전화번호", "진단명", "상태", "관리", "오늘"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-[11px] font-bold uppercase tracking-wider whitespace-nowrap"
                      style={{ color: C.muted }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => {
                  const age = computeAge(p.birth_date);
                  const status = STATUS_META[p.medication_status];
                  return (
                    <tr key={p.id} className="border-b last:border-0" style={{ borderColor: "rgba(30,26,23,0.06)" }}>
                      <td className="px-4 py-4 text-[13px]" style={{ color: C.muted }}>{p.id}</td>
                      <td className="px-4 py-4 text-[15px] font-bold whitespace-nowrap" style={{ color: C.dark }}>{p.name}</td>
                      <td className="px-4 py-4 text-[14px] whitespace-nowrap" style={{ color: C.dark }}>
                        {age !== null ? `${age}세` : "-"}
                      </td>
                      <td className="px-4 py-4 text-[14px] whitespace-nowrap" style={{ color: C.dark }}>
                        {p.gender ? GENDER_LABEL[p.gender] : "-"}
                      </td>
                      <td className="px-4 py-4 text-[14px] whitespace-nowrap" style={{ color: C.dark }}>{p.phone ?? "-"}</td>
                      <td className="px-4 py-4 text-[14px]" style={{ color: C.dark }}>{p.diagnoses ?? "-"}</td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span
                          className="px-3 py-1.5 rounded-full text-[12px] font-bold"
                          style={{ background: status.bg, color: status.color }}
                        >
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            onClick={() => openPatientMenu(p.id, "/schedule")}
                            className="px-4 py-2 rounded-full text-[13px] font-bold whitespace-nowrap"
                            style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                          >
                            <CalendarClock className="inline w-3.5 h-3.5 mr-1" /> 복약일정
                          </button>
                          <button
                            onClick={() => openPatientMenu(p.id, "/notification")}
                            className="px-4 py-2 rounded-full text-[13px] font-bold whitespace-nowrap"
                            style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                          >
                            <Bell className="inline w-3.5 h-3.5 mr-1" /> 알림설정
                          </button>
                          <button
                            onClick={() => openPatientMenu(p.id, "/records")}
                            className="px-4 py-2 rounded-full text-[13px] font-bold whitespace-nowrap"
                            style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                          >
                            <ClipboardList className="inline w-3.5 h-3.5 mr-1" /> 등록내역
                          </button>
                          <button
                            onClick={() => openPatientMenu(p.id, `/monitoring?patient_id=${p.id}`)}
                            className="px-4 py-2 rounded-full text-[13px] font-bold whitespace-nowrap"
                            style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                          >
                            <LayoutDashboard className="inline w-3.5 h-3.5 mr-1" /> 모니터링
                          </button>
                          <button
                            onClick={() => remove(p.id)}
                            aria-label="환자 연결 해제"
                            className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-black/5 shrink-0"
                            style={{ color: C.muted }}
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span
                          title={p.today_status === "missed" ? "오늘 놓친 약이 있어요" : "오늘 복약 정상"}
                          className="inline-block w-3 h-3 rounded-full"
                          style={{ background: p.today_status === "missed" ? "#D94F4F" : C.success }}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        {!loading && patients.length > 0 && (
          <p className="text-[13px] mt-3" style={{ color: C.muted }}>
            총 {filtered.length}명 / 전체 {patients.length}명
          </p>
        )}
      </main>
    </div>
  );
}
