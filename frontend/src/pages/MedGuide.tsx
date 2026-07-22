import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import NavBar from "../components/NavBar";
import { formatUniqueSourceRefs, getRecord, type RecordResult } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName } from "../lib/session";

// ponytail: Figma 원본은 병명 백과사전·시간대별 복약 일정 탭도 있었지만, 백엔드가
// 그런 데이터(질병 설명 DB, 복용 시간 슬롯)를 안 주기 때문에 실제로 있는 필드
// (medication_guide/lifestyle_guide/source_refs)로만 탭을 구성했습니다.
const TABS = ["복약 지도", "주의사항", "생활습관"] as const;

export default function MedGuide() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [result, setResult] = useState<RecordResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<(typeof TABS)[number]>("복약 지도");

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(setResult)
      .catch(() => setError("복약 가이드를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
      </div>
    );
  }

  if (error || !result?.guide) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <div className="rounded-2xl p-10 m-8 text-center" style={{ background: C.surface }}>
          <p className="text-[14px]" style={{ color: "#D94F4F" }}>{error || "가이드를 찾을 수 없어요."}</p>
        </div>
      </div>
    );
  }

  const { guide } = result;

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate(`/records/${result.record_id}`)}
          className="flex items-center gap-1 text-[13px] font-bold mb-5 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          <ChevronLeft className="w-3.5 h-3.5" /> 처방 상세로
        </button>

        <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>{guide.lifestyle_guide.diagnosis}</p>
        <h1 className="text-[24px] font-black mb-6" style={{ color: C.dark }}>복약 가이드</h1>

        <div className="flex gap-2 mb-6 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-5 py-2.5 rounded-full text-[14px] font-bold transition-all"
              style={{
                background: tab === t ? C.terracotta : C.white,
                color: tab === t ? C.white : C.muted,
                boxShadow: tab === t ? "none" : "0 2px 8px rgba(30,26,23,0.06)",
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "복약 지도" && (
          <div className="space-y-3">
            {guide.medication_guide.drugs.map((d, i) => {
              const med = result.medications.find((m) => m.drug_name === d.drug_name);
              // [7/9] dosage_text(stub) / medication_guide(실제) 중 있는 걸 씀
              const guideText = d.medication_guide ?? d.dosage_text ?? "";
              const content = (
                <>
                  <div className="flex items-center justify-between gap-3 mb-1.5">
                    <p className="text-[15px] font-black" style={{ color: C.dark }}>💊 {d.drug_name}</p>
                    <div className="flex items-center gap-2 shrink-0">
                      {med?.drug_class && (
                        <span
                          className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                          style={{ background: `${C.terracotta}12`, color: C.terracotta }}
                        >
                          {med.drug_class}
                        </span>
                      )}
                      {med && <ChevronRight className="w-4 h-4" style={{ color: C.muted }} />}
                    </div>
                  </div>
                  {med?.frequency && (
                    <p className="text-[12px] mb-2" style={{ color: C.muted }}>{med.frequency}</p>
                  )}
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{guideText}</p>
                </>
              );
              return med ? (
                <button
                  key={i}
                  onClick={() => navigate(`/records/${result.record_id}/drugs/${med.id}`)}
                  className="w-full text-left rounded-2xl p-5 transition-all hover:shadow-md"
                  style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}
                >
                  {content}
                </button>
              ) : (
                <div key={i} className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  {content}
                </div>
              );
            })}
          </div>
        )}

        {/* 약물 주의사항(caution)과 생활습관상 주의사항(피해야 할 음식)은 둘 다 "조심해야 할 것"이라
            겹치는 성격이라, 한 탭에 같이 모아서 보여줍니다. */}
        {tab === "주의사항" && (() => {
          // [7/9] caution(stub, 단일 문자열) / precautions(실제, 배열) 중 있는 걸 씀
          const drugsWithCaution = guide.medication_guide.drugs
            .map((d) => ({ d, cautionText: d.precautions?.length ? d.precautions.join(" ") : d.caution }))
            .filter((x) => x.cautionText);
          const dietAvoid = guide.lifestyle_guide.diet?.avoid ?? [];
          const dietSpecific = guide.lifestyle_guide.diet?.drug_specific ?? [];
          const hasDietWarning = dietAvoid.length > 0 || dietSpecific.length > 0;
          return (
            <div className="space-y-4">
              {drugsWithCaution.length > 0 && (
                <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>💊 약물별 주의사항</p>
                  <ul className="space-y-2.5">
                    {drugsWithCaution.map(({ d, cautionText }, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: C.terracotta }} />
                        <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>
                          <span className="font-bold">{d.drug_name}</span> — {cautionText}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {hasDietWarning && (
                <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>🥗 생활 속 주의사항</p>
                  <ul className="space-y-2.5">
                    {dietAvoid.map((food, i) => (
                      <li key={`avoid-${i}`} className="flex items-start gap-2.5">
                        <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: C.terracottaLight }} />
                        <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{food} 섭취를 피하세요</p>
                      </li>
                    ))}
                    {dietSpecific.map((note, i) => (
                      <li key={`specific-${i}`} className="flex items-start gap-2.5">
                        <div className="w-1.5 h-1.5 rounded-full mt-2 shrink-0" style={{ background: C.terracottaLight }} />
                        <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{note}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {drugsWithCaution.length === 0 && !hasDietWarning && (
                <p className="text-[14px]" style={{ color: C.muted }}>특별히 주의할 사항이 없어요.</p>
              )}
            </div>
          );
        })()}

        {tab === "생활습관" && (
          <div className="space-y-4">
            {guide.lifestyle_guide.guides?.length ? (
              // [2026-07-21 회의 반영] 실제 파이프라인 모양 — 진단명별 생활습관 안내(약별이 아님)
              guide.lifestyle_guide.guides.map((entry, i) => (
                <div key={i} className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>🌿 {entry.diagnosis || "생활습관 안내"}</p>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{entry.guide}</p>
                </div>
              ))
            ) : (
              // stub 모양 — 구조화된 diet/exercise
              <>
                <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>🥗 식이</p>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>
                    피해야 할 음식: {guide.lifestyle_guide.diet?.avoid.join(", ") || "없음"}
                  </p>
                  {!!guide.lifestyle_guide.diet?.drug_specific.length && (
                    <p className="text-[13px] mt-2" style={{ color: C.muted }}>
                      {guide.lifestyle_guide.diet.drug_specific.join(" ")}
                    </p>
                  )}
                </div>
                <div className="rounded-2xl p-5" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.07)" }}>
                  <p className="text-[15px] font-black mb-3" style={{ color: C.dark }}>🏃 운동</p>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>
                    {guide.lifestyle_guide.exercise?.type} · {guide.lifestyle_guide.exercise?.duration} ·{" "}
                    {guide.lifestyle_guide.exercise?.intensity}
                  </p>
                </div>
              </>
            )}
          </div>
        )}

        {guide.source_refs.length > 0 && (() => {
          const uniqueRefs = formatUniqueSourceRefs(guide.source_refs);
          return (
            <p className="text-[12px] mt-6" style={{ color: C.muted }}>
              출처:{" "}
              {uniqueRefs.map((s, i) => (
                <span key={i}>
                  {/* [7/9] url(stub)이 있을 때만 링크로, 실제 파이프라인 인용(url 없음)은 텍스트로만 표시 */}
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline" style={{ color: C.muted }}>
                      {s.text}
                    </a>
                  ) : (
                    s.text
                  )}
                  {i < uniqueRefs.length - 1 && ", "}
                </span>
              ))}
            </p>
          );
        })()}

        <button
          onClick={() => navigate("/chat", { state: { diagnosis: guide.lifestyle_guide.diagnosis } })}
          className="w-full mt-8 py-4 rounded-xl font-bold text-[15px] text-white"
          style={{ background: C.terracotta }}
        >
          💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}
