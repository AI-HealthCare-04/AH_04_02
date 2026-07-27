import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, Check, Plus, X } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import PrescriptionImageViewer from "../components/PrescriptionImageViewer";
import {
  addMedicationItem,
  confirmMedications,
  correctMedicationField,
  getDrugIndication,
  getRecord,
  removeMedicationItem,
  type OcrMedication,
  type RecordResult,
} from "../api/records";
import { C } from "../theme";
import { getCurrentUserName } from "../lib/session";
import { FIELDS } from "../lib/prescriptionFields";
import { DOSE_TIMINGS } from "./Schedule";

// [2026-07-21 추가] 처방확인 화면에서 "1일 N회"를 보고 복용시간을 바로 추정해서 보여줌 —
// 백엔드 _DEFAULT_TIME_SLOTS(records_router.py)와 같은 빈도 표기를 기준으로 삼되, 실제
// 시간대 개수는 여기서 사용자가 고른 값의 "개수"가 그대로 진실 공급원이 된다(백엔드도 동일).
// 인식 못 하는 빈도 표기는 지어내지 않고 빈 배열(사용자가 직접 고르게 둠).
const DOSE_TIMING_GUESS: Record<string, string[]> = {
  "1일 1회": ["아침 식후"],
  "1일 2회": ["아침 식후", "저녁 식후"],
  "1일 3회": ["아침 식후", "점심 식후", "저녁 식후"],
};

// [2026-07-21 추가] "몇 시간마다 반복" — 시작 시각부터 간격만큼 더해가며 하루(24시간)를
// 채울 만큼만 생성한다(자정 넘어가면 다음날로 넘기지 않고 그 시각에서 멈춤 — 다음날 몫은
// 이 처방전의 하루 일정과 무관하므로 배제).
function expandInterval(startTime: string, intervalHours: number): string[] {
  const [h, m] = startTime.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m) || !intervalHours || intervalHours <= 0) return [];
  const startMinutes = h * 60 + m;
  const times: string[] = [];
  for (let minutes = startMinutes; minutes < 24 * 60; minutes += intervalHours * 60) {
    times.push(`${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`);
  }
  return times;
}


// 1회 사용량엔 반드시 숫자+개수단위가 같이 있어야 함 (예: "1정") — "1"처럼 단위 빠진 OCR
// 오류를 잡아냄. [PR #90 리뷰 반영 — pecs0310] parsing_rules.py의
// DOSE_QTY_UNITS(정|캡슐|캅셀|포|병|환)와 맞춰 캅셀(대체 표기)/병/환을 추가 — 이 세 단위가
// 빠져 있어서 해당 단위로 처방된 항목은 isUsageValid()가 계속 실패로 잡고, allOk가
// false가 돼 "확인 완료" 제출 자체가 막혀 있었다.
const USAGE_RE = /(\d+\.?\d*)\s*(정|캡슐|캅셀|포|병|환)/i;
function isUsageValid(dosage: string) {
  return USAGE_RE.test(dosage.trim());
}

// [2026-07-25 추가] 1회 투여량 — mg/ml 등 질량·부피 단위. 1회 사용량(개수 단위)과
// 별개 필드라 단위도 따로 검증한다. "50/1000mg"(복합제) 표기도 허용.
const AMOUNT_RE = /(\d+\/\d+|\d+\.?\d*)\s*(mg|g|ml|mcg|iu|밀리그램|그램)/i;
function isAmountValid(amount: string) {
  return AMOUNT_RE.test(amount.trim());
}

type FieldIssue = { field: keyof OcrMedication; message: string };

// [7/9] 신뢰도(review_required)와 무관하게 항상 확인 화면을 거치므로, "어떤 항목이 문제인지"는
// OCR의 overall_confidence가 아니라 실제 필드 값(약품명 매칭 여부·용량 형식·빈 칸)으로 판단한다.
// 초기 로드 시(비동기 검증 전)와 렌더링 시 양쪽에서 같은 기준을 써야 해서 순수 함수로 분리했다.
function computeIssues(m: OcrMedication, drugNameOk: boolean | undefined, nameOverridden = false): FieldIssue[] {
  const issues: FieldIssue[] = [];
  if (drugNameOk === false && !nameOverridden) {
    issues.push({ field: "drug_name", message: "약품명이 올바르지 않아요. 처방전의 철자를 다시 확인해주세요." });
  } else if (!m.drug_name.trim()) {
    issues.push({ field: "drug_name", message: "약품명이 비어있어요. 입력해주세요." });
  }
  if (m.dosage.trim() && !isUsageValid(m.dosage)) {
    issues.push({ field: "dosage", message: "1회 사용량 형식이 잘못됐어요 (예: 1정, 2캡슐처럼 단위를 함께 입력)." });
  } else if (!m.dosage.trim()) {
    issues.push({ field: "dosage", message: "1회 사용량이 비어있어요. 입력해주세요." });
  }
  // [2026-07-25 추가] 1회 투여량(mg/ml)은 선택 항목 — 값이 있을 때만 형식을 검사한다.
  if (m.dose_amount.trim() && !isAmountValid(m.dose_amount)) {
    issues.push({ field: "dose_amount", message: "1회 투여량 형식이 잘못됐어요 (예: 5mg, 10ml처럼 단위를 함께 입력)." });
  }
  // [2026-07-18] 약효분류는 OCR로 못 잡는 경우가 많아 필수에서 제외 — 비어있어도 확인 완료로
  // 넘어갈 수 있다. 총 투약일수도 같은 이유로 필수가 아니다.
  // [2026-07-19] 진단명도 같은 이유로 필수에서 제외 — OCR이 진단명을 못 뽑는 처방전이 많다.
  (["frequency"] as const).forEach((f) => {
    if (!m[f].trim()) {
      issues.push({ field: f, message: `${FIELDS.find((x) => x.key === f)?.label}이 비어있어요. 입력해주세요.` });
    }
  });
  return issues;
}

