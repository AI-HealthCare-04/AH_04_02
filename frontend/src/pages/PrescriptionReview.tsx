import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, Check } from "lucide-react";
import NavBar from "../components/NavBar";
import { confirmMedications, getRecord, type OcrMedication, type RecordResult } from "../api/records";
import { C } from "../theme";

const FIELDS: { key: keyof OcrMedication; label: string }[] = [
  { key: "drug_name", label: "약품명" },
  { key: "dosage", label: "용량" },
  { key: "frequency", label: "복용횟수" },
  { key: "diagnosis", label: "진단명" },
  { key: "drug_class", label: "약효분류" },
];

export default function PrescriptionReview() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [record, setRecord] = useState<RecordResult | null>(null);
  const [edited, setEdited] = useState<Record<number, OcrMedication>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then((data) => {
        setRecord(data);
        const initial: Record<number, OcrMedication> = {};
        data.medications.forEach((m) => (initial[m.id] = { ...m }));
        setEdited(initial);
      })
      .catch(() => setError("처방전 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  const update = (id: number, field: keyof OcrMedication, value: string) => {
    setEdited((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  };

  const reviewItems = record?.medications.filter((m) => m.review_required) ?? [];
  const allFilled = reviewItems.every((m) =>
    FIELDS.every((f) => String(edited[m.id]?.[f.key] ?? "").trim().length > 0)
  );

  const submit = async () => {
    if (!record || !allFilled) return;
    setSubmitting(true);
    setError("");
    try {
      const corrections = reviewItems.map((m) => {
        const e = edited[m.id];
        return {
          id: m.id,
          drug_name: e.drug_name.trim(),
          dosage: e.dosage.trim(),
          frequency: e.frequency.trim(),
          diagnosis: e.diagnosis.trim(),
          drug_class: e.drug_class.trim(),
        };
      });
      const updated = await confirmMedications(record.record_id, corrections);
      navigate(`/records/${updated.record_id}`);
    } catch {
      setError("확정 처리에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>불러오는 중이에요...</p>
        ) : !record ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
        ) : record.status !== "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.white }}>
            <p className="text-[14px]" style={{ color: C.muted }}>이미 확인이 끝난 처방전이에요.</p>
            <button
              onClick={() => navigate(`/records/${record.record_id}`)}
              className="mt-4 px-6 py-3 rounded-full font-bold text-[14px] text-white"
              style={{ background: C.terracotta }}
            >
              결과 보러 가기
            </button>
          </div>
        ) : (
          <>
            <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>처방전 인식 완료</p>
            <h1 className="text-[26px] font-black mb-2" style={{ color: C.dark }}>처방전 확인 및 수정</h1>
            <p className="text-[14px] mb-7" style={{ color: C.muted }}>
              인식 정확도가 낮은 항목이에요. 처방전을 보고 직접 확인·수정해 주세요.
            </p>

            <div className="space-y-5 mb-7">
              {reviewItems.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl p-6"
                  style={{ background: C.white, border: `2px solid ${C.terracotta}40`, boxShadow: "0 2px 16px rgba(30,26,23,0.07)" }}
                >
                  <div className="flex items-center gap-2 mb-4">
                    <AlertCircle className="w-4 h-4" style={{ color: C.terracotta }} />
                    <span className="text-[12px] font-black" style={{ color: C.terracotta }}>
                      확인 필요 (인식 정확도 {Math.round(item.confidence * 100)}%)
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {FIELDS.map(({ key, label }) => (
                      <div key={key} className={key === "drug_name" ? "col-span-2" : ""}>
                        <label className="block text-[11px] font-bold uppercase tracking-wider mb-1.5" style={{ color: C.muted }}>
                          {label}
                        </label>
                        <input
                          value={String(edited[item.id]?.[key] ?? "")}
                          onChange={(e) => update(item.id, key, e.target.value)}
                          className="w-full px-4 py-2.5 rounded-xl border text-[14px] outline-none"
                          style={{ borderColor: `${C.terracotta}45`, color: C.dark }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {record.medications.filter((m) => !m.review_required).length > 0 && (
                <div className="rounded-2xl p-5" style={{ background: "#F5F2ED" }}>
                  <p className="text-[12px] font-bold mb-3" style={{ color: C.muted }}>자동 인식됨 (수정 불필요)</p>
                  {record.medications
                    .filter((m) => !m.review_required)
                    .map((m) => (
                      <div key={m.id} className="flex items-center gap-2 py-1.5">
                        <Check className="w-3.5 h-3.5" style={{ color: C.success }} />
                        <span className="text-[13px]" style={{ color: C.dark }}>{m.drug_name} · {m.dosage}</span>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

            <button
              disabled={!allFilled || submitting}
              onClick={submit}
              className="w-full py-4 rounded-full text-white font-black text-[16px] disabled:opacity-50"
              style={{ background: C.terracotta }}
            >
              {submitting ? "처리 중..." : "확인 완료 · 복약 가이드 만들기"}
            </button>
            <p className="text-center text-[12px] mt-4" style={{ color: C.muted }}>
              본 정보는 의료진의 진단·처방을 대체하지 않습니다
            </p>
          </>
        )}
      </main>
    </div>
  );
}
