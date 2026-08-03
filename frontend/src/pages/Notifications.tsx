import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, AlertTriangle, FileEdit, CheckCircle2, Link2, Trash2, Unlink } from "lucide-react";
import NavBar from "../components/NavBar";
import Skeleton from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import {
  acknowledgeNotifications,
  deleteNotification,
  deleteNotifications,
  getNotifications,
  type NotificationLogEntry,
} from "../api/monitoring";
import { listCorrectionNotices, markCorrectionNoticeRead, type RecordCorrectionNotice } from "../api/records";
import { listRelationNotices, markRelationNoticeRead, type RelationNotice } from "../api/care";
import { getCurrentCaregiverId, getCurrentUserName, isLoggedIn, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

const KIND_META: Record<NotificationLogEntry["kind"], { label: string; bg: string; color: string }> = {
  reminder: { label: "복약 알림", bg: `${C.terracotta}18`, color: C.terracotta },
  missed: { label: "놓침 감지", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
};

// [2026-07-25 추가] 처방전 검토/수정 알림 — review_pending(보호자·기관에게: 새 처방전 등록됨),
// correction_requested(환자에게: 수정 요청 옴), correction_completed(보호자·기관에게: 환자가 수정함)
// [2026-07-30 추가] review_completed(환자에게: 보호자·기관이 검토를 완료함)
const CORRECTION_META: Record<RecordCorrectionNotice["event"], { label: string; bg: string; color: string }> = {
  review_pending: { label: "검토 요청", bg: `${C.terracotta}18`, color: C.terracotta },
  correction_requested: { label: "수정 요청", bg: "rgba(217,79,79,0.12)", color: "#D94F4F" },
  correction_completed: { label: "수정 완료", bg: `${C.success}18`, color: "#4A7A47" },
  review_completed: { label: "검토 완료", bg: `${C.success}18`, color: "#4A7A47" },
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
  const [clearing, setClearing] = useState(false);
  const [selectedReminderIds, setSelectedReminderIds] = useState<Set<number>>(new Set());

  const handleDeleteReminder = async (id: number) => {
    if (patientId == null) return;
    await deleteNotification(patientId, id);
    setReminders((prev) => prev.filter((r) => r.id !== id));
    setSelectedReminderIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const handleDeleteSelected = async (ids: number[]) => {
    if (patientId == null || clearing || ids.length === 0) return;
    setClearing(true);
    setError("");
    try {
      await deleteNotifications(patientId, ids);
      const deletedIds = new Set(ids);
      setReminders((prev) => prev.filter((r) => !deletedIds.has(r.id)));
      setSelectedReminderIds((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.delete(id));
        return next;
      });
    } catch {
      setError("선택한 알림을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setClearing(false);
    }
  };

  const handleClearRead = async () => {
    if (patientId == null || clearing) return;
    setClearing(true);
    try {
      await deleteNotifications(patientId, reminders.map((reminder) => reminder.id));
      setReminders([]);
      setSelectedReminderIds(new Set());
    } catch {
      setError("확인한 알림을 정리하지 못했어요.");
    } finally {
      setClearing(false);
    }
  };

  useEffect(() => {
    if (patientId == null) return;
    getNotifications(patientId)
      .then(async (items) => {
        setReminders(items);
        await acknowledgeNotifications(patientId);
        const acknowledgedAt = new Date().toISOString();
        setReminders((current) => current.map((item) => ({
          ...item,
          acknowledged_at: item.acknowledged_at ?? acknowledgedAt,
        })));
      })
      // [2026-07-30 추가] 이 화면에 목록이 실제로 표시된 시점 = "읽음" 처리 기준.
      // 개별 항목이 클릭 대상이 없는 단순 로그라, 목록을 성공적으로 불러온 직후
      // 그 시점까지 안 읽었던 것 전부를 한 번에 표시 처리한다(실패해도 무시).
      .catch(() => {});
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
    // [2026-07-31 추가] correction_requested를 이제 환자뿐 아니라 다른 보호자·기관에게도
    // 보낸다 — 보호자·기관은 직접 수정하는 사람이 아니라 지켜보는 입장이라, 환자용 수정
    // 화면(review?mode=correction) 대신 다른 보호자용 알림과 동일하게 읽기 전용 가이드로 보낸다.
    const isCaregiver = getCurrentCaregiverId() != null;
    navigate(
      notice.event === "correction_requested" && !isCaregiver
        ? `/records/${notice.record_id}/review?mode=correction`
        : `/records/${notice.record_id}/guide`
    );
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
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <div className="flex items-center justify-between gap-4 mb-1">
          <h1 className="text-[26px] font-black" style={{ color: C.dark }}>알림함</h1>
          {patientId != null && reminders.length > 0 && (
            <button onClick={handleClearRead} disabled={clearing} className="text-[13px] font-bold disabled:opacity-50" style={{ color: C.muted }}>
              {clearing ? "정리 중..." : "확인한 복약 알림 모두 정리"}
            </button>
          )}
        </div>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          복약 알림·놓침 감지부터 처방전 검토·수정, 환자 연결 소식까지 한눈에 모아 봐요.
        </p>

        {patientId != null && reminders.length > 0 && (
          <div className="flex items-center justify-between gap-3 mb-4">
            <label className="flex items-center gap-2 text-[13px] font-bold cursor-pointer" style={{ color: C.dark }}>
              <input
                type="checkbox"
                checked={selectedReminderIds.size === reminders.length}
                onChange={(event) => setSelectedReminderIds(
                  event.target.checked ? new Set(reminders.map((reminder) => reminder.id)) : new Set()
                )}
                className="w-4 h-4"
              />
              복약 알림 전체 선택
            </label>
            <button
              onClick={() => handleDeleteSelected([...selectedReminderIds])}
              disabled={clearing || selectedReminderIds.size === 0}
              className="px-3 py-2 rounded-lg text-[13px] font-bold disabled:opacity-40"
              style={{ background: `${C.terracotta}18`, color: C.terracotta }}
            >
              선택 삭제 ({selectedReminderIds.size})
            </button>
          </div>
        )}

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
                    <input
                      type="checkbox"
                      checked={selectedReminderIds.has(r.id)}
                      onChange={(event) => setSelectedReminderIds((prev) => {
                        const next = new Set(prev);
                        if (event.target.checked) next.add(r.id);
                        else next.delete(r.id);
                        return next;
                      })}
                      aria-label={`${r.drug_name} 알림 선택`}
                      className="w-4 h-4 mt-2.5 shrink-0"
                    />
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
                    <button
                      onClick={() => handleDeleteReminder(r.id).catch(() => setError("알림을 삭제하지 못했어요."))}
                      aria-label={`${r.drug_name} 알림 삭제`}
                      className="p-2 rounded-lg hover:opacity-60"
                      style={{ color: C.muted }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
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
                      {n.event === "correction_completed" || n.event === "review_completed" ? (
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