// 실제 백엔드 응답에는 어떤 단계가 지났는지 알려주는 값이 없어서(동기 호출 한 번으로 끝남),
// 사용자에게 진행 중임을 보여주기 위한 연출용 진행률입니다. 실제 완료 시 바로 100%로 점프합니다.
const FAKE_PROGRESS_STEPS = [22, 48, 72, 90];
const LOADING_STAGES = [
  { label: "처방전 내용 확인", threshold: 25 },
  { label: "약물 정보 검색 중", threshold: 55 },
  { label: "맞춤 가이드 생성 중", threshold: 85 },
  { label: "최종 검토 완료", threshold: 100 },
];

export default function PrescriptionReview() {
  const navigate = useNavigate();
  const { recordId } = useParams<{ recordId: string }>();
  const [record, setRecord] = useState<RecordResult | null>(null);
  const [edited, setEdited] = useState<Record<number, OcrMedication>>({});
  // [2026-07-21 추가] 항목별 복용시간(공복/아침 식후 등) 다중 선택 — 순서가 곧 하루 중 순서.
  // 같은 항목을 여러 번 고를 수 있어서(중복 허용) Set이 아니라 배열 그대로 유지.
  const [doseTimings, setDoseTimings] = useState<Record<number, string[]>>({});
  const [customTimeDraft, setCustomTimeDraft] = useState<Record<number, string>>({});
  const [intervalDraft, setIntervalDraft] = useState<Record<number, { start: string; hours: string }>>({});
  const [confirmed, setConfirmed] = useState<Set<number>>(new Set());
  // 약품명이 실제 존재하는 약인지(e약은요/HIRA 매칭) — key: 항목 id, undefined면 아직 조회 전
  const [drugNameOk, setDrugNameOk] = useState<Record<number, boolean>>({});
  // [2026-07-20 추가] 참조 DB에 없는 실제 약(복합제 등, "알려진 제한사항" 참고)까지
  // match_drug()가 다 잡아내진 못한다 — 사용자가 직접 확인했다고 재확인한 항목은
  // drugNameOk=false여도 막지 않는다. 이름을 다시 수정하면(handleBlur) 새로 검증하도록 해제.
  const [nameOverride, setNameOverride] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [addingItem, setAddingItem] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const [showFinalModal, setShowFinalModal] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  // [2026-07-25 추가] 보호자·기관이 "수정이 필요해요"로 지목한 칸만 고치는 correction
  // 모드 — key: `${medicationId}:${field}`, 저장 요청 중인 칸.
  const [correctingField, setCorrectingField] = useState<string | null>(null);
  // 항목별 입력칸을 감싸는 컨테이너 — blur 시 포커스가 "같은 항목의 다른 칸"으로
  // 이동하는 중인지 판별해서, 그 경우엔 아직 확인 완료 처리하지 않기 위함
  const itemContainerRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!recordId) return;
    getRecord(Number(recordId))
      .then(async (data) => {
        setRecord(data);
        const initial: Record<number, OcrMedication> = {};
        data.medications.forEach((m) => (initial[m.id] = { ...m }));
        setEdited(initial);

        const initialTimings: Record<number, string[]> = {};
        data.medications.forEach((m) => {
          initialTimings[m.id] = DOSE_TIMING_GUESS[m.frequency.trim()] ?? [];
        });
        setDoseTimings(initialTimings);

        // [7/9] 신뢰도와 무관하게 항상 모든 항목의 약품명을 검증한다 (예전엔 review_required
        // 항목만 검증했음 — 그래서 신뢰도가 높으면 오타가 있어도 그냥 넘어갔었다).
        const nameOkEntries = await Promise.all(
          data.medications.map(async (m) => {
            try {
              const info = await getDrugIndication(m.drug_name);
              return [m.id, info.matched_name !== null] as const;
            } catch {
              return [m.id, true] as const; // 조회 실패(네트워크 등)는 오류로 단정하지 않음
            }
          })
        );
        const nameOkMap: Record<number, boolean> = {};
        nameOkEntries.forEach(([id, ok]) => { nameOkMap[id] = ok; });
        setDrugNameOk(nameOkMap);

        // 문제 없는 항목은 바로 "확인 완료"(초록)로 시작 — 사용자가 다시 볼 필요 없게.
        const doneIds = data.medications
          .filter((m) => computeIssues(m, nameOkMap[m.id]).length === 0)
          .map((m) => m.id);
        setConfirmed(new Set(doneIds));
      })
      .catch(() => setError("처방전 정보를 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [recordId]);

  const update = (id: number, field: keyof OcrMedication, value: string) => {
    setEdited((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value } }));
  };

  // [2026-07-25 추가] correction 모드 — 보호자·기관이 지목한 칸 하나를 저장한다. 성공하면
  // 서버가 그 칸의 플래그를 corrected=true로 바꿔서 내려주니(초록/완료로 바뀜), 응답을
  // 그대로 record/edited에 반영한다.
  const handleCorrectField = async (medicationId: number, field: keyof OcrMedication) => {
    if (!record) return;
    const key = `${medicationId}:${field}`;
    setCorrectingField(key);
    try {
      const updated = await correctMedicationField(record.record_id, medicationId, field);
      setRecord(updated);
      const nextEdited: Record<number, OcrMedication> = {};
      updated.medications.forEach((m) => { nextEdited[m.id] = { ...m }; });
      setEdited(nextEdited);
      setError("");
    } catch {
      setError("수정에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setCorrectingField(null);
    }
  };

  // 필드(약품명/투약량/투약횟수)는 문제없는데 복용시간만 만지작거리다 끝난 경우에도
  // "확인 완료"로 넘어갈 수 있게 — handleBlur 안에서만 확인하던 걸 공용 함수로 뺐다.
  // (복용시간 자체는 필수 항목이 아니라 computeIssues에 영향 없음 — 그래서 여기선
  // edited[id] 값만 다시 검사하면 된다, doseTimings 최신값은 필요 없음)
  const maybeConfirm = (id: number) => {
    const m = edited[id];
    if (m && computeIssues(m, drugNameOk[id], nameOverride[id]).length === 0) {
      setConfirmed((prev) => new Set([...prev, id]));
    }
  };

  // [2026-07-21 변경] 같은 시간대를 여러 번 고를 수 있어야 해서(중복 허용) 토글이 아니라
  // 클릭할 때마다 추가 — 제거는 아래 목록에서 항목별 × 버튼으로.
  // [2026-07-23 수정] 여기서 바로 maybeConfirm을 부르면 "1일 3회"라 시간대를 3개 골라야
  // 하는데 1개만 클릭해도 카드가 곧바로 "확인 완료"로 접혀버렸다 — 시간대 추가 자체는
  // 더 이상 완료 처리를 트리거하지 않고, 아래 "복용시간 확인 완료" 버튼을 눌러야 확정된다.
  const addDoseTiming = (id: number, timing: string) => {
    setDoseTimings((prev) => ({ ...prev, [id]: [...(prev[id] ?? []), timing] }));
  };

  const removeDoseTimingAt = (id: number, index: number) => {
    setDoseTimings((prev) => ({ ...prev, [id]: (prev[id] ?? []).filter((_, i) => i !== index) }));
  };

  const addCustomTime = (id: number) => {
    const time = customTimeDraft[id];
    if (!time) return;
    setDoseTimings((prev) => ({ ...prev, [id]: [...(prev[id] ?? []), time] }));
    setCustomTimeDraft((prev) => ({ ...prev, [id]: "" }));
  };

  const addInterval = (id: number) => {
    const draft = intervalDraft[id];
    const hours = Number(draft?.hours);
    if (!draft?.start || !hours || hours <= 0) return;
    const times = expandInterval(draft.start, hours);
    if (times.length === 0) return;
    setDoseTimings((prev) => ({ ...prev, [id]: [...(prev[id] ?? []), ...times] }));
  };

  const fieldIssues = (item: OcrMedication): FieldIssue[] =>
    computeIssues(edited[item.id] ?? item, drugNameOk[item.id], nameOverride[item.id]);

  // 약품명 자동 검증에 안 걸리는 실제 약(복합제 등)을 사용자가 직접 확인했을 때 쓰는 override.
  const confirmDrugNameAnyway = (id: number) => {
    setNameOverride((prev) => ({ ...prev, [id]: true }));
    const m = edited[id];
    if (m && computeIssues(m, drugNameOk[id], true).length === 0) {
      setConfirmed((prev) => new Set([...prev, id]));
    }
  };

  // 항목의 모든 칸을 채운 채로 "그 항목을 완전히 벗어나면"(blur) 자동으로 "확인 완료" 처리합니다.
  // 약품명은 다시 입력했으면 e약은요/HIRA 재조회로 실제 존재하는 약인지 확인하고,
  // 용량은 단위 포함 형식인지 확인한 뒤에야 완료 처리합니다.
  // [수정] relatedTarget(다음에 포커스를 받을 요소)이 같은 항목 컨테이너 안에 있으면
  // — 즉 사용자가 같은 항목의 다음 칸으로 탭/클릭 이동 중이면 — 아직 다 안 봤으니
  // 확인 완료로 잠그지 않고 계속 입력 가능한 상태로 둔다.
  const handleBlur = async (id: number, field: keyof OcrMedication, relatedTarget: EventTarget | null) => {
    const m = edited[id];
    if (!m) return;

    let nameOk = drugNameOk[id];
    let overridden = nameOverride[id];
    if (field === "drug_name") {
      overridden = false; // 이름을 다시 고쳤으니 예전 override는 무효 — 새 값으로 다시 검증
      setNameOverride((prev) => ({ ...prev, [id]: false }));
      try {
        const info = await getDrugIndication(m.drug_name);
        nameOk = info.matched_name !== null;
        setDrugNameOk((prev) => ({ ...prev, [id]: nameOk as boolean }));
      } catch {
        // 조회 실패(네트워크 등) 시엔 기존 상태를 유지 — 오류로 단정하지 않음
      }
    }

    const container = itemContainerRefs.current[id];
    if (relatedTarget instanceof Node && container?.contains(relatedTarget)) return;

    if (computeIssues(edited[id], nameOk, overridden).length === 0) {
      setConfirmed((prev) => new Set([...prev, id]));
    }
  };

  const startReEdit = (id: number) => {
    setConfirmed((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const addItem = async () => {
    if (!record || addingItem) return;
    setAddingItem(true);
    try {
      const updated = await addMedicationItem(record.record_id);
      setRecord(updated);
      const next: Record<number, OcrMedication> = { ...edited };
      const nextTimings: Record<number, string[]> = { ...doseTimings };
      updated.medications.forEach((m) => {
        if (!(m.id in next)) next[m.id] = { ...m };
        if (!(m.id in nextTimings)) nextTimings[m.id] = DOSE_TIMING_GUESS[m.frequency.trim()] ?? [];
      });
      setEdited(next);
      setDoseTimings(nextTimings);
    } catch {
      setError("약물을 추가하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setAddingItem(false);
    }
  };

  const removeItem = async (id: number) => {
    if (!record || removingId !== null) return;
    setRemovingId(id);
    try {
      const updated = await removeMedicationItem(record.record_id, id);
      setRecord(updated);
      setEdited((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setConfirmed((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch {
      setError("약물을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setRemovingId(null);
    }
  };

  // [7/9] review_required(OCR 전체 신뢰도) 기준으로 나누던 걸 없앴다 — 이제 모든 항목을
  // 똑같이 보여주고, 문제 있는지는 항목별로(computeIssues) 판단한다.
  const allItems = record?.medications ?? [];
  const allOk = allItems.length > 0 && allItems.every((m) => confirmed.has(m.id));

  const startGuideGeneration = async () => {
    if (!record) return;
    setShowFinalModal(false);
    setError("");
    setProgress(0);
    setGenerating(true);

    let done = false;
    (async () => {
      for (const step of FAKE_PROGRESS_STEPS) {
        await new Promise((r) => setTimeout(r, 450));
        if (done) return;
        setProgress((p) => Math.max(p, step));
      }
    })();

    try {
      const corrections = allItems.map((m) => {
        const e = edited[m.id];
        return {
          id: m.id,
          drug_name: e.drug_name.trim(),
          dosage: e.dosage.trim(),
          dose_amount: e.dose_amount.trim(),
          frequency: e.frequency.trim(),
          total_days: e.total_days.trim(),
          diagnosis: e.diagnosis.trim(),
          drug_class: e.drug_class.trim(),
          dose_timings: doseTimings[m.id] ?? [],
        };
      });
      const updated = await confirmMedications(record.record_id, corrections);
      done = true;
      setProgress(100);
      // [2026-07-23 추가] 이미 활성 일정이 있던 약은 건너뛰고 등록됐다 — 다음 화면에
      // "이미 등록된 처방이에요" 배너로 보여주기 위해 넘겨준다(이 정보는 DB에 저장되지
      // 않는 confirm 응답 한정값이라, 재조회로는 알 수 없어 state로만 전달 가능).
      setTimeout(
        () =>
          navigate(`/records/${updated.record_id}`, {
            state: { duplicateDrugNames: updated.duplicate_drug_names },
          }),
        500
      );
    } catch {
      done = true;
      setGenerating(false);
      setError("확정 처리에 실패했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  // ── 가이드 생성 중 로딩 화면 ──────────────────────────────────────────────
  if (generating) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <div className="flex-1 flex flex-col items-center justify-center px-8">
        <div className="relative mb-8 flex items-center justify-center">
          {/* 진행률이 90%에서 API 응답까지(최대 1분) 멈춰있어도 계속 도는 링 —
              멈춘 것처럼 보이지 않게 진행률과 무관하게 항상 회전한다 */}
          <div
            className="absolute animate-spin rounded-full"
            style={{
              width: 144,
              height: 144,
              border: "7px solid transparent",
              borderTopColor: C.terracotta,
              borderRightColor: `${C.terracotta}30`,
            }}
          />
          <div
            style={{
              width: 100,
              height: 100,
              borderRadius: "50%",
              background: C.ivory,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center text-[30px]"
              style={{
                background: `linear-gradient(135deg, ${C.terracotta} 0%, #A5522F 100%)`,
                boxShadow: "0 6px 20px rgba(193,101,61,0.35)",
              }}
            >
              📋
            </div>
          </div>
        </div>
        <h2 className="text-[22px] font-black mb-2 text-center" style={{ color: C.dark }}>
          복약 가이드를 만들고 있어요
        </h2>
        <p className="text-[14px] mb-8 text-center leading-relaxed" style={{ color: C.muted }}>
          처방전 정보를 분석하고
          <br />
          맞춤 복약 가이드를 생성 중이에요
          <br />
          <span style={{ fontWeight: 600 }}>보통 1분 정도 걸려요. 조금만 기다려 주세요</span>
        </p>
        <div className="w-72 mb-6">
          <div className="h-2.5 rounded-full overflow-hidden mb-2" style={{ background: "rgba(30,26,23,0.10)" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${progress}%`,
                background: `linear-gradient(90deg, ${C.terracotta}, ${C.terracottaLight})`,
                transitionDuration: "250ms",
              }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[12px]" style={{ color: C.muted }}>분석중...</span>
            <span className="text-[14px] font-black" style={{ color: C.terracotta }}>{progress}%</span>
          </div>
        </div>
        <div className="space-y-2.5">
          {LOADING_STAGES.map(({ label, threshold }) => {
            const stepDone = progress >= threshold;
            const active = !stepDone && progress >= threshold - 30;
            return (
              <div key={label} className="flex items-center gap-3">
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all"
                  style={{ background: stepDone ? C.success : active ? `${C.terracotta}20` : "rgba(30,26,23,0.08)" }}
                >
                  {stepDone ? (
                    <Check className="w-3.5 h-3.5 text-white" />
                  ) : active ? (
                    <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: C.terracotta }} />
                  ) : null}
                </div>
                <span className="text-[14px]" style={{ color: stepDone ? C.dark : C.muted, fontWeight: stepDone ? 700 : 400 }}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}>
            <LoadingDots label="처방전 정보를 불러오는 중이에요" />
          </p>
        ) : !record ? (
          <p className="text-center py-16 text-[14px]" style={{ color: "#D94F4F" }}>{error || "기록을 찾을 수 없어요."}</p>
        ) : record.status === "completed" && record.medications.some((m) => m.field_flags.length > 0) ? (
          (() => {
            const totalFlags = record.medications.reduce((sum, m) => sum + m.field_flags.length, 0);
            const correctedCount = record.medications.reduce(
              (sum, m) => sum + m.field_flags.filter((f) => f.corrected).length,
              0
            );
            const allDone = correctedCount === totalFlags;
            return (
              <>
                {/* [2026-07-25 추가] 수정하면서 원본 사진을 참고할 수 있게 — 챗봇처럼 열었다 닫았다 */}
                {record.has_image && <PrescriptionImageViewer recordId={record.record_id} floating />}
                <p className="text-[13px] font-bold mb-1" style={{ color: C.terracottaLight }}>처방전 수정</p>
                <h1 className="text-[26px] font-black mb-2" style={{ color: C.dark }}>보호자·기관이 요청한 칸을 확인해 주세요</h1>
                <p className="text-[14px] mb-6" style={{ color: C.muted }}>
                  빨간 테두리 칸만 수정할 수 있어요. 나머지 칸은 이미 확인된 내용이라 잠겨 있어요.
                </p>

                <div
                  className="px-5 py-4 rounded-2xl mb-6"
                  style={{ background: allDone ? `${C.success}12` : C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}
                >
                  <p className="text-[14px] font-bold" style={{ color: allDone ? "#4A7A47" : C.dark }}>
                    {allDone
                      ? "✓ 모두 수정했어요! 보호자·기관에게 알렸어요."
                      : `${correctedCount} / ${totalFlags}칸 수정 완료`}
                  </p>
                </div>

                {error && <p className="text-[14px] text-center py-3" style={{ color: "#D94F4F" }}>{error}</p>}

                <div className="space-y-4 mb-8">
                  {record.medications.map((m) => (
                    <div key={m.id} className="rounded-2xl overflow-hidden" style={{ background: C.white, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}>
                      <div className="px-6 py-4" style={{ background: C.surface }}>
                        <p className="font-black text-[15px]" style={{ color: C.dark }}>💊 {m.drug_name}</p>
                      </div>
                      <div className="p-6 grid grid-cols-2 gap-4">
                        {FIELDS.map(({ key, label }) => {
                          const flag = m.field_flags.find((f) => f.field_name === key);
                          const spanFull = key === "drug_name";
                          if (!flag) {
                            return (
                              <div key={key} className={spanFull ? "col-span-2" : ""}>
                                <label className="block text-[11px] font-bold uppercase tracking-wider mb-1.5" style={{ color: C.muted }}>
                                  {label}
                                </label>
                                <p className="text-[14px] px-4 py-2.5 rounded-xl" style={{ color: C.muted, background: "rgba(30,26,23,0.04)" }}>
                                  {String(m[key]) || "-"}
                                </p>
                              </div>
                            );
                          }
                          if (flag.corrected) {
                            return (
                              <div key={key} className={spanFull ? "col-span-2" : ""}>
                                <label className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider mb-1.5" style={{ color: "#4A7A47" }}>
                                  {label}
                                  <span className="px-1.5 py-0.5 rounded text-[9px] font-black normal-case tracking-normal" style={{ background: C.success, color: C.white }}>
                                    수정완료
                                  </span>
                                </label>
                                <p className="text-[14px] px-4 py-2.5 rounded-xl font-medium" style={{ color: C.dark, background: `${C.success}12` }}>
                                  {String(m[key])}
                                </p>
                              </div>
                            );
                          }
                          const flagKey = `${m.id}:${key}`;
                          const saving = correctingField === flagKey;
                          return (
                            <div key={key} className={spanFull ? "col-span-2" : ""}>
                              <label className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: "#D94F4F" }}>
                                {label}
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-black normal-case tracking-normal" style={{ background: "#D94F4F", color: C.white }}>
                                  수정 필요
                                </span>
                              </label>
                              {/* [2026-07-25 수정] 이유는 선택 입력이라 비어있을 수 있다 — 빈 괄호가 뜨지 않게 */}
                              {flag.reason && (
                                <p className="text-[12px] mb-1.5" style={{ color: "#D94F4F" }}>({flag.reason})</p>
                              )}
                              <div className="flex gap-2">
                                {/* [2026-07-25 추가] 자유 입력 대신 드롭다운 — 보호자·기관이 지정한
                                    정답(suggested_value)만 고를 수 있고, 다른 값은 아예 선택지에 없다. */}
                                <select
                                  value={String(edited[m.id]?.[key] ?? "")}
                                  onChange={(e) => update(m.id, key, e.target.value)}
                                  disabled={saving}
                                  className="flex-1 min-w-0 px-4 py-2.5 rounded-xl border text-[14px] outline-none"
                                  style={{ borderColor: "#D94F4F", background: C.white, color: C.dark }}
                                >
                                  <option value="">선택하세요</option>
                                  <option value={flag.suggested_value}>{flag.suggested_value}</option>
                                </select>
                                <button
                                  onClick={() => handleCorrectField(m.id, key)}
                                  disabled={saving || edited[m.id]?.[key] !== flag.suggested_value}
                                  className="px-4 py-2 rounded-xl text-[13px] font-bold text-white disabled:opacity-50 shrink-0"
                                  style={{ background: C.terracotta }}
                                >
                                  {saving ? "저장 중..." : "저장"}
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  onClick={() => navigate(`/records/${record.record_id}`)}
                  className="w-full py-4 rounded-full text-white font-black text-[16px]"
                  style={{ background: C.terracotta }}
                >
                  처방 상세로 돌아가기
                </button>
              </>
            );
          })()
        ) : record.status !== "review_required" ? (
          <div className="rounded-2xl p-10 text-center" style={{ background: C.surface }}>
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
            {/* [2026-07-27 추가] 처음 확인·수정하는 화면에도 원본 사진을 참고할 수 있게 —
                보호자·기관이 지목한 칸을 고치는 화면(위 correction 모드)과 동일하게. */}
            {record.has_image && <PrescriptionImageViewer recordId={record.record_id} floating />}
            <p className="text-[13px] font-bold mb-1" style={{ color: C.terracottaLight }}>처방전 인식 완료</p>
            <h1 className="text-[26px] font-black mb-2" style={{ color: C.dark }}>처방전 확인 및 수정</h1>
            <p className="text-[14px] mb-6" style={{ color: C.muted }}>
              오류가 있는 항목을 수정하면{" "}
              <span className="font-bold" style={{ color: C.success }}>자동으로 확인 완료</span>가 돼요.
            </p>

            {/* 확인 진행률 */}
            <div
              className="px-5 py-4 rounded-2xl mb-7 transition-all"
              style={{
                background: allOk ? `${C.success}12` : C.white,
                border: allOk ? `2px solid ${C.success}` : "none",
                boxShadow: allOk ? "none" : "0 2px 12px rgba(30,26,23,0.06)",
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[13px] font-bold" style={{ color: C.dark }}>확인 진행률</span>
                <div className="flex items-center gap-1.5">
                  {allOk && <Check className="w-4 h-4" style={{ color: C.success }} />}
                  <span className="text-[14px] font-black" style={{ color: allOk ? C.success : C.terracotta }}>
                    {confirmed.size} / {allItems.length} 완료
                  </span>
                </div>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "rgba(30,26,23,0.08)" }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${allItems.length ? (confirmed.size / allItems.length) * 100 : 0}%`,
                    background: allOk ? C.success : C.terracotta,
                    transitionDuration: "600ms",
                  }}
                />
              </div>
              {allOk && (
                <p className="text-[12px] font-bold mt-1.5" style={{ color: "#4A7A47" }}>
                  모두 완료됐어요! 아래에서 최종 확인 후 가이드를 만들어보세요.
                </p>
              )}
            </div>

            <div className="space-y-5 mb-7">
              {allItems.map((item) => {
                const isDone = confirmed.has(item.id);
                const issues = fieldIssues(item);
                return (
                  <div key={item.id}>
                    <div
                      className="rounded-2xl overflow-hidden transition-all"
                      style={{
                        background: isDone ? `${C.success}0D` : C.white,
                        border: isDone ? `2px solid ${C.success}` : "2px solid #D94F4F",
                        boxShadow: isDone ? "0 4px 20px rgba(143,174,139,0.20)" : "0 4px 24px rgba(30,26,23,0.10)",
                      }}
                    >
                      <div
                        className="flex items-center justify-between px-6 py-3 border-b"
                        style={{
                          borderColor: isDone ? `${C.success}30` : "rgba(217,79,79,0.15)",
                          background: isDone ? `${C.success}18` : "rgba(217,79,79,0.05)",
                        }}
                      >
                        {isDone ? (
                          <span className="px-3 py-1 rounded-full text-[12px] font-bold text-white" style={{ background: C.success }}>
                            ✓ 확인 완료
                          </span>
                        ) : (
                          <span className="px-3 py-1 rounded-full text-[12px] font-black text-white" style={{ background: "#D94F4F" }}>
                            ⚠ 확인 필요
                          </span>
                        )}
                        <div className="flex items-center gap-2">
                          {isDone && (
                            <button
                              onClick={() => startReEdit(item.id)}
                              className="text-[12px] font-bold px-3 py-1.5 rounded-full transition-all hover:opacity-80"
                              style={{ background: "rgba(143,174,139,0.18)", color: "#4A7A47" }}
                            >
                              수정하기
                            </button>
                          )}
                          {(record?.medications.length ?? 0) > 1 && (
                            <button
                              onClick={() => removeItem(item.id)}
                              disabled={removingId === item.id}
                              className="text-[12px] font-bold px-3 py-1.5 rounded-full transition-all hover:opacity-80 disabled:opacity-50"
                              style={{ background: "rgba(217,79,79,0.12)", color: "#D94F4F" }}
                            >
                              {removingId === item.id ? "삭제 중..." : "삭제"}
                            </button>
                          )}
                        </div>
                      </div>

                      {!isDone && (
                        <div
                          className="mx-5 mt-4 px-4 py-3 rounded-xl flex items-start gap-2.5"
                          style={{ background: "rgba(217,79,79,0.06)", border: "1px solid rgba(217,79,79,0.18)" }}
                        >
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "#D94F4F" }} />
                          {issues.length > 0 ? (
                            <div>
                              <p className="text-[12px] font-bold mb-1" style={{ color: "#C13F3F" }}>수정이 필요한 항목</p>
                              <ul className="space-y-0.5">
                                {issues.map((iss) => (
                                  <li key={iss.field} className="text-[12px]" style={{ color: "#C13F3F" }}>
                                    <span className="font-bold">{FIELDS.find((f) => f.key === iss.field)?.label}</span> — {iss.message}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : (
                            <p className="text-[12px]" style={{ color: "#C13F3F" }}>
                              이 항목은 문제없이 인식됐어요. 필요하면 내용을 직접 수정해주세요.
                            </p>
                          )}
                        </div>
                      )}

                      {/* [2026-07-20 추가] 복합제 등 참조 DB에 없는 실제 약은 자동 검증을 통과하지
                          못할 수 있다 — 사용자가 실제 약이 맞다고 직접 확인하면 진행할 수 있게 함. */}
                      {!isDone && drugNameOk[item.id] === false && (
                        <div className="mx-5 mt-2 mb-1">
                          <button
                            onClick={() => confirmDrugNameAnyway(item.id)}
                            className="text-[12px] font-bold px-3 py-1.5 rounded-full transition-all hover:opacity-80"
                            style={{ background: "rgba(30,26,23,0.06)", color: C.dark }}
                          >
                            철자를 확인했고, 이 약품명이 맞아요
                          </button>
                        </div>
                      )}

                      <div ref={(el) => { itemContainerRefs.current[item.id] = el; }}>
                      <div className="p-6 grid grid-cols-2 gap-4">
                        {FIELDS.map(({ key, label }) => {
                          const hasIssue = !isDone && issues.some((iss) => iss.field === key);
                          return (
                            <div key={key} className={key === "drug_name" ? "col-span-2" : ""}>
                              <label
                                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider mb-1.5"
                                style={{ color: hasIssue ? "#D94F4F" : C.muted }}
                              >
                                {label}
                                {hasIssue && (
                                  <span
                                    className="px-1.5 py-0.5 rounded text-[9px] font-black normal-case tracking-normal"
                                    style={{ background: "#D94F4F", color: C.white }}
                                  >
                                    오류
                                  </span>
                                )}
                              </label>
                              {isDone ? (
                                <p
                                  className="text-[14px] px-4 py-2.5 rounded-xl font-medium"
                                  style={{ color: C.dark, background: `${C.success}12` }}
                                >
                                  {String(edited[item.id]?.[key] ?? "")}
                                </p>
                              ) : (
                                <input
                                  value={String(edited[item.id]?.[key] ?? "")}
                                  onChange={(e) => update(item.id, key, e.target.value)}
                                  onBlur={(e) => handleBlur(item.id, key, e.relatedTarget)}
                                  className="w-full px-4 py-2.5 rounded-xl border text-[14px] outline-none transition-all"
                                  style={{
                                    borderColor: hasIssue ? "#D94F4F" : `${C.terracottaLight}60`,
                                    background: C.white,
                                    color: C.dark,
                                  }}
                                />
                              )}
                            </div>
                          );
                        })}
                      </div>

                      {/* [2026-07-21 추가] 처방확인 화면에서 복용시간을 바로 설정 — 나중에
                          Schedule.tsx에서 또 손대지 않아도 되고, 대시보드/알림에서 시간대별로
                          묶어 보여줄 수 있게 됨. 필수 항목이 아니라(issues에 안 들어감) 몰라도
                          그냥 넘어갈 수 있다 — 모르는 걸 지어내지 않는다는 기존 원칙 유지.
                          [2026-07-21 수정] 같은 시간대 중복 선택 허용 + 직접 시간 입력/반복
                          추가 — 토글(Set) 대신 배열에 계속 추가하고 목록에서 개별 삭제. */}
                      <div className="px-6 pb-6">
                        <label className="block text-[11px] font-bold uppercase tracking-wider mb-1.5" style={{ color: C.muted }}>
                          복용시간 (선택)
                        </label>
                        {isDone ? (
                          <p className="text-[14px] px-4 py-2.5 rounded-xl font-medium" style={{ color: C.dark, background: `${C.success}12` }}>
                            {(doseTimings[item.id] ?? []).length > 0 ? doseTimings[item.id].join(" · ") : "설정 안 함"}
                          </p>
                        ) : (
                          <>
                            <div className="flex flex-wrap gap-2 mb-3">
                              {DOSE_TIMINGS.map((timing) => (
                                <button
                                  key={timing}
                                  type="button"
                                  onClick={() => addDoseTiming(item.id, timing)}
                                  className="flex items-center gap-1 px-3.5 py-2 rounded-full text-[13px] font-bold transition-all hover:opacity-70"
                                  style={{ background: C.ivory, color: C.dark, border: "1.5px solid rgba(30,26,23,0.12)" }}
                                >
                                  <Plus className="w-3 h-3" /> {timing}
                                </button>
                              ))}
                            </div>

                            {(doseTimings[item.id] ?? []).length > 0 && (
                              <div className="flex flex-wrap gap-2 mb-3">
                                {(doseTimings[item.id] ?? []).map((timing, i) => (
                                  <span
                                    key={`${timing}-${i}`}
                                    className="flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 rounded-full text-[13px] font-bold"
                                    style={{ background: C.terracotta, color: C.white }}
                                  >
                                    {timing}
                                    <button
                                      type="button"
                                      onClick={() => removeDoseTimingAt(item.id, i)}
                                      className="w-4 h-4 rounded-full flex items-center justify-center hover:opacity-70"
                                      style={{ background: "rgba(255,255,255,0.25)" }}
                                      aria-label={`${timing} 삭제`}
                                    >
                                      <X className="w-2.5 h-2.5" />
                                    </button>
                                  </span>
                                ))}
                              </div>
                            )}

                            <div className="flex flex-wrap items-center gap-2 mb-2">
                              <span className="text-[12px] font-bold" style={{ color: C.muted }}>직접 시간 설정</span>
                              <input
                                type="time"
                                value={customTimeDraft[item.id] ?? ""}
                                onChange={(e) => setCustomTimeDraft((prev) => ({ ...prev, [item.id]: e.target.value }))}
                                className="px-3 py-1.5 rounded-lg border text-[13px] outline-none"
                                style={{ borderColor: "rgba(30,26,23,0.15)" }}
                              />
                              <button
                                type="button"
                                onClick={() => addCustomTime(item.id)}
                                className="px-3 py-1.5 rounded-full text-[12px] font-bold"
                                style={{ background: "rgba(30,26,23,0.06)", color: C.dark }}
                              >
                                추가
                              </button>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[12px] font-bold" style={{ color: C.muted }}>몇 시간마다 반복</span>
                              <input
                                type="time"
                                value={intervalDraft[item.id]?.start ?? "08:00"}
                                onChange={(e) =>
                                  setIntervalDraft((prev) => ({ ...prev, [item.id]: { hours: prev[item.id]?.hours ?? "", start: e.target.value } }))
                                }
                                className="px-3 py-1.5 rounded-lg border text-[13px] outline-none"
                                style={{ borderColor: "rgba(30,26,23,0.15)" }}
                              />
                              <span className="text-[12px]" style={{ color: C.muted }}>부터</span>
                              <input
                                type="number"
                                min={1}
                                max={24}
                                placeholder="시간"
                                value={intervalDraft[item.id]?.hours ?? ""}
                                onChange={(e) =>
                                  setIntervalDraft((prev) => ({ ...prev, [item.id]: { start: prev[item.id]?.start ?? "08:00", hours: e.target.value } }))
                                }
                                className="w-16 px-3 py-1.5 rounded-lg border text-[13px] outline-none"
                                style={{ borderColor: "rgba(30,26,23,0.15)" }}
                              />
                              <span className="text-[12px]" style={{ color: C.muted }}>시간마다</span>
                              <button
                                type="button"
                                onClick={() => addInterval(item.id)}
                                className="px-3 py-1.5 rounded-full text-[12px] font-bold"
                                style={{ background: "rgba(30,26,23,0.06)", color: C.dark }}
                              >
                                추가
                              </button>
                            </div>

                            {/* [2026-07-23 추가] "1일 N회"만큼 시간대를 다 고르기 전에 카드가
                                접히면 안 되므로, 시간대 선택은 완료 처리를 자동으로 트리거하지
                                않는다 — 다 골랐으면 이 버튼을 눌러야 확인 완료로 넘어간다. */}
                            <button
                              type="button"
                              onClick={() => maybeConfirm(item.id)}
                              className="w-full mt-4 py-2.5 rounded-xl text-[13px] font-bold transition-all hover:opacity-85"
                              style={{ background: C.terracotta, color: C.white }}
                            >
                              복용시간 확인 완료
                            </button>
                          </>
                        )}
                      </div>
                      </div>
                    </div>

                    {/* [2026-07-19 추가, REQ-048] 이 화면은 항상 record.status === "review_required"
                        상태에서만 보이고(위 353번째 줄 가드), 가이드는 confirmMedications() 확정 후에야
                        생성되므로 지금 이 시점엔 record.guide가 사실상 항상 null이다 — 그래도 "가이드
                        존재 여부"를 status로 추측하지 않고 record.guide(GET /records/{id}가 이미 내려주는
                        값, 새 API 불필요)로 직접 판단한다. 요구사항_정의서 REQ-048: 가이드가 있을 때만
                        챗봇 진입 버튼을 노출하고, 없으면 안내 문구만 보여준다(스키마 확장 없음). */}
                    {!isDone && (
                      <div
                        className="flex items-center justify-between gap-4 px-5 py-4 rounded-2xl mt-3"
                        style={{ background: "#FBF8F3", border: "1px solid rgba(30,26,23,0.09)" }}
                      >
                        <p className="text-[13px] font-medium" style={{ color: C.dark }}>
                          {record.guide
                            ? "약품명을 찾기 어려우신가요? AI 챗봇이 도와드릴게요"
                            : "복약 가이드가 생성되면 AI 챗봇으로 질문할 수 있어요"}
                        </p>
                        {record.guide && (
                          <button
                            onClick={() => navigate("/chat", { state: { diagnosis: record.guide!.lifestyle_guide.diagnosis } })}
                            className="shrink-0 px-4 py-2.5 rounded-full text-white font-bold text-[13px] hover:opacity-88 transition-all whitespace-nowrap"
                            style={{ background: C.terracotta }}
                          >
                            챗봇에게 물어보기 💬
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              <button
                onClick={addItem}
                disabled={addingItem}
                className="w-full py-4 rounded-2xl font-bold text-[14px] border-2 border-dashed transition-all hover:bg-black/[0.02] disabled:opacity-50"
                style={{ borderColor: "rgba(30,26,23,0.18)", color: C.muted }}
              >
                {addingItem ? "추가하는 중..." : "+ 약물 추가"}
              </button>
            </div>

            {!allOk && (
              <div
                className="rounded-xl px-5 py-3 mb-5 flex items-center gap-2.5"
                style={{ background: "rgba(30,26,23,0.04)", border: "1px solid rgba(30,26,23,0.10)" }}
              >
                <AlertCircle className="w-4 h-4 shrink-0" style={{ color: C.muted }} />
                <p className="text-[13px]" style={{ color: C.muted }}>오류 항목을 수정하면 자동으로 확인 완료 처리돼요.</p>
              </div>
            )}

            {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

            <button
              disabled={!allOk}
              onClick={() => allOk && setShowFinalModal(true)}
              className="w-full py-5 rounded-full text-white text-[16px] font-black transition-all"
              style={{
                background: allOk ? C.terracotta : "#C8BFB8",
                cursor: allOk ? "pointer" : "not-allowed",
                boxShadow: allOk ? "0 8px 24px rgba(193,101,61,0.30)" : "none",
              }}
            >
              {allOk ? "✓ 확인 완료 · 복약 가이드 만들기" : "확인 완료하고 가이드 만들기"}
            </button>
            <p className="text-center text-[12px] mt-4" style={{ color: C.muted }}>
              본 정보는 의료진의 진단·처방을 대체하지 않습니다
            </p>
          </>
        )}
      </main>

      {showFinalModal && record && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: "rgba(30,26,23,0.55)" }}
          onClick={() => setShowFinalModal(false)}
        >
          <div className="rounded-3xl p-8 w-full max-w-md" style={{ background: C.surface }} onClick={(e) => e.stopPropagation()}>
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 text-[28px]"
              style={{ background: `${C.success}15` }}
            >
              ✅
            </div>
            <h3 className="text-[20px] font-black text-center mb-2" style={{ color: C.dark }}>한 번 더 확인해주세요</h3>
            <p className="text-[14px] text-center mb-6" style={{ color: C.muted }}>
              아래 내용으로 복약 가이드를 만들게 돼요. 맞으면 "가이드 만들기"를 눌러주세요.
            </p>
            <div className="rounded-2xl p-4 mb-6 space-y-2" style={{ background: C.ivory }}>
              {allItems.map((m) => {
                const e = edited[m.id] ?? m;
                return (
                  <div key={m.id} className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: C.success }} />
                    <div>
                      <span className="text-[14px] font-bold" style={{ color: C.dark }}>{e.drug_name}</span>
                      <span className="text-[13px] ml-2" style={{ color: C.muted }}>{e.dosage} · {e.diagnosis}</span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowFinalModal(false)}
                className="flex-1 py-3.5 rounded-full font-bold border-2 text-[15px]"
                style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
              >
                다시 확인
              </button>
              <button
                onClick={startGuideGeneration}
                className="flex-[1.5] py-3.5 rounded-full text-white font-black text-[15px] hover:opacity-88 transition-all"
                style={{ background: C.terracotta, boxShadow: "0 4px 16px rgba(193,101,61,0.30)" }}
              >
                가이드 만들기 →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
