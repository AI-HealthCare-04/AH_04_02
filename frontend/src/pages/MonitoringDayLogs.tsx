import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft, Clock, FileText, Heart } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import PatientContextBanner from "../components/PatientContextBanner";
import { getLogs, type MedicationLogEntry } from "../api/monitoring";
import { listRecords, type RecordSummary } from "../api/records";
import { getCurrentUserName, useGuardedPatientId } from "../lib/session";
import { C } from "../theme";

function dateKey(iso: string) {
  return iso.slice(0, 10);
}

// [2026-07-25 추가] 보호자·기관 시점의 검토 상태 뱃지 — "none"(대상 아님)은 안 보여준다.
const REVIEW_STATUS_LABEL: Record<string, { text: string; bg: string; color: string }> = {
  pending: { text: "검토해 주세요", bg: `${C.terracotta}15`, color: C.terracotta },
  needs_correction: { text: "환자 수정 대기 중", bg: "#F5E6C8", color: "#8A6D1F" },
  reviewed: { text: "검토 완료", bg: `${C.success}20`, color: "#4A7A47" },
};

// ponytail: 특정 날짜 하나만 콕 집어 조회하는 백엔드 엔드포인트가 따로 없어서,
// 넉넉한 기간(1년치) 로그를 받아 프론트에서 그 날짜만 걸러냅니다 — 데이터량이
// 작아서(가정용 복약 기록) 실용적인 선택. 나중에 기록이 많아지면 GET /monitoring/logs에
// date 파라미터를 추가해 서버에서 필터링하도록 바꾸면 됩니다.
export default function MonitoringDayLogs() {
  const navigate = useNavigate();
  const { date } = useParams<{ date: string }>();
  const [searchParams] = useSearchParams();
  const guardedPatientId = useGuardedPatientId();
  const patientId = Number(searchParams.get("patient_id")) || guardedPatientId;

  const [logs, setLogs] = useState<MedicationLogEntry[]>([]);
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (patientId == null) return;
    Promise.all([getLogs(patientId, 366), listRecords(patientId)])
      .then(([l, r]) => {
        setLogs(l);
        setRecords(r);
      })
      .catch(() => setError("기록을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const dayLogs = logs
    .filter((l) => dateKey(l.checked_at) === date)
    .sort((a, b) => +new Date(a.checked_at) - +new Date(b.checked_at));

  const displayDate = date ? date.replace(/-/g, ".") : "";

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner afterSwitchPath="/monitoring" />
        <button
          onClick={() => navigate("/monitoring")}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 모니터링으로
        </button>

        <div className="flex items-center justify-between mb-6">
          <div>
            <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>날짜별 복약 기록</p>
            <h1 className="text-[26px] font-black" style={{ color: C.dark }}>{displayDate}</h1>
          </div>
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"
            style={{ background: `${C.terracotta}12` }}
          >
            <Clock className="w-5 h-5" style={{ color: C.terracotta }} />
          </div>
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
        ) : (
          <>
            <div className="rounded-2xl overflow-hidden mb-8" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
              {dayLogs.length === 0 ? (
                <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>이 날짜엔 복약 기록이 없어요.</p>
              ) : (
                <>
                  <div className="sm:hidden">
                    {dayLogs.map((log, i) => (
                      <div key={log.id} className="px-5 py-4" style={{ borderBottom: i < dayLogs.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}>
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="font-bold text-[14px]" style={{ color: C.dark }}>{log.drug_name}</span>
                          <span
                            className="shrink-0 px-3 py-1 rounded-full text-[12px] font-bold"
                            style={{
                              background: log.status === "taken" ? `${C.success}20` : "rgba(217,79,79,0.12)",
                              color: log.status === "taken" ? "#4A7A47" : "#D94F4F",
                            }}
                          >
                            {log.status === "taken" ? "복용완료" : log.status === "missed" ? "놓침" : "건너뜀"}
                          </span>
                        </div>
                        <p className="text-[13px]" style={{ color: C.muted }}>
                          {new Date(log.checked_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                          {log.confirmed_by_name ? ` · 확인자 ${log.confirmed_by_name}` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                  <table className="w-full hidden sm:table">
                    <thead>
                      <tr style={{ borderBottom: "1px solid rgba(30,26,23,0.08)" }}>
                        {["약 이름", "복용 시각", "상태", "확인자"].map((h) => (
                          <th key={h} className="px-5 py-3 text-left text-[11px] font-bold uppercase tracking-wider" style={{ color: C.muted }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {dayLogs.map((log, i) => (
                        <tr key={log.id} style={{ borderBottom: i < dayLogs.length - 1 ? "1px solid rgba(30,26,23,0.06)" : undefined }}>
                          <td className="px-5 py-3.5 font-bold text-[14px]" style={{ color: C.dark }}>{log.drug_name}</td>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>
                            {new Date(log.checked_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                          </td>
                          <td className="px-5 py-3.5">
                            <span
                              className="px-3 py-1 rounded-full text-[12px] font-bold"
                              style={{
                                background: log.status === "taken" ? `${C.success}20` : "rgba(217,79,79,0.12)",
                                color: log.status === "taken" ? "#4A7A47" : "#D94F4F",
                              }}
                            >
                              {log.status === "taken" ? "복용완료" : log.status === "missed" ? "놓침" : "건너뜀"}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-[13px]" style={{ color: C.muted }}>{log.confirmed_by_name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>

            <h2 className="text-[18px] font-black mb-4" style={{ color: C.dark }}>전체 처방 기록</h2>
            <div className="space-y-4">
              {records.length === 0 ? (
                <div className="rounded-2xl p-10 text-center" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                  <p className="text-[14px]" style={{ color: C.muted }}>아직 업로드한 처방전이 없어요.</p>
                </div>
              ) : (
                records.map((r) => (
                  <div key={r.record_id} className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
                    {r.uploaded_by_name && (
                      <div className="flex items-center gap-1.5 px-6 py-2.5" style={{ background: `${C.terracotta}08` }}>
                        <Heart className="w-3.5 h-3.5" style={{ color: C.terracotta }} />
                        <span className="text-[12px] font-bold" style={{ color: C.terracotta }}>
                          {r.uploaded_by_name}님이 대신 올려드렸어요
                        </span>
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-4 p-6">
                      <div className="flex-1 min-w-0">
                        <p className="text-[12px] mb-1" style={{ color: C.muted }}>
                          업로드일 {new Date(r.created_at).toLocaleDateString("ko-KR")}
                        </p>
                        <p className="text-[16px] font-black mb-2" style={{ color: C.dark }}>{r.diagnosis || "진단명 확인 중"}</p>
                        <p className="text-[13px]" style={{ color: C.muted }}>
                          {r.drug_names.length > 0 ? r.drug_names.join(", ") : "인식된 약품 없음"}
                        </p>
                      </div>
                      <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${C.terracotta}12` }}>
                        <FileText className="w-5 h-5" style={{ color: C.terracotta }} />
                      </div>
                    </div>
                    <div className="px-6 pb-5 flex items-center gap-2 flex-wrap">
                      <button
                        onClick={() => navigate(`/records/${r.record_id}`)}
                        className="px-4 py-2 rounded-full text-[13px] font-bold"
                        style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                      >
                        자세히 보기 ›
                      </button>
                      {r.caregiver_review_status !== "none" && (
                        <button
                          onClick={() => navigate(`/records/${r.record_id}/guide`)}
                          className="px-4 py-2 rounded-full text-[13px] font-bold"
                          style={{
                            background: REVIEW_STATUS_LABEL[r.caregiver_review_status].bg,
                            color: REVIEW_STATUS_LABEL[r.caregiver_review_status].color,
                          }}
                        >
                          {REVIEW_STATUS_LABEL[r.caregiver_review_status].text}
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
