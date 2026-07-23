import { useEffect, useState } from "react";
import { Bell, AlertTriangle } from "lucide-react";
import NavBar from "../components/NavBar";
import { getNotifications, type NotificationLogEntry } from "../api/monitoring";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

const KIND_META: Record<NotificationLogEntry["kind"], { label: string; bg: string; color: string }> = {
  reminder: { label: "복약 알림", bg: `${C.terracotta}18`, color: C.terracotta },
  missed: { label: "놓침 감지", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
};

export default function Notifications() {
  const patientId = useGuardedPatientId();
  const [entries, setEntries] = useState<NotificationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (patientId == null) return;
    getNotifications(patientId)
      .then(setEntries)
      .catch(() => setError("알림을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>알림함</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          최근 30일간 보낸 복약 알림과 놓침 감지 기록이에요.
        </p>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : entries.length === 0 ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            <Bell className="w-8 h-8 mx-auto mb-3 opacity-30" style={{ color: C.muted }} />
            <p className="text-[14px]" style={{ color: C.muted }}>아직 온 알림이 없어요.</p>
          </div>
        ) : (
          <div className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            {entries.map((entry, i) => {
              const meta = KIND_META[entry.kind];
              return (
                <div
                  key={entry.id}
                  className="flex items-start gap-3 px-5 py-4"
                  style={{ borderBottom: i < entries.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}
                >
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: meta.bg }}
                  >
                    {entry.kind === "missed" ? (
                      <AlertTriangle className="w-4 h-4" style={{ color: meta.color }} />
                    ) : (
                      <Bell className="w-4 h-4" style={{ color: meta.color }} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="font-bold text-[14px]" style={{ color: C.dark }}>{entry.drug_name}</span>
                      <span
                        className="px-2.5 py-0.5 rounded-full text-[11px] font-bold"
                        style={{ background: meta.bg, color: meta.color }}
                      >
                        {meta.label}
                      </span>
                    </div>
                    <p className="text-[13px]" style={{ color: C.muted }}>
                      {new Date(entry.fired_at).toLocaleString("ko-KR", {
                        month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
                      })}
                      {" · "}복용 시간 {entry.time_slot}
                      {entry.status === "suppressed" && " · 알림 꺼짐(발송 안 됨)"}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
