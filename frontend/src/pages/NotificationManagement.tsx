import { useEffect, useState } from "react";
import { BellOff } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import {
  getCaregiverPatients,
  updateCaregiverPatientNotifications,
  type Patient,
} from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentUserName, isLoggedIn } from "../lib/session";
import { C } from "../theme";

// [2026-07-30 신규] 여러 환자를 관리하는 보호자·기관이 "이 환자 알림은 이 기기로 안 받고
// 싶다"를 환자별로 개별 끄고 켤 수 있는 화면 — Notification.tsx(이 기기로 알림 받기 +
// 복약/돌봄 알림 종류 설정)와 별개로, "여러 환자 중 누구 알림을 받을지"만 다룬다.
function Toggle({ on, onChange, disabled = false }: { on: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={!disabled ? onChange : undefined}
      className="relative w-12 h-6 rounded-full shrink-0 transition-all"
      style={{ background: on ? (disabled ? `${C.success}99` : C.terracotta) : "rgba(30,26,23,0.15)", cursor: disabled ? "not-allowed" : "pointer" }}
    >
      <div
        className="absolute top-1 w-4 h-4 bg-white rounded-full transition-all"
        style={{ left: on ? "calc(100% - 20px)" : 4 }}
      />
    </button>
  );
}

export default function NotificationManagement() {
  const caregiverId = getCurrentCaregiverId();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    if (!caregiverId) {
      setError("로그인 정보를 확인할 수 없어요.");
      setLoading(false);
      return;
    }
    getCaregiverPatients(caregiverId)
      .then(setPatients)
      .catch(() => setError("환자 목록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [caregiverId]);

  const toggle = async (patient: Patient) => {
    if (!caregiverId) return;
    const next = !patient.notifications_enabled;
    // 낙관적 업데이트, 실패 시 롤백
    setPatients((prev) => prev.map((p) => (p.id === patient.id ? { ...p, notifications_enabled: next } : p)));
    setSavingId(patient.id);
    try {
      await updateCaregiverPatientNotifications(caregiverId, patient.id, next);
    } catch {
      setPatients((prev) => prev.map((p) => (p.id === patient.id ? { ...p, notifications_enabled: !next } : p)));
      setError("저장하지 못했어요.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#F2E8D8]">
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">알림 관리</h1>
        <p className="text-[14px] text-[#6E6259] mb-7">
          여러 환자를 관리하고 계시네요. 이 기기로 알림 받을 환자만 켜두세요.
        </p>

        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        {loading ? (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center justify-between gap-4 px-6 py-4 border-b border-[#F4F0EA] last:border-0">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="w-12 h-6 rounded-full shrink-0" />
              </div>
            ))}
          </div>
        ) : patients.length === 0 ? (
          <EmptyState icon={BellOff} title="관리 중인 환자가 없어요" description="환자와 먼저 연결해주세요" />
        ) : (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl overflow-hidden">
            {patients.map((patient) => (
              <div
                key={patient.id}
                className="flex items-center justify-between gap-4 px-6 py-4 border-b border-[#F4F0EA] last:border-0"
              >
                <p className="text-[16px] font-bold text-[#1E1A17]">{patient.name}</p>
                <Toggle
                  on={patient.notifications_enabled}
                  onChange={() => toggle(patient)}
                  disabled={savingId === patient.id}
                />
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
