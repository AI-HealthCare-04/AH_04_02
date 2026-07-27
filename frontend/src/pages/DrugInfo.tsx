import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import { getDrugIndication, getRecord, type DrugIndicationInfo, type RecordResult } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName } from "../lib/session";

export default function DrugInfo() {
  const navigate = useNavigate();
  const { recordId, medId } = useParams<{ recordId: string; medId: string }>();

  const [record, setRecord] = useState<RecordResult | null>(null);
  const [drugInfo, setDrugInfo] = useState<DrugIndicationInfo | null>(null);
  const [drugInfoLoading, setDrugInfoLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(setRecord)
      .catch(() => setError("약품 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  const med = record?.medications.find((m) => m.id === Number(medId));
  const guideDrug = record?.guide?.medication_guide.drugs.find((d) => d.drug_name === med?.drug_name);
  // [7/9] dosage_text/caution(stub) 또는 medication_guide/precautions(실제 파이프라인) 중
  // 있는 걸 씀 — MedGuide.tsx/Result.tsx와 동일한 stub/real 호환 처리(PR #16/#17)를 여기도 적용.
  const dosageGuideText = guideDrug?.medication_guide ?? guideDrug?.dosage_text;
  // [2026-07-20] 처방 시점에 생성된 RAG 가이드의 주의사항(이 환자의 실제 처방 맥락 반영) —
  // 없으면 아래에서 e약은요/허가사항 live 조회(drugInfo)의 환자용 요약 또는 원문으로 폴백한다.
  const guideCautionText = guideDrug?.precautions?.length ? guideDrug.precautions.join(" ") : guideDrug?.caution;

  // [2026-07-25 추가] 뱃지("1정"/"5mg"/"1일 1회")의 숫자만 보면 어떤 값이 사용량이고
  // 어떤 값이 투여량인지 헷갈릴 수 있어 — 어르신도 바로 이해할 수 있게 문장으로 풀어 쓴다.
  const doseExplanation = [
    med?.dosage ? `1회 사용량은 ${med.dosage}` : null,
    med?.dose_amount ? `1회 투여량은 ${med.dose_amount}` : null,
    med?.frequency ? `1일 ${med.frequency} 복용해요` : null,
  ]
    .filter(Boolean)
    .join(", ");

  useEffect(() => {
    if (!med) return;
    // [2026-07-21 추가] e약은요/허가정보/DUR live 조회(_fetch_rag_drug_detail)는 후보 이름별로
    // 순차 API 호출이 여러 번 걸려 수 초가 걸릴 수 있다 — drugInfo가 null인 로딩 중과
    // "조회했지만 없음"을 구분 못 해서, 로딩 중에도 "등록된 정보가 없어요"가 먼저 보이던 문제.
    setDrugInfoLoading(true);
    getDrugIndication(med.drug_name)
      .then(setDrugInfo)
      .catch(() => setDrugInfo(null))
      .finally(() => setDrugInfoLoading(false));
  }, [med]);

  const hasPatientSummary = !!(
    drugInfo?.patient_summary &&
    (drugInfo.patient_summary.must_check.length ||
      drugInfo.patient_summary.tell_doctor.length ||
      drugInfo.patient_summary.avoid_together.length)
  );

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate(`/records/${recordId}`)}
          className="flex items-center gap-1.5 text-[13px] font-bold mb-6 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          ← 처방 상세로
        </button>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
        ) : !med ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "약품 정보를 찾을 수 없어요."}</p>
        ) : (
          <>
            <div
              className="rounded-3xl p-7 mb-5"
              style={{ background: "linear-gradient(135deg, #C1653D 0%, #A5522F 100%)", boxShadow: "0 8px 32px rgba(193,101,61,0.30)" }}
            >
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center shrink-0 text-[32px]" style={{ background: "rgba(255,255,255,0.18)" }}>💊</div>
                <div className="flex-1">
                  <p className="text-[13px] font-bold mb-1" style={{ color: "rgba(255,255,255,0.65)" }}>{med.drug_class || "약효분류 확인 중"}</p>
                  <h1 className="text-[26px] font-black leading-tight mb-2" style={{ color: C.white }}>{med.drug_name}</h1>
                  <div className="flex flex-wrap gap-2">
                    <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                      {med.dosage}
                    </span>
                    {med.dose_amount && (
                      <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                        {med.dose_amount}
                      </span>
                    )}
                    {med.frequency && (
                      <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                        {med.frequency}
                      </span>
                    )}
                  </div>
                  {/* [2026-07-25 추가] 어르신도 뱃지의 숫자·단위가 뭘 뜻하는지 바로 알 수 있게
                      풀어 쓴 설명 — 값이 있는 항목만 이어붙인다. */}
                  {doseExplanation && (
                    <p className="text-[13px] mt-2" style={{ color: "rgba(255,255,255,0.75)" }}>{doseExplanation}</p>
                  )}
                </div>
              </div>
            </div>

            <div
              className="flex items-start gap-2.5 px-4 py-3.5 rounded-2xl mb-5"
              style={{ background: C.warningBg, border: `1px solid ${C.warningBorder}` }}
            >
              <span className="text-[14px] shrink-0">ℹ️</span>
              <p className="text-[12px] leading-relaxed" style={{ color: C.warningText }}>
                아래 정보는 일반적인 복약 안내입니다. 개인 상태에 따라 다를 수 있으므로, 정확한 복약 지도는 담당 의사·약사에게 확인하세요.
              </p>
            </div>

            <div className="space-y-4">
              {drugInfo?.indication && (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">🩺</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>적응증</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.indication}</p>
                </div>
              )}

              {dosageGuideText && (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">💊</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>복용 방법</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{dosageGuideText}</p>
                </div>
              )}

              {/* [2026-07-20] 처방 시점 RAG 가이드에 이 환자 맥락을 반영한 주의사항이 있으면
                  그걸 우선 보여준다 — 없으면 아래 e약은요/허가사항 live 조회 결과(환자용
                  요약 우선, 없으면 원문)로 폴백한다. */}
              {guideCautionText ? (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">⚠️</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>주의사항</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{guideCautionText}</p>
                </div>
              ) : !hasPatientSummary ? (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">⚠️</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>주의사항</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed whitespace-pre-line" style={{ color: C.dark }}>
                    {drugInfoLoading ? "조회하는 중이에요..." : (drugInfo?.precautions || "등록된 주의사항이 없어요.")}
                  </p>
                </div>
              ) : null}

              {drugInfoLoading ? (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5">
                    <span className="text-[18px] animate-pulse">⏳</span>
                    <p className="text-[13px]" style={{ color: C.muted }}>부작용·약물 상호작용·보관 방법을 조회하는 중이에요...</p>
                  </div>
                </div>
              ) : hasPatientSummary ? (
                <>
                  {!!drugInfo?.patient_summary?.must_check.length && (
                    <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="flex items-center gap-2.5 mb-3">
                        <span className="text-[18px]">⚠️</span>
                        <h2 className="text-[15px] font-black" style={{ color: C.dark }}>꼭 확인하세요</h2>
                      </div>
                      {drugInfo.patient_summary.must_check.map((line, i) => (
                        <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                      ))}
                    </div>
                  )}

                  {!!drugInfo?.patient_summary?.tell_doctor.length && (
                    <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="flex items-center gap-2.5 mb-3">
                        <span className="text-[18px]">💬</span>
                        <h2 className="text-[15px] font-black" style={{ color: C.dark }}>의사·약사에게 알려주세요</h2>
                      </div>
                      {drugInfo.patient_summary.tell_doctor.map((line, i) => (
                        <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                      ))}
                    </div>
                  )}

                  {!!drugInfo?.patient_summary?.avoid_together.length && (
                    <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="flex items-center gap-2.5 mb-3">
                        <span className="text-[18px]">🚫</span>
                        <h2 className="text-[15px] font-black" style={{ color: C.dark }}>함께 조심하세요</h2>
                      </div>
                      {drugInfo.patient_summary.avoid_together.map((line, i) => (
                        <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>• {line}</p>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <>
                  {drugInfo?.side_effects && (
                    <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="flex items-center gap-2.5 mb-3">
                        <span className="text-[18px]">🤕</span>
                        <h2 className="text-[15px] font-black" style={{ color: C.dark }}>부작용</h2>
                      </div>
                      <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.side_effects}</p>
                    </div>
                  )}

                  {drugInfo?.interactions && (
                    <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="flex items-center gap-2.5 mb-3">
                        <span className="text-[18px]">🔀</span>
                        <h2 className="text-[15px] font-black" style={{ color: C.dark }}>약물 상호작용</h2>
                      </div>
                      <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.interactions}</p>
                    </div>
                  )}
                </>
              )}

              {drugInfo?.storage && (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">🗄️</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>보관 방법</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{drugInfo.storage}</p>
                </div>
              )}

              {!!drugInfo?.dur_cautions?.length && (
                <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">🚸</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>복용 시 유의(DUR)</h2>
                  </div>
                  {drugInfo.dur_cautions.map((c, i) => (
                    <p key={i} className="text-[14px] leading-relaxed mb-2 last:mb-0" style={{ color: C.dark }}>
                      <span className="font-bold">[{c.category}]</span> {c.detail}
                      {c.extra ? ` (${c.extra})` : ""}
                    </p>
                  ))}
                </div>
              )}

              {!drugInfoLoading && !hasPatientSummary && !drugInfo?.side_effects && !drugInfo?.interactions && !drugInfo?.storage && !drugInfo?.dur_cautions?.length && (
                <div className="rounded-2xl p-6" style={{ background: "#F5F2ED" }}>
                  <p className="text-[13px]" style={{ color: C.muted }}>
                    부작용·약물 상호작용·보관 방법 정보를 아직 확인하지 못했어요.
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={() => navigate("/chat", { state: { drugName: med.drug_name } })}
                className="flex-1 py-4 rounded-full font-bold text-[15px] border-2 transition-all hover:bg-black/[0.02]"
                style={{ borderColor: C.terracotta, color: C.terracotta }}
              >
                챗봇에게 질문하기 💬
              </button>
              <button
                onClick={() => navigate(`/records/${recordId}`)}
                className="flex-1 py-4 rounded-full font-bold text-[15px] text-white transition-all hover:opacity-88"
                style={{ background: C.terracotta }}
              >
                처방 상세로
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
