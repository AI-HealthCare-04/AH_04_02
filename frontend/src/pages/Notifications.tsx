import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, AlertTriangle, FileEdit, CheckCircle2, Link2, Unlink } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import { getNotifications, type NotificationLogEntry } from "../api/monitoring";
import { listCorrectionNotices, markCorrectionNoticeRead, type RecordCorrectionNotice } from "../api/records";
import { listRelationNotices, markRelationNoticeRead, type RelationNotice } from "../api/care";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

const KIND_META: Record<NotificationLogEntry["kind"], { label: string; bg: string; color: string }> = {
  reminder: { label: "복약 알림", bg: `${C.terracotta}18`, color: C.terracotta },
  missed: { label: "놓침 감지", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
};

// [2026-07-25 추가] 처방전 검토/수정 알림 — review_pending(보호자·기관에게: 새 처방전 등록됨),
// correction_requested(환자에게: 수정 요청 옴), correction_completed(보호자·기관에게: 환자가 수정함)
const CORRECTION_META: Record<RecordCorrectionNotice["event"], { label: string; bg: string; color: string }> = {
  review_pending: { label: "검토 요청", bg: `${C.terracotta}18`, color: C.terracotta },
  correction_requested: { label: "수정 요청", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
  correction_completed: { label: "수정 완료", bg: `${C.success}18`, color: "#4A7A47" },
};

const RELATION_META: Record<RelationNotice["event"], { label: string; bg: string; color: string }> = {
  linked: { label: "환자 연결", bg: `${C.success}18`, color: "#4A7A47" },
  unlinked: { label: "연결 해제", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
  revocation_approved: { label: "해제 승인", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
  revocation_rejected: { label: "해제 거부", bg: `${C.terracotta}18`, color: C.terracotta },
};

// [2026-07-25 추가] 세 종류의 알림(복약 알림/놓침 감지, 처방전 검토·수정, 환자 연결)을
// 시간순 한 목록으로 합쳐서 보여준다 — 알림함 하나로 통일.
type UnifiedEntry =
  | { kind: "reminder"; id: string; timestamp: string; entry: NotificationLogEntry }
  | { kind: "correction"; id: string; timestamp: string; notice: RecordCorrectionNotice }
  | { kind: "relation"; id: string; timestamp: string; notice: RelationNotice };

export default function Notifications() {
  const navigate = useNavigate();
  // silent: 처방전·연결 알림은 특정 환자에 묶이지 않으므로, 환자가 아직 안 정해졌다고
  // 화면 전체를 /patients로 떠나보내면 안 됨(그 알림 자체를 못 보게 됨).
  const patientId = useGuardedPatientId({ silent: true });
  const [reminders, setReminders] = useState<NotificationLogEntry[]>([]);
  const [correctionNotices, setCorrectionNotices] = useState<RecordCorrectionNotice[]>([]);
  const [relationNotices, setRelationNotices] = useState<RelationNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (patientId == null) return;
    getNotifications(patientId).then(setReminders).catch(() => {});
  }, [patientId]);

  useEffect(() => {
    Promise.all([
      listCorrectionNotices().catch(() => []),
      listRelationNotices().catch(() => []),
    ])
      .then(([corrections, relations]) => {
        setCorrectionNotices(corrections);
        setRelationNotices(relations);
      })
      .catch(() => setError("알림을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, []);

  const handleCorrectionClick = async (notice: RecordCorrectionNotice) => {
    await markCorrectionNoticeRead(notice.id).catch(() => {});
    setCorrectionNotices((prev) => prev.filter((n) => n.id !== notice.id));
    navigate(notice.event === "correction_requested" ? `/records/${notice.record_id}/review?mode=correction` : `/records/${notice.record_id}/guide`);
  };

  const handleRelationClick = async (notice: RelationNotice) => {
    await markRelationNoticeRead(notice.id).catch(() => {});
    setRelationNotices((prev) => prev.filter((n) => n.id !== notice.id));
    navigate("/connect");
  };

  const entries: UnifiedEntry[] = [
    ...reminders.map((r): UnifiedEntry => ({ kind: "reminder", id: `reminder:${r.id}`, timestamp: r.fired_at, entry: r })),
    ...correctionNotices.map((n): UnifiedEntry => ({ kind: "correction", id: `correction:${n.id}`, timestamp: n.created_at, notice: n })),
    ...relationNotices.map((n): UnifiedEntry => ({ kind: "relation", id: `relation:${n.id}`, timestamp: n.created_at, notice: n })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>알림함</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          복약 알림·놓침 감지부터 처방전 검토·수정, 환자 연결 소식까지 한눈에 모아 봐요.
        </p>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <div className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-start gap-3 px-5 py-4" style={{ borderBottom: i < 3 ? "1px solid rgba(30,26,23,0.06)" : undefined }}>
                <Skeleton className="w-9 h-9 shrink-0" />
                <div className="flex-1 min-w-0">
                  <Skeleton className="h-4 w-32 mb-2" />
                  <Skeleton className="h-3 w-48" />
                </div>
              </div>
            ))}
          </div>
        ) : entries.length === 0 ? (
          <EmptyState icon={Bell} title="아직 온 알림이 없어요" />
        ) : (
          <div className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            {entries.map((entry, i) => {
              const border = { borderBottom: i < entries.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined };

              if (entry.kind === "reminder") {
                const r = entry.entry;
                const meta = KIND_META[r.kind];
                return (
                  <div key={entry.id} className="flex items-start gap-3 px-5 py-4" style={border}>
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: meta.bg }}>
                      {r.kind === "missed" ? (
                        <AlertTriangle className="w-4 h-4" style={{ color: meta.color }} />
                      ) : (
                        <Bell className="w-4 h-4" style={{ color: meta.color }} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="font-bold text-[14px]" style={{ color: C.dark }}>{r.drug_name}</span>
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold" style={{ background: meta.bg, color: meta.color }}>
                          {meta.label}
                        </span>
                      </div>
                      <p className="text-[13px]" style={{ color: C.muted }}>
                        {new Date(r.fired_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        {" · "}복용 시간 {r.time_slot}
                        {r.status === "suppressed" && " · 알림 꺼짐(발송 안 됨)"}
                      </p>
                    </div>
                  </div>
                );
              }

              if (entry.kind === "correction") {
                const n = entry.notice;
                const meta = CORRECTION_META[n.event];
                return (
                  <button
                    key={entry.id}
                    onClick={() => handleCorrectionClick(n)}
                    className="w-full flex items-start gap-3 px-5 py-4 text-left hover:opacity-80 transition-opacity"
                    style={border}
                  >
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: meta.bg }}>
                      {n.event === "correction_completed" ? (
                        <CheckCircle2 className="w-4 h-4" style={{ color: meta.color }} />
                      ) : (
                        <FileEdit className="w-4 h-4" style={{ color: meta.color }} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="font-bold text-[14px]" style={{ color: C.dark }}>{n.patient_name}님의 처방전</span>
                        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold" style={{ background: meta.bg, color: meta.color }}>
                          {meta.label}
                        </span>
                      </div>
                      <p className="text-[13px]" style={{ color: C.muted }}>
                        {new Date(n.created_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </p>
                    </div>
                  </button>
                );
              }

              const n = entry.notice;
              const meta = RELATION_META[n.event];
              return (
                <button
                  key={entry.id}
                  onClick={() => handleRelationClick(n)}
                  className="w-full flex items-start gap-3 px-5 py-4 text-left hover:opacity-80 transition-opacity"
                  style={border}
                >
                  <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: meta.bg }}>
                    {n.event === "linked" ? (
                      <Link2 className="w-4 h-4" style={{ color: meta.color }} />
                    ) : (
                      <Unlink className="w-4 h-4" style={{ color: meta.color }} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="font-bold text-[14px]" style={{ color: C.dark }}>{n.patient_name} · {n.counterpart_name}</span>
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold" style={{ background: meta.bg, color: meta.color }}>
                        {meta.label}
                      </span>
                    </div>
                    <p className="text-[13px]" style={{ color: C.muted }}>
                      {new Date(n.created_at).toLocaleString("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      {n.reason && ` · ${n.reason}`}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
