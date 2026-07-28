import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import NavBar from "../components/NavBar";
import { formatUniqueSourceRefs, type LifestyleCategory, type RecordResult } from "../api/records";
import { C } from "../theme";
import { getCurrentUserName, isLoggedIn } from "../lib/session";

const STATIC_DISCLAIMER =
  "이 정보는 AI가 생성한 참고용 안내입니다. 정확한 복약 지도는 담당 의사 또는 약사에게 확인하세요.";

const cardCls = "rounded-[14px] p-5";
const cardStyle = { background: C.white, border: "1px solid rgba(30,26,23,0.12)" };
const cardTitleCls = "text-[15px] font-bold mb-4 flex items-center gap-1.5";
const guideItemCls = "py-2.5 border-t";
const guideLabelCls = "text-[13px] font-semibold mb-1";
const guideTextCls = "text-[13px] leading-relaxed";
const chatBtnCls = "w-full p-4 text-[15px] font-semibold rounded-xl cursor-pointer";

const pageStyle = { background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" };

/** [2026-07-23 추가] 생활습관 카테고리(식사/운동/그 외)의 권장·비권장을 요약 한 줄씩으로 압축 —
 * 이 화면은 업로드 직후 요약 카드라 MedGuide.tsx처럼 목록 전체를 펼치지 않는다. */
function lifestyleCategorySummary(label: string, category: LifestyleCategory): string {
  const parts: string[] = [];
  if (category.recommended.length > 0) parts.push(`${label} 권장: ${category.recommended.join(", ")}`);
  if (category.avoid.length > 0) parts.push(`${label} 비권장: ${category.avoid.join(", ")}`);
  return parts.join(" · ");
}

export default function Result() {
  const navigate = useNavigate();
  const location = useLocation();
  const result = (location.state as { result?: RecordResult } | null)?.result;

  useEffect(() => {
    // Processing.tsx를 거치지 않고 직접 들어온 경우 (새로고침 등) — 다시 시작
    if (!result) navigate("/upload", { replace: true });
  }, [result, navigate]);

  if (!result) {
    return null;
  }

  if (result.status === "review_required") {
    return (
      <div className="min-h-screen" style={pageStyle}>
        <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
        <main className="max-w-[1100px] mx-auto text-center px-4 py-20 sm:px-6 sm:py-[120px]">
          <p className="text-[15px] mb-5" style={{ color: C.warningText }}>
            일부 항목의 인식 정확도가 낮아 확인이 필요해요.
          </p>
          <button className={chatBtnCls} style={{ background: C.terracotta, color: C.white }} onClick={() => navigate(`/records/${result.record_id}/review`)}>
            처방전 확인하러 가기
          </button>
        </main>
      </div>
    );
  }

  if (result.status === "failed" || !result.guide) {
    return (
      <div className="min-h-screen" style={pageStyle}>
        <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />
        <main className="max-w-[1100px] mx-auto text-center px-4 py-20 sm:px-6 sm:py-[120px]">
          <p className="text-[15px] mb-5" style={{ color: C.danger }}>
            {result.failure_reason || "결과를 생성하지 못했어요."}
          </p>
          <button className={chatBtnCls} style={{ background: C.terracotta, color: C.white }} onClick={() => navigate("/upload")}>
            다시 업로드하기
          </button>
        </main>
      </div>
    );
  }

  const { guide, medications } = result;

  return (
    <div className="min-h-screen" style={pageStyle}>
      <NavBar isLoggedIn={isLoggedIn()} userName={getCurrentUserName()} />

      <main className="max-w-[1100px] mx-auto px-4 pt-6 pb-16 sm:px-6 sm:pt-10 sm:pb-20">
        {/* 헤더 */}
        <div className="mb-5">
          <div className="flex items-center gap-3 mb-1.5">
            <h1 className="text-xl sm:text-2xl font-bold" style={{ color: C.dark }}>복약 안내 결과</h1>
            <span className="text-[13px] font-semibold px-3 py-1 rounded-full" style={{ background: `${C.success}25`, color: C.successText }}>✓ 분석 완료</span>
          </div>
        </div>

        {/* 면책 고지 */}
        <div className="rounded-[10px] px-4 py-3 mb-6" style={{ background: `${C.terracotta}10`, border: `1px solid ${C.terracotta}25` }}>
          <p className="text-[13px] leading-relaxed" style={{ color: C.terracotta }}>⚠️ {STATIC_DISCLAIMER}</p>
        </div>

        {/* 2단 레이아웃 (모바일: 세로 스택) */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-5 mb-6">
          {/* 좌측: OCR 결과 */}
          <div className="flex flex-col gap-4">
            <div className={cardCls} style={cardStyle}>
              <h2 className={cardTitleCls} style={{ color: C.dark }}>📄 OCR 인식 결과</h2>
              {medications.map((med, i) => (
                <div key={i} className="flex justify-between items-start py-2.5 border-t" style={{ borderColor: C.bubbleBg }}>
                  <div>
                    <p className="text-sm font-semibold mb-[3px]" style={{ color: C.dark }}>{med.drug_name}</p>
                    <p className="text-xs" style={{ color: C.muted }}>{med.dosage} · {med.frequency}</p>
                    {med.review_required && (
                      <p className="text-[11px] mt-0.5" style={{ color: C.warningText }}>
                        확인 필요 (인식 정확도 {Math.round(med.confidence * 100)}%)
                      </p>
                    )}
                  </div>
                  <span className="text-[11px] px-2 py-[3px] rounded-full whitespace-nowrap" style={{ background: C.bubbleBg, color: C.terracotta }}>{med.drug_class}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 우측: 진단 기반 안내 + 가이드 */}
          <div className="flex flex-col gap-4">
            <div className={cardCls} style={{ background: `${C.terracotta}10`, border: `1px solid ${C.terracotta}25` }}>
              <h2 className={cardTitleCls} style={{ color: C.dark }}>🔍 진단 기반 안내</h2>
              <p className="text-base font-bold mb-1.5" style={{ color: C.terracotta }}>{guide.lifestyle_guide.diagnosis}</p>
              <p className="text-xs" style={{ color: C.muted }}>진단명 + 처방 약물 기반 분석 결과입니다.</p>
            </div>

            <div className={cardCls} style={cardStyle}>
              <h2 className={cardTitleCls} style={{ color: C.dark }}>💊 맞춤 복약 지도</h2>
              {guide.medication_guide.drugs.map((drug, i) => {
                // [7/9] dosage_text(stub) / medication_guide(실제) 중 있는 걸 씀
                const guideText = drug.medication_guide ?? drug.dosage_text ?? "";
                // caution(stub, 단일 문자열) / precautions(실제, 배열) 중 있는 걸 씀
                const cautionText = drug.precautions?.length ? drug.precautions.join(" ") : drug.caution;
                return (
                  <div key={i} className={guideItemCls} style={{ borderColor: C.bubbleBg }}>
                    <p className={guideLabelCls} style={{ color: C.dark }}>💊 {drug.drug_name}</p>
                    <p className={guideTextCls} style={{ color: C.dark }}>{guideText}</p>
                    {cautionText && (
                      <p className={`${guideTextCls} mt-1`} style={{ color: C.terracotta }}>
                        ⚠️ {cautionText}
                      </p>
                    )}
                    {drug.review_required && (
                      <p className="text-[11px] mt-1" style={{ color: C.warningText }}>
                        AI 검토 필요 — 참고자료 인용이 부족하거나 OCR 인식 신뢰도가 낮아요.
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className={cardCls} style={cardStyle}>
              <h2 className={cardTitleCls} style={{ color: C.dark }}>🌿 생활습관 개선 가이드</h2>
              {guide.lifestyle_guide.guides.length > 0 ? (
                guide.lifestyle_guide.guides.map((entry, i) => {
                  const summary = [
                    lifestyleCategorySummary("식사", entry.diet),
                    lifestyleCategorySummary("운동", entry.exercise),
                    lifestyleCategorySummary("그 외", entry.other),
                  ]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <div key={i} className={guideItemCls} style={{ borderColor: C.bubbleBg }}>
                      <p className={guideLabelCls} style={{ color: C.dark }}>🌿 {entry.diagnosis || "생활습관 안내"}</p>
                      <p className={guideTextCls} style={{ color: C.dark }}>{summary || "안내할 내용이 없어요."}</p>
                    </div>
                  );
                })
              ) : (
                <p className={guideTextCls} style={{ color: C.muted }}>생활습관 안내가 아직 없어요.</p>
              )}
              {guide.source_refs.length > 0 && (
                <div className="mt-3 pt-2.5 border-t" style={{ borderColor: C.bubbleBg }}>
                  <p className="text-xs" style={{ color: C.muted }}>
                    출처: {formatUniqueSourceRefs(guide.source_refs).map((s) => s.text).join(", ")}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 복약·생활 가이드(탭 화면) 이동 버튼 */}
        <button className="w-full p-4 text-[15px] font-bold rounded-xl cursor-pointer mb-3" style={{ background: C.dark, color: C.white }} onClick={() => navigate(`/records/${result.record_id}/guide`)}>
          📋 가이드 생성하기
        </button>

        {/* 챗봇 이동 버튼 */}
        <button className={chatBtnCls} style={{ background: C.terracotta, color: C.white }} onClick={() => navigate("/chat", { state: { diagnosis: guide.lifestyle_guide.diagnosis } })}>
          💬 더 궁금한 점이 있으신가요? 챗봇에게 물어보기
        </button>
      </main>
    </div>
  );
}
