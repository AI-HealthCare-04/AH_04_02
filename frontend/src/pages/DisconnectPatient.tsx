import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, Check } from "lucide-react";
import NavBar from "../components/NavBar";
import { getCaregiverPatients, unlinkCaregiverPatient, type Patient } from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentUserName } from "../lib/session";
import { C } from "../theme";

/**
 * [2026-07-23 추가] 기관(organization) 계정이 환자와의 연결을 끊을 때 사유를 입력하는
 * 전용 화면 — 이전엔 window.prompt()를 썼는데, 브라우저 네이티브 팝업이라 한글
 * 입력(IME)이 제대로 안 되는 문제가 있었다. 일반 React 입력창(textarea)으로 바꿔서
 * 해결한다. 개인 보호자·환자 본인은 이 화면을 거치지 않고 기존처럼 즉시 처리된다
 * (PatientManagement.tsx/Connect.tsx가 기관 계정일 때만 이 화면으로 보낸다).
 */
export default function DisconnectPatient() {
  const navigate = useNavigate();
  const { patientId } = useParams<{ patientId: string }>();
  const caregiverId = getCurrentCaregiverId();

  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!caregiverId) return;
    getCaregiverPatients(caregiverId)
      .then((patients) => setPatient(patients.find((p) => p.id === Number(patientId)) ?? null))
      .catch(() => setError("환자 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [caregiverId, patientId]);

  const handleSubmit = async () => {
    if (!caregiverId || !patientId || !reason.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      await unlinkCaregiverPatient(caregiverId, Number(patientId), reason.trim());
      if (localStorage.getItem("patient_id") === patientId) {
        localStorage.removeItem("patient_id");
      }
      setDone(true);
    } catch {
      setError("연결 해제 요청을 보내지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-lg mx-auto px-6 sm:px-8 py-10">
        {done ? (
          <div className="rounded-2xl p-8 text-center" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ background: `${C.success}20` }}
            >
              <Check className="w-7 h-7" style={{ color: "#4A7A47" }} />
            </div>
            <h1 className="text-[20px] font-black mb-2" style={{ color: C.dark }}>연결 해제 요청을 보냈어요</h1>
            <p className="text-[14px] mb-6" style={{ color: C.muted }}>
              환자 또는 다른 보호자가 승인하거나, 2주 안에 응답이 없으면 자동으로 처리돼요.
            </p>
            <button
              onClick={() => navigate("/patients")}
              className="w-full py-3.5 rounded-full text-white font-bold text-[15px]"
              style={{ background: C.terracotta }}
            >
              환자 관리로 돌아가기
            </button>
          </div>
        ) : (
          <div className="rounded-2xl p-8" style={{ background: C.surface, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-5 h-5" style={{ color: "#D94F4F" }} />
              <h1 className="text-[20px] font-black" style={{ color: C.dark }}>
                {loading ? "환자" : patient?.name ?? "환자"}님과의 연결을 끊으시겠어요?
              </h1>
            </div>
            <p className="text-[14px] mb-5" style={{ color: C.muted }}>
              기관 계정은 사유를 남겨야 연결을 끊을 수 있어요. 환자 또는 다른 보호자가 승인해야 실제로
              연결이 끊기고, 2주 안에 응답이 없으면 자동으로 처리돼요.
            </p>

            <label className="block text-[13px] font-bold mb-2" style={{ color: C.dark }}>
              연결을 끊는 사유
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="예: 환자가 타 시설로 전원했어요"
              rows={4}
              className="w-full px-4 py-3.5 rounded-xl border text-[15px] outline-none resize-none mb-5"
              style={{ borderColor: "rgba(30,26,23,0.15)", background: C.white, color: C.dark }}
            />

            {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

            <div className="flex gap-3">
              <button
                onClick={() => navigate(-1)}
                disabled={submitting}
                className="flex-1 py-3.5 rounded-full font-bold text-[15px] border-2 disabled:opacity-60"
                style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
              >
                취소
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !reason.trim()}
                className="flex-1 py-3.5 rounded-full font-bold text-[15px] text-white disabled:opacity-50"
                style={{ background: "#D94F4F" }}
              >
                {submitting ? "보내는 중..." : "연결 해제 요청"}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
