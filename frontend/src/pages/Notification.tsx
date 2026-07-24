import { useEffect, useState } from "react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import PatientContextBanner from "../components/PatientContextBanner";
import { getNotificationSettings, updateNotificationSettings, type NotificationSettings } from "../api/care";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

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

export default function Notification() {
  const patientId = useGuardedPatientId();
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    if (patientId == null) return;
    getNotificationSettings(patientId)
      .then(setSettings)
      .catch(() => setError("설정을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const toggle = async (key: keyof Pick<NotificationSettings, "medication_reminder_enabled" | "care_alert_enabled" | "all_push_enabled">) => {
    if (!settings || patientId == null) return;

    const next = { ...settings, [key]: !settings[key] };
    setSettings(next); // 낙관적 업데이트
    setSavingKey(key);
    try {
      await updateNotificationSettings(patientId, { [key]: next[key] });
    } catch {
      setSettings(settings); // 실패 시 롤백
      setError("저장하지 못했어요.");
    } finally {
      setSavingKey(null);
    }
  };

  const rows: { key: keyof Pick<NotificationSettings, "medication_reminder_enabled" | "care_alert_enabled" | "all_push_enabled">; label: string; desc: string }[] = [
    { key: "medication_reminder_enabled", label: "복약 알림", desc: "복약 시간에 맞춰 알림을 보내드립니다" },
    { key: "care_alert_enabled", label: "돌봄 알림", desc: "보호자·지원인력에게 복약 상태를 공유합니다" },
    { key: "all_push_enabled", label: "전체 푸시 수신", desc: "건강동행의 모든 알림을 받습니다" },
  ];

  return (
    <div className="min-h-screen bg-[#F2E8D8]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner />
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">알림 설정</h1>
        <p className="text-[14px] text-[#8A7E75] mb-7">받고 싶은 알림을 선택하세요.</p>

        {loading && <p className="text-[14px] text-[#8A7E75]"><LoadingDots /></p>}
        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        {settings && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6">
            {rows.map(({ key, label, desc }) => (
              <div key={key} className="flex items-start justify-between py-5 border-b border-[#F4F0EA] last:border-0">
                <div className="flex-1 pr-4">
                  <p className="text-[16px] font-bold text-[#1E1A17] mb-1">{label}</p>
                  <p className="text-[14px] text-[#8A7E75]">{desc}</p>
                </div>
                <Toggle on={settings[key]} onChange={() => toggle(key)} disabled={savingKey === key} />
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
