import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, Plus, Search, X } from "lucide-react";
import NavBar from "../components/NavBar";
import { createPatient, deletePatient, getCaregiverPatients, linkCaregiverPatient, type Patient } from "../api/monitoring";
import { getCurrentCaregiverId } from "../lib/session";
import { C } from "../theme";

export default function PatientManagement() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

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
  }, []);

  const filtered = patients.filter((p) => !search || p.name.includes(search));

  const save = async () => {
    if (!name.trim() || !caregiverId) return;
    setSaving(true);
    try {
      const patient = await createPatient({ name: name.trim(), note: note.trim() || undefined });
      await linkCaregiverPatient(caregiverId, patient.id);
      setModalOpen(false);
      setName("");
      setNote("");
      await load();
    } catch {
      setError("환자를 등록하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm("이 환자 정보를 삭제할까요? 연결된 일정·기록에 영향을 줄 수 있어요.")) return;
    try {
      await deletePatient(id);
      setPatients((prev) => prev.filter((p) => p.id !== id));
    } catch {
      setError("삭제하지 못했어요.");
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김보호" />
      <main className="max-w-3xl mx-auto px-6 sm:px-8 py-10">
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
            <p className="text-[14px] mt-1" style={{ color: C.muted }}>연결된 환자 {patients.length}명을 관리하세요.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate("/care-education")}
              className="px-5 py-3 rounded-full font-bold text-[14px] border-2"
              style={{ borderColor: C.terracotta, color: C.terracotta }}
            >
              교육 관리
            </button>
            <button
              onClick={() => setModalOpen(true)}
              className="flex items-center gap-2 px-5 py-3 rounded-full text-white font-bold text-[14px]"
              style={{ background: C.terracotta }}
            >
              <Plus className="w-4 h-4" /> 환자 등록
            </button>
          </div>
        </div>

        <div className="relative mb-6">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: C.muted }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="이름 검색"
            className="w-full pl-11 pr-4 py-3 rounded-xl border text-[14px] outline-none bg-white"
            style={{ borderColor: "rgba(30,26,23,0.15)" }}
          />
        </div>

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        <div className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}>
          {loading ? (
            <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
          ) : filtered.length === 0 ? (
            <p className="px-6 py-10 text-center text-[14px]" style={{ color: C.muted }}>
              {patients.length === 0 ? "등록된 환자가 없어요." : "검색 결과가 없어요."}
            </p>
          ) : (
            filtered.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between gap-4 px-6 py-4 border-b last:border-0"
                style={{ borderColor: "rgba(30,26,23,0.06)" }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-11 h-11 rounded-2xl flex items-center justify-center text-white text-[16px] font-black shrink-0"
                    style={{ background: C.terracotta }}
                  >
                    {p.name[0]}
                  </div>
                  <div>
                    <p className="text-[15px] font-bold" style={{ color: C.dark }}>{p.name}</p>
                    <p className="text-[13px]" style={{ color: C.muted }}>{p.note || "특이사항 없음"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => {
                      // [7/14] 다른 화면(Dashboard/Schedule/Notification/Connect/Check)은
                      // ?patient_id= 쿼리를 안 읽고 localStorage만 보므로, 여기서 고른
                      // 환자가 그 화면들에도 이어지도록 같이 저장해둔다.
                      localStorage.setItem("patient_id", String(p.id));
                      navigate(`/records?patient_id=${p.id}`);
                    }}
                    className="px-4 py-2 rounded-full text-[13px] font-bold"
                    style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                  >
                    복약 현황
                  </button>
                  <button
                    onClick={() => remove(p.id)}
                    className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-black/5"
                    style={{ color: C.muted }}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </main>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: "rgba(30,26,23,0.5)" }}
          onClick={() => setModalOpen(false)}
        >
          <div className="bg-white rounded-2xl p-7 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-[19px] font-black mb-5" style={{ color: C.dark }}>환자 등록</h3>

            <label className="block text-[12px] font-bold uppercase tracking-wide mb-2" style={{ color: C.muted }}>이름</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: 김건강"
              className="w-full px-4 py-3 rounded-xl border border-black/12 text-[14px] outline-none mb-4"
            />

            <label className="block text-[12px] font-bold uppercase tracking-wide mb-2" style={{ color: C.muted }}>특이사항 (선택)</label>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="예: 혼자 거주, 거동 불편"
              className="w-full px-4 py-3 rounded-xl border border-black/12 text-[14px] outline-none mb-6"
            />

            <div className="flex gap-3">
              <button
                onClick={() => setModalOpen(false)}
                className="flex-1 py-3 rounded-full font-bold text-[14px] border-2 border-black/12"
                style={{ color: C.dark }}
              >
                취소
              </button>
              <button
                onClick={save}
                disabled={saving || !name.trim()}
                className="flex-1 py-3 rounded-full font-bold text-[14px] text-white disabled:opacity-50"
                style={{ background: C.terracotta }}
              >
                {saving ? "저장 중..." : "등록"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
