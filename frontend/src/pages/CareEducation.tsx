import { Fragment, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import NavBar from "../components/NavBar";
import { C } from "../theme";

type StageType = "집중교육" | "전화지원" | "자립단계";
type SupportType = "앱 내" | "전화" | "방문";
type Trainee = { id: number; name: string; stage: StageType; nextCall: string };

// ponytail: 백엔드에 교육/지원기록 테이블이 아직 없어서 목록·저장 모두 화면 안 로컬 상태로만
// 처리합니다. 새로고침하면 "기록 완료" 표시가 사라져요 — 실제 운영에 쓰려면 백엔드에
// education_stage/support_log 모델과 엔드포인트를 먼저 설계해야 합니다.
const TRAINEES: Trainee[] = [
  { id: 1, name: "김건강", stage: "집중교육", nextCall: "2025.07.05" },
  { id: 2, name: "이복자", stage: "전화지원", nextCall: "2025.07.08" },
  { id: 3, name: "박순자", stage: "자립단계", nextCall: "2025.07.15" },
  { id: 4, name: "최길동", stage: "전화지원", nextCall: "2025.07.09" },
];

const stageStyle = (s: StageType) =>
  s === "집중교육"
    ? { bg: `${C.terracotta}18`, color: C.terracotta }
    : s === "전화지원"
    ? { bg: `${C.terracottaLight}18`, color: C.terracottaLight }
    : { bg: `${C.success}18`, color: C.success };

export default function CareEducation() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [sType, setSType] = useState<SupportType>("전화");
  const [memo, setMemo] = useState("");
  const [saved, setSaved] = useState<Set<number>>(new Set());

  const renderSupportForm = (t: Trainee) => (
    <>
      <p className="text-[14px] font-black mb-4" style={{ color: C.dark }}>{t.name} 지원 기록</p>
      <div className="flex gap-2 mb-4">
        {(["앱 내", "전화", "방문"] as SupportType[]).map((type) => (
          <button
            key={type}
            onClick={() => setSType(type)}
            className="px-5 py-2 rounded-full text-[13px] font-bold transition-all"
            style={{ background: sType === type ? C.terracotta : "#F0EDE8", color: sType === type ? C.white : C.muted }}
          >
            {type}
          </button>
        ))}
      </div>
      <textarea
        value={memo}
        onChange={(e) => setMemo(e.target.value)}
        placeholder="지원 내용을 입력하세요..."
        rows={3}
        className="w-full px-4 py-3 rounded-xl border text-[14px] outline-none resize-none mb-4"
        style={{ borderColor: "rgba(30,26,23,0.15)", background: C.white }}
      />
      <div className="flex justify-end gap-3">
        <button
          onClick={() => setSelectedId(null)}
          className="px-5 py-2.5 rounded-full border font-bold text-[14px]"
          style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
        >
          취소
        </button>
        <button
          onClick={() => {
            setSaved((p) => new Set([...p, t.id]));
            setSelectedId(null);
            setMemo("");
          }}
          className="px-5 py-2.5 rounded-full font-bold text-white text-[14px]"
          style={{ background: C.terracotta }}
        >
          저장
        </button>
      </div>
    </>
  );

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김보호" />
      <main className="max-w-4xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate("/patients")}
          className="flex items-center gap-1 text-[13px] font-bold mb-4 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 환자 관리
        </button>

        <h1 className="text-[26px] font-black mb-2" style={{ color: C.dark }}>대상자 교육 관리</h1>
        <p className="text-[15px] mb-8" style={{ color: C.muted }}>
          배정된 대상자의 교육 진행 상황을 관리하고 지원 기록을 남겨주세요.
        </p>

        <div className="rounded-2xl overflow-hidden" style={{ background: C.surface, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
          {/* 모바일: 표 4컬럼(이름/단계/예정일/버튼)이 좁은 화면에서 한 글자씩 줄바꿈되는 걸 피하려고 카드형으로 */}
          <div className="sm:hidden">
            {TRAINEES.map((t) => {
              const ss = stageStyle(t.stage);
              const isOpen = selectedId === t.id;
              return (
                <div key={t.id} style={{ borderBottom: "1px solid rgba(30,26,23,0.07)" }}>
                  <div
                    className="px-5 py-4 cursor-pointer hover:bg-black/[0.02] transition-colors"
                    style={{ background: isOpen ? `${C.terracotta}04` : undefined }}
                    onClick={() => setSelectedId(isOpen ? null : t.id)}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="font-bold text-[15px]" style={{ color: C.dark }}>
                        {t.name}
                        {saved.has(t.id) && (
                          <span
                            className="ml-2 text-[11px] font-bold px-2 py-0.5 rounded-full"
                            style={{ background: `${C.success}20`, color: C.success }}
                          >
                            기록 완료
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 px-3 py-1.5 rounded-full text-[12px] font-black" style={{ background: ss.bg, color: ss.color }}>
                        {t.stage}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px]" style={{ color: C.muted }}>다음 전화지원 {t.nextCall}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedId(isOpen ? null : t.id);
                        }}
                        className="shrink-0 px-4 py-2 rounded-full text-[13px] font-bold border"
                        style={{ borderColor: `${C.terracotta}35`, color: C.terracotta }}
                      >
                        지원 기록 남기기
                      </button>
                    </div>
                  </div>
                  {isOpen && (
                    <div className="px-5 py-5" style={{ background: `${C.terracotta}05` }}>
                      {renderSupportForm(t)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <table className="w-full hidden sm:table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(30,26,23,0.07)" }}>
                {["이름", "교육 단계", "다음 전화지원 예정일", ""].map((h) => (
                  <th
                    key={h}
                    className="px-6 py-3 text-left text-[11px] font-bold uppercase tracking-wider"
                    style={{ color: C.muted }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TRAINEES.map((t) => {
                const ss = stageStyle(t.stage);
                const isOpen = selectedId === t.id;
                return (
                  <Fragment key={t.id}>
                    <tr
                      className="cursor-pointer hover:bg-black/[0.02] transition-colors"
                      style={{
                        borderBottom: "1px solid rgba(30,26,23,0.07)",
                        background: isOpen ? `${C.terracotta}04` : undefined,
                      }}
                      onClick={() => setSelectedId(isOpen ? null : t.id)}
                    >
                      <td className="px-6 py-4 font-bold text-[15px]" style={{ color: C.dark }}>
                        {t.name}
                        {saved.has(t.id) && (
                          <span
                            className="ml-2 text-[11px] font-bold px-2 py-0.5 rounded-full"
                            style={{ background: `${C.success}20`, color: C.success }}
                          >
                            기록 완료
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="px-3 py-1.5 rounded-full text-[12px] font-black" style={{ background: ss.bg, color: ss.color }}>
                          {t.stage}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-[14px]" style={{ color: C.muted }}>{t.nextCall}</td>
                      <td className="px-6 py-4">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedId(isOpen ? null : t.id);
                          }}
                          className="px-4 py-2 rounded-full text-[13px] font-bold border"
                          style={{ borderColor: `${C.terracotta}35`, color: C.terracotta }}
                        >
                          지원 기록 남기기
                        </button>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={4} className="px-6 py-5" style={{ background: `${C.terracotta}05`, borderBottom: "1px solid rgba(30,26,23,0.07)" }}>
                          {renderSupportForm(t)}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
