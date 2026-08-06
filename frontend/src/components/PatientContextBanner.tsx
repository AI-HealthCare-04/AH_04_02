import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, User } from "lucide-react";
import { getCaregiverPatients, type Patient } from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

/**
 * [2026-07-23 추가] 보호자/기관 계정이 환자 공유 화면(Dashboard/Schedule/Notification 등)에
 * 들어왔을 때 "지금 누구 화면인지" 알려주고, 클릭 한 번으로 다른 환자로 바로 전환할 수
 * 있게 한다 — 여러 환자를 오가는 기관 계정이 실수로 엉뚱한 환자 데이터를 고치는 걸 막기
 * 위함(단순 이름 표시만으로는 "전환이 귀찮아서 그냥 이 화면에서 처리"하는 습관이 생길
 * 수 있어, 전환 자체를 여기서 바로 할 수 있게 했다).
 *
 * 환자 본인 로그인이면 렌더링하지 않는다(자기 자신 화면이라 모호할 게 없음).
 * 각 페이지의 <main> 맨 위에 그대로 넣어 쓰면 그 페이지의 폭을 그대로 물려받는다.
 *
 * @param afterSwitchPath URL 자체가 특정 환자의 리소스(예: /drugs/:scheduleId,
 * /monitoring/logs/:date?patient_id=)를 가리키는 화면에서 쓴다 — 그냥 새로고침하면
 * 새 환자로 안 바뀌거나(쿼리파라미터가 우선이라) 다른 환자의 URL을 그대로 보여주게
 * 되므로, 전환 후 이 안전한 경로로 이동시킨다.
 */
export default function PatientContextBanner({ afterSwitchPath }: { afterSwitchPath?: string }) {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!caregiverId) return;
    getCaregiverPatients(caregiverId)
      .then(setPatients)
      .catch(() => {});
  }, [caregiverId]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!caregiverId || patients.length === 0) return null;

  const currentId = getCurrentPatientId();
  const current = patients.find((p) => p.id === currentId);

  const switchTo = (id: number) => {
    if (id === currentId) {
      setOpen(false);
      return;
    }
    localStorage.setItem("patient_id", String(id));
    if (afterSwitchPath) {
      navigate(afterSwitchPath);
      return;
    }
    // [의도적] 이 화면들 대부분이 patientId를 mount 시점에 한 번 읽어와서 상태로 굳히므로
    // (useGuardedPatientId 등), 새로고침이 모든 하위 fetch를 새 환자 기준으로 다시 맞추는
    // 가장 단순하고 확실한 방법이다.
    window.location.reload();
  };

  return (
    <div ref={ref} className="relative inline-block mb-5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-bold"
        style={{ background: `${C.terracotta}12`, color: C.terracotta }}
      >
        <User className="w-3.5 h-3.5" />
        {current ? `${current.name}님의 화면이에요` : "환자를 선택해 주세요"}
        {patients.length > 1 && <ChevronDown className="w-3.5 h-3.5" />}
      </button>
      {open && patients.length > 1 && (
        <div
          className="absolute z-20 mt-1 min-w-[180px] rounded-xl overflow-hidden"
          style={{ background: C.white, boxShadow: C.shadowDropdown, border: "1px solid rgba(30,26,23,0.10)" }}
        >
          {patients.map((p) => (
            <button
              key={p.id}
              onClick={() => switchTo(p.id)}
              className="w-full text-left px-4 py-2.5 text-[14px] hover:bg-black/[0.03] whitespace-nowrap"
              style={{ color: p.id === currentId ? C.terracotta : C.dark, fontWeight: p.id === currentId ? 700 : 500 }}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
