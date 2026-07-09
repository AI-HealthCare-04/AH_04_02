import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import NavBar from "../components/NavBar";
import { getDrugIndication, getRecord, type RecordResult } from "../api/records";
import { C } from "../theme";

export default function DrugInfo() {
  const navigate = useNavigate();
  const { recordId, medId } = useParams<{ recordId: string; medId: string }>();

  const [record, setRecord] = useState<RecordResult | null>(null);
  const [indication, setIndication] = useState<string | null>(null);
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
  // [7/9] dosage_text(stub) / medication_guide(실제), caution(stub) / precautions(실제, 배열) —
  // MedGuide.tsx/Result.tsx와 동일한 분기. 여기서 안 하면 RAG_PROVIDER=real일 때 이미
  // guide에 들어있는 복용법·주의사항을 그대로 두고도 "없음"으로 잘못 표시됨.
  const guideText = guideDrug?.medication_guide ?? guideDrug?.dosage_text;
  const cautionText = guideDrug?.precautions?.length ? guideDrug.precautions.join(" ") : guideDrug?.caution;

  useEffect(() => {
    if (!med) return;
    getDrugIndication(med.drug_name)
      .then((info) => setIndication(info.indication))
      .catch(() => setIndication(null));
  }, [med]);

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <button
          onClick={() => navigate(`/records/${recordId}`)}
          className="flex items-center gap-1.5 text-[13px] font-bold mb-6 hover:opacity-60 transition-opacity"
          style={{ color: C.muted }}
        >
          ← 처방 상세로
        </button>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
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
                    {med.frequency && (
                      <span className="px-3 py-1 rounded-full text-[12px] font-bold" style={{ background: "rgba(255,255,255,0.18)", color: C.white }}>
                        {med.frequency}
                      </span>
                    )}
                  </div>
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
              {indication && (
                <div className="rounded-2xl p-6" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">🩺</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>적응증</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{indication}</p>
                </div>
              )}

              {guideText && (
                <div className="rounded-2xl p-6" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                  <div className="flex items-center gap-2.5 mb-3">
                    <span className="text-[18px]">💊</span>
                    <h2 className="text-[15px] font-black" style={{ color: C.dark }}>복용 방법</h2>
                  </div>
                  <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>{guideText}</p>
                </div>
              )}

              <div className="rounded-2xl p-6" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                <div className="flex items-center gap-2.5 mb-3">
                  <span className="text-[18px]">⚠️</span>
                  <h2 className="text-[15px] font-black" style={{ color: C.dark }}>주의사항</h2>
                </div>
                <p className="text-[14px] leading-relaxed" style={{ color: C.dark }}>
                  {cautionText || "등록된 주의사항이 없어요."}
                </p>
              </div>

              {/* ponytail: 부작용·상호작용·보관법은 e약은요/HIRA 데이터에 아예 없는 필드라
                  채우지 못했습니다 — 가짜 정보를 보여주는 대신 준비 중이라고 안내합니다. */}
              <div className="rounded-2xl p-6" style={{ background: "#F5F2ED" }}>
                <p className="text-[13px]" style={{ color: C.muted }}>
                  부작용·약물 상호작용·보관 방법 정보는 아직 준비 중이에요.
                </p>
              </div>
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
