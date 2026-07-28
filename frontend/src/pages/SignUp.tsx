import { Fragment, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Building2, Check, Mail, MessageSquare, Phone, User } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import NavBar from "../components/NavBar";
import { checkCaregiverDuplicate, checkPatientDuplicate, createCaregiver, createPatient } from "../api/monitoring";
import { login } from "../api/auth";
import { C } from "../theme";

type MemberType = "personal" | "organization";
type PatientRole = "patient" | "guardian";

const ORG_TYPE_OPTIONS = ["요양원", "정부기관", "협회", "보건소", "기타"];
const STEPS = ["약관동의", "유형선택", "정보입력", "본인인증"];

/** [2026-07-23 추가] 생년월일 형식만 검증한다 — 미래 날짜도 허용해야 해서(대리 가입 등
 * 정확한 생년월일을 모르는 경우 포함) 오늘 이전인지는 확인하지 않고, "YYYY.MM.DD" 류
 * 구분자(.,-,/)로 연/월/일이 실제로 존재하는 날짜인지만 본다. 빈 값은 선택 입력이라 통과. */
function isValidBirthDate(input: string): boolean {
  const trimmed = input.trim();
  if (!trimmed) return true;
  const match = trimmed.match(/^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$/);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12) return false;
  const daysInMonth = new Date(year, month, 0).getDate();
  return day >= 1 && day <= daysInMonth;
}

/** [2026-07-23 추가] 생년월일 입력 중 숫자 4자리(연) 뒤, 2자리(월) 뒤에 "."을 자동으로
 * 붙여준다 — 매번 숫자만 남기고 다시 조립하는 방식이라 백스페이스로 지울 때도 그대로
 * 재적용된다. */
function formatBirthDateInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  const year = digits.slice(0, 4);
  const month = digits.slice(4, 6);
  const day = digits.slice(6, 8);
  if (digits.length > 6) return `${year}.${month}.${day}`;
  if (digits.length > 4) return `${year}.${month}`;
  return year;
}

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center mb-8">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const active = n === current;
        const done = n < current;
        return (
          <Fragment key={n}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-[13px] font-black transition-all"
                style={{
                  background: active ? C.terracotta : done ? `${C.terracotta}22` : "rgba(30,26,23,0.09)",
                  color: active ? C.white : done ? C.terracotta : C.muted,
                }}
              >
                {done ? <Check className="w-4 h-4" /> : n}
              </div>
              <span className="text-[10px] font-bold whitespace-nowrap" style={{ color: active ? C.terracotta : C.muted }}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className="h-px mx-2 mb-5 shrink-0" style={{ width: 28, background: n < current ? `${C.terracotta}55` : "rgba(30,26,23,0.12)" }} />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}

const inputCss = "w-full px-4 py-3.5 rounded-xl border text-[15px] outline-none";
const inputStyle = { borderColor: "rgba(30,26,23,0.12)", color: C.dark, background: C.ivory };

function Field({
  label, value, onChange, placeholder, type = "text", error, onBlur,
}: { label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string; error?: string; onBlur?: () => void }) {
  return (
    <div>
      <label className="block text-[13px] font-bold mb-1.5" style={{ color: C.dark }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        className={inputCss}
        style={{ ...inputStyle, borderColor: error ? "#D94F4F" : inputStyle.borderColor }}
      />
      {error && <p className="text-[12px] mt-1" style={{ color: "#D94F4F" }}>{error}</p>}
    </div>
  );
}

interface NotifPrefs { push: boolean; sms: boolean; email: boolean; }

function NotificationSettings({ prefs, setPrefs, pushError }: { prefs: NotifPrefs; setPrefs: (p: NotifPrefs) => void; pushError?: boolean }) {
  const items: { key: keyof NotifPrefs; icon: LucideIcon; label: string; desc: string; required: boolean }[] = [
    { key: "push", icon: Bell, label: "Push 알림 허용", desc: "복약 시간, 건강 정보 앱 푸시 알림", required: true },
    { key: "sms", icon: MessageSquare, label: "문자(SMS) 수신 허용", desc: "복약 안내·보호자 알림 문자 수신", required: false },
    { key: "email", icon: Mail, label: "이메일 수신 허용", desc: "건강 뉴스레터, 서비스 공지 이메일", required: false },
  ];
  return (
    <div className="mt-5 pt-5 border-t" style={{ borderColor: "rgba(30,26,23,0.10)" }}>
      <div className="flex items-center gap-2 mb-3">
        <p className="text-[13px] font-black" style={{ color: C.dark }}>알림 수신 설정</p>
        <span className="px-2 py-0.5 rounded text-[10px] font-black" style={{ background: `${C.terracotta}15`, color: C.terracotta }}>Push 필수</span>
      </div>
      <div className="space-y-2">
        {items.map(({ key, icon: Icon, label, desc, required }) => {
          const checked = prefs[key];
          const showError = key === "push" && pushError && !checked;
          return (
            <button
              key={key}
              onClick={() => { if (!required || !checked) setPrefs({ ...prefs, [key]: !checked }); }}
              className="flex items-center gap-3 w-full px-4 py-3 rounded-xl transition-all text-left"
              style={{
                background: showError ? "rgba(217,79,79,0.06)" : checked ? (required ? `${C.terracotta}08` : `${C.success}10`) : "rgba(30,26,23,0.03)",
                border: `1.5px solid ${showError ? "#D94F4F" : checked ? (required ? C.terracotta : C.success) : "rgba(30,26,23,0.09)"}`,
              }}
            >
              <div
                className="w-5 h-5 flex items-center justify-center shrink-0 transition-all"
                style={{ background: checked ? (required ? C.terracotta : C.success) : C.white, border: `2px solid ${checked ? (required ? C.terracotta : C.success) : "rgba(30,26,23,0.2)"}`, borderRadius: 5 }}
              >
                {checked && <Check className="w-3 h-3 text-white" />}
              </div>
              <Icon
                className="w-[15px] h-[15px] shrink-0"
                style={{ color: checked ? (required ? C.terracotta : "#4A7A47") : C.muted }}
                strokeWidth={2.2}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-[13px] font-bold" style={{ color: checked ? (required ? C.terracotta : "#4A7A47") : C.dark }}>{label}</p>
                  {required && <span className="px-1.5 py-0.5 rounded text-[10px] font-black shrink-0" style={{ background: `${C.terracotta}15`, color: C.terracotta }}>필수</span>}
                </div>
                <p className="text-[11px]" style={{ color: C.muted }}>{desc}</p>
              </div>
            </button>
          );
        })}
      </div>
      {!prefs.push && (
        <p className="text-[12px] mt-2" style={{ color: pushError ? "#D94F4F" : C.terracotta }}>
          Push 알림은 복약 알림 서비스 이용을 위해 필수로 허용해주세요.
        </p>
      )}
    </div>
  );
}

export default function SignUp() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);

  // Step 1 — 약관동의
  const [t1, setT1] = useState(false);
  const [t2, setT2] = useState(false);
  const [t3, setT3] = useState(false);
  const [t4, setT4] = useState(false);
  const requiredChecked = t1 && t2 && t3;
  const allChecked = t1 && t2 && t3 && t4;

  // Step 2 — 유형선택
  const [memberType, setMemberType] = useState<MemberType | null>(null);

  // Step 3 — 정보입력 (개인)
  const [pRole, setPRole] = useState<PatientRole>("patient");
  const [name, setName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [birthDateTouched, setBirthDateTouched] = useState(false);
  // [2026-07-22 추가] 환자 관리 테이블(PatientManagement.tsx)의 "성별" 컬럼용 — 환자 본인
  // 가입에서만 받는다(보호자/기관 계정엔 해당 없는 필드). 모르면 그냥 비워둔다.
  const [gender, setGender] = useState<"male" | "female" | "">("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  // [2026-07-23 추가] 이메일/전화번호에서 다른 필드로 넘어갈 때(onBlur) 바로 중복 확인 —
  // 비밀번호 확인과 동일하게 빨간 테두리 + 문구로 보여준다. 값을 고치면 다시 확인 전까지
  // 초기화(더 이상 유효하지 않은 판정을 계속 보여주지 않기 위함).
  const [emailTaken, setEmailTaken] = useState(false);
  const [phoneTaken, setPhoneTaken] = useState(false);

  // Step 3 — 정보입력 (단체)
  const [orgName, setOrgName] = useState("");
  const [orgType, setOrgType] = useState(ORG_TYPE_OPTIONS[0]);
  const [businessRegNo, setBusinessRegNo] = useState("");
  const [managerName, setManagerName] = useState("");
  const [managerEmail, setManagerEmail] = useState("");
  const [managerPhone, setManagerPhone] = useState("");
  const [managerEmailTaken, setManagerEmailTaken] = useState(false);
  const [managerPhoneTaken, setManagerPhoneTaken] = useState(false);

  const [notifPrefs, setNotifPrefs] = useState<NotifPrefs>({ push: false, sms: false, email: false });

  // step3Valid이 false일 때 "왜 안 눌리는지" 알려주기 위한 필드별 표시 — 버튼을 누르기
  // 전까지는 빨간 테두리를 숨겨서(attempted) 처음 화면 진입 시 전부 빨갛게 보이지 않게 함
  const [step3Attempted, setStep3Attempted] = useState(false);

  // Step 4 — 본인인증 (데모: 실제 SMS 발송 없이 6자리 입력하면 통과)
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState("");
  const [timer, setTimer] = useState(180);

  useEffect(() => {
    if (!codeSent || timer <= 0) return;
    const t = setTimeout(() => setTimer((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [codeSent, timer]);

  // [2026-07-23 추가] 환자 본인/보호자 전환은 확인 대상 테이블(patients vs caregivers)이
  // 바뀌므로, 이전 판정을 그대로 들고 있으면 안 된다 — 다시 확인 전까지 초기화.
  useEffect(() => {
    setEmailTaken(false);
    setPhoneTaken(false);
  }, [pRole]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const passwordValid = password.length >= 8 && password === passwordConfirm;
  const verifyPhone = memberType === "organization" ? managerPhone : phone;
  // [2026-07-24 추가] 중복 확인은 onBlur에서 즉시 결과가 나오므로, "다음" 버튼을 처음
  // 눌러보기 전(step3Attempted=false)에도 이미 알고 있는 중복 상태라면 바로 흐리게
  // 보여줘야 한다 — 안 그러면 중복 문구가 떠 있는데도 버튼만 멀쩡해 보여서 눌러도 되는
  // 것처럼 오해하게 된다.
  const duplicateBlocked =
    memberType === "organization" ? managerEmailTaken || managerPhoneTaken : emailTaken || phoneTaken;

  const step3Valid =
    memberType === "organization"
      ? Boolean(
          orgName.trim() && businessRegNo.trim() && managerName.trim() && managerPhone.trim() &&
          passwordValid && !managerEmailTaken && !managerPhoneTaken
        )
      : Boolean(name.trim() && phone.trim() && passwordValid && !emailTaken && !phoneTaken && isValidBirthDate(birthDate));

  const showErr = (invalid: boolean) => step3Attempted && invalid;
  const nameError = showErr(!name.trim()) ? "이름을 입력해주세요" : undefined;
  const birthDateError =
    (birthDateTouched || step3Attempted) && birthDate.trim() && !isValidBirthDate(birthDate)
      ? "생년월일이 정확한지 확인해주세요."
      : undefined;
  const emailError = emailTaken ? "이미 사용중인 이메일이에요." : undefined;
  const phoneError = phoneTaken
    ? "이미 사용중인 전화번호예요."
    : showErr(!phone.trim())
    ? "전화번호를 입력해주세요"
    : undefined;
  const orgNameError = showErr(!orgName.trim()) ? "기관명을 입력해주세요" : undefined;
  const businessRegNoError = showErr(!businessRegNo.trim()) ? "사업자등록번호를 입력해주세요" : undefined;
  const managerNameError = showErr(!managerName.trim()) ? "담당자 이름을 입력해주세요" : undefined;
  const managerEmailError = managerEmailTaken ? "이미 사용중인 이메일이에요." : undefined;
  const managerPhoneError = managerPhoneTaken
    ? "이미 사용중인 전화번호예요."
    : showErr(!managerPhone.trim())
    ? "담당자 전화번호를 입력해주세요"
    : undefined;
  const passwordError = showErr(password.length < 8) ? "비밀번호는 8자 이상이어야 해요" : undefined;
  const passwordConfirmError =
    passwordConfirm.length > 0 && password !== passwordConfirm
      ? "비밀번호가 일치하지 않아요."
      : showErr(!passwordConfirm)
      ? "비밀번호를 다시 입력해주세요"
      : undefined;
  const pushError = showErr(!notifPrefs.push);

  // [2026-07-23 추가] 이메일/전화번호 입력 필드에서 포커스를 잃으면 바로 중복 확인 —
  // 실패(네트워크 오류 등)는 조용히 무시한다. 최종 제출 시 서버가 다시 한번 막아준다.
  const checkEmailDuplicate = async () => {
    if (!email.trim()) return;
    try {
      const result =
        pRole === "patient"
          ? await checkPatientDuplicate({ email: email.trim() })
          : await checkCaregiverDuplicate({ relation_type: "guardian", email: email.trim() });
      setEmailTaken(result.email_taken);
    } catch {
      // ignore
    }
  };
  const checkPhoneDuplicate = async () => {
    if (!phone.trim()) return;
    try {
      const result =
        pRole === "patient"
          ? await checkPatientDuplicate({ phone: phone.trim() })
          : await checkCaregiverDuplicate({ relation_type: "guardian", phone: phone.trim() });
      setPhoneTaken(result.phone_taken);
    } catch {
      // ignore
    }
  };
  const checkManagerEmailDuplicate = async () => {
    if (!managerEmail.trim()) return;
    try {
      const result = await checkCaregiverDuplicate({ relation_type: "organization", email: managerEmail.trim() });
      setManagerEmailTaken(result.email_taken);
    } catch {
      // ignore
    }
  };
  const checkManagerPhoneDuplicate = async () => {
    if (!managerPhone.trim()) return;
    try {
      const result = await checkCaregiverDuplicate({ relation_type: "organization", phone: managerPhone.trim() });
      setManagerPhoneTaken(result.phone_taken);
    } catch {
      // ignore
    }
  };

  const sendCode = () => {
    setCodeSent(true);
    setTimer(180);
  };

  const submit = async () => {
    if (!memberType || !step3Valid) return;
    setSubmitting(true);
    setError("");
    try {
      if (memberType === "personal" && pRole === "patient") {
        const patient = await createPatient({
          name: name.trim(),
          phone: phone.trim(),
          email: email.trim() || undefined,
          birth_date: birthDate.trim() || undefined,
          gender: gender || undefined,
          password,
          push_enabled: notifPrefs.push,
          sms_enabled: notifPrefs.sms,
          email_opt_in: notifPrefs.email,
        });
        localStorage.setItem("patient_id", String(patient.id));
        localStorage.removeItem("caregiver_id");
        // [7/13] 환자 본인도 가입 직후 로그인해 토큰을 받는다 — Dashboard/Schedule/
        // Notification 등 공유 화면의 인가된 API 호출에 필요 (issue #28).
        const { access_token, name: loggedInName } = await login(phone.trim(), password);
        localStorage.setItem("access_token", access_token);
        // [2026-07-19 추가] NavBar가 화면마다 "김건강"으로 하드코딩돼있던 문제 수정
        localStorage.setItem("user_name", loggedInName);
      } else if (memberType === "personal") {
        await createCaregiver({
          name: name.trim(),
          relation_type: "guardian",
          phone: phone.trim(),
          email: email.trim() || undefined,
          birth_date: birthDate.trim() || undefined,
          password,
          push_enabled: notifPrefs.push,
          sms_enabled: notifPrefs.sms,
          email_opt_in: notifPrefs.email,
        });
        // [7/10] 가입 직후엔 토큰이 없어서 다음 화면(PatientManagement.tsx)의 인가된
        // API 호출이 401 나던 문제 — 방금 만든 계정으로 바로 로그인해 토큰을 받는다.
        const { access_token, caregiver_id, name: loggedInName } = await login(phone.trim(), password);
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("caregiver_id", String(caregiver_id));
        localStorage.setItem("user_name", loggedInName);
      } else {
        await createCaregiver({
          // 기관 계정도 화면 상단에는 기관명이 아니라 실제 로그인/담당자 이름이 보여야 한다.
          // 기관명은 org_name에 별도 보관한다.
          name: managerName.trim(),
          relation_type: "organization",
          phone: managerPhone.trim(),
          email: managerEmail.trim() || undefined,
          password,
          push_enabled: notifPrefs.push,
          sms_enabled: notifPrefs.sms,
          email_opt_in: notifPrefs.email,
          org_name: orgName.trim(),
          org_type: orgType,
          business_reg_no: businessRegNo.trim(),
          manager_name: managerName.trim(),
          manager_phone: managerPhone.trim(),
        });
        const { access_token, caregiver_id, name: loggedInName } = await login(managerPhone.trim(), password);
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("caregiver_id", String(caregiver_id));
        localStorage.setItem("user_name", loggedInName);
      }
      setDone(true);
    } catch (e) {
      // [2026-07-22 수정] 이메일/전화번호 중복(409)처럼 백엔드가 구체적인 사유를 주는
      // 경우까지 "가입 처리에 실패했어요"로 뭉개면 사용자가 뭘 고쳐야 할지 알 수 없다
      // — Schedule.tsx의 describeError와 동일한 방식으로 detail이 있으면 그대로 보여준다.
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "가입 처리에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  // [2026-07-16] 환자 본인 가입 직후엔 대시보드 전에 식사 시간 체크리스트를 먼저 물어본다
  // (복약 알림 시각 설정에 쓰임) — 보호자/기관 가입은 아직 케어할 환자가 없어서 해당 없음.
  const nextRoute = memberType === "personal" && pRole === "patient" ? "/meal-check" : "/patients";
  const nextLabel = memberType === "personal" && pRole === "patient" ? "시작하기" : "환자 등록하러 가기";
  const mm = String(Math.floor(timer / 60)).padStart(2, "0");
  const ss = String(timer % 60).padStart(2, "0");

  return (
    <div className="min-h-screen flex flex-col" style={{ background: C.ivory }}>
      <NavBar />

      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="w-full" style={{ maxWidth: 480 }}>
          {!done && <StepIndicator current={step} />}
          <div className="rounded-3xl p-8" style={{ background: C.surface, boxShadow: "0 8px 40px rgba(30,26,23,0.10)" }}>
            {done ? (
              <div className="text-center py-6">
                <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ background: `${C.success}22` }}>
                  <Check className="w-10 h-10" style={{ color: C.success }} />
                </div>
                <h2 className="text-[24px] font-black mb-2" style={{ color: C.dark }}>가입이 완료되었어요!</h2>
                <p className="text-[15px] mb-8" style={{ color: C.muted }}>건강동행과 함께 건강한 일상을 시작해보세요</p>
                <button onClick={() => navigate(nextRoute)} className="w-full py-4 rounded-full text-white font-black text-[16px]" style={{ background: C.terracotta }}>
                  {nextLabel}
                </button>
              </div>
            ) : step === 1 ? (
              <>
                <h2 className="text-[20px] font-black mb-1.5 leading-snug" style={{ color: C.dark }}>
                  서비스 이용을 위해<br />약관에 동의해주세요
                </h2>
                <p className="text-[14px] mb-6" style={{ color: C.muted }}>필수 항목 동의 후 서비스를 이용하실 수 있어요.</p>
                <button
                  onClick={() => { const next = !allChecked; setT1(next); setT2(next); setT3(next); setT4(next); }}
                  className="flex items-center gap-3 w-full px-4 py-4 rounded-2xl mb-3 transition-all"
                  style={{ background: allChecked ? `${C.terracotta}06` : C.ivory, border: `1.5px solid ${allChecked ? C.terracotta : "rgba(30,26,23,0.12)"}` }}
                >
                  <div className="w-6 h-6 rounded-md flex items-center justify-center shrink-0" style={{ background: allChecked ? C.terracotta : C.white, border: `2px solid ${allChecked ? C.terracotta : "rgba(30,26,23,0.22)"}` }}>
                    {allChecked && <Check className="w-3.5 h-3.5 text-white" />}
                  </div>
                  <span className="text-[16px] font-black" style={{ color: C.dark }}>전체 동의</span>
                </button>
                <div className="h-px mb-3" style={{ background: "rgba(30,26,23,0.08)" }} />
                {(
                  [
                    { checked: t1, set: setT1, label: "서비스 이용약관 동의", badge: "필수" },
                    { checked: t2, set: setT2, label: "개인정보 수집·이용 동의 (진료기록 포함)", badge: "필수" },
                    { checked: t3, set: setT3, label: "만 14세 이상입니다", badge: "필수" },
                    { checked: t4, set: setT4, label: "건강 정보 뉴스레터 수신 동의", badge: "선택" },
                  ] as { checked: boolean; set: (v: boolean) => void; label: string; badge: string }[]
                ).map(({ checked, set, label, badge }) => (
                  <div key={label} className="flex items-center gap-3 py-3 border-b last:border-0" style={{ borderColor: "rgba(30,26,23,0.07)" }}>
                    <button
                      onClick={() => set(!checked)}
                      className="w-5 h-5 flex items-center justify-center shrink-0"
                      style={{ background: checked ? C.terracotta : C.white, border: `2px solid ${checked ? C.terracotta : "rgba(30,26,23,0.2)"}`, borderRadius: 5 }}
                    >
                      {checked && <Check className="w-3 h-3 text-white" />}
                    </button>
                    <span className="px-2 py-0.5 rounded text-[11px] font-black shrink-0" style={{ background: badge === "필수" ? `${C.terracotta}15` : "rgba(30,26,23,0.08)", color: badge === "필수" ? C.terracotta : C.muted }}>
                      {badge}
                    </span>
                    <span className="flex-1 text-[14px]" style={{ color: C.dark }}>{label}</span>
                  </div>
                ))}
                <button
                  disabled={!requiredChecked}
                  onClick={() => setStep(2)}
                  className="w-full py-4 rounded-full text-white font-black text-[16px] mt-6 disabled:opacity-40"
                  style={{ background: C.terracotta }}
                >
                  동의하고 계속하기
                </button>
              </>
            ) : step === 2 ? (
              <>
                <h2 className="text-[20px] font-black mb-1.5 leading-snug" style={{ color: C.dark }}>
                  어떤 회원으로<br />가입하시나요?
                </h2>
                <p className="text-[14px] mb-6" style={{ color: C.muted }}>이용 목적에 맞는 유형을 선택해주세요.</p>
                <div className="grid grid-cols-2 gap-4 mb-6">
                  {(
                    [
                      { key: "personal" as const, icon: User, title: "개인", desc: "환자 본인 또는 보호자(가족)", tags: ["환자 본인", "보호자"] },
                      { key: "organization" as const, icon: Building2, title: "단체·기관", desc: "요양보호사, 협회, 보건소 등 기관 소속", tags: ["요양보호사", "협회", "보건소"] },
                    ]
                  ).map(({ key, icon: Icon, title, desc, tags }) => {
                    const sel = memberType === key;
                    return (
                      <button
                        key={key}
                        onClick={() => setMemberType(key)}
                        className="flex flex-col items-start text-left p-5 rounded-2xl transition-all w-full"
                        style={{ background: sel ? `${C.terracotta}06` : C.white, border: `2px solid ${sel ? C.terracotta : "rgba(30,26,23,0.10)"}` }}
                      >
                        <div
                          className="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
                          style={{ background: sel ? C.terracotta : C.ivory }}
                        >
                          <Icon className="w-6 h-6" style={{ color: sel ? C.white : C.terracotta }} strokeWidth={2} />
                        </div>
                        <p className="text-[16px] font-black mb-1" style={{ color: sel ? C.terracotta : C.dark }}>{title}</p>
                        <p className="text-[12px] leading-relaxed mb-3" style={{ color: C.muted }}>{desc}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {tags.map((t) => (
                            <span key={t} className="px-2.5 py-1 rounded-full text-[11px] font-bold" style={{ background: sel ? `${C.terracotta}15` : "rgba(30,26,23,0.07)", color: sel ? C.terracotta : C.muted }}>
                              {t}
                            </span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-3">
                  <button onClick={() => setStep(1)} className="flex-1 py-4 rounded-full font-bold text-[15px] border-2" style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}>
                    이전
                  </button>
                  <button
                    disabled={!memberType}
                    onClick={() => setStep(3)}
                    className="flex-[2] py-4 rounded-full text-white font-black text-[15px] disabled:opacity-40"
                    style={{ background: C.terracotta }}
                  >
                    다음
                  </button>
                </div>
              </>
            ) : step === 3 ? (
              <>
                <h2 className="text-[20px] font-black mb-1" style={{ color: C.dark }}>
                  {memberType === "organization" ? "기관 정보를 입력해주세요" : "기본 정보를 입력해주세요"}
                </h2>
                <button onClick={() => setStep(2)} className="text-[13px] mb-5 block" style={{ color: C.muted }}>← 이전</button>

                <div className="space-y-4">
                  {memberType === "organization" ? (
                    <>
                      <Field label="기관명" value={orgName} onChange={setOrgName} placeholder="예: 행복요양원" error={orgNameError} />
                      <div>
                        <label className="block text-[13px] font-bold mb-1.5" style={{ color: C.dark }}>기관 유형</label>
                        <select value={orgType} onChange={(e) => setOrgType(e.target.value)} className={inputCss} style={inputStyle}>
                          {ORG_TYPE_OPTIONS.map((t) => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                      <Field label="사업자등록번호" value={businessRegNo} onChange={setBusinessRegNo} placeholder="000-00-00000" error={businessRegNoError} />
                      <Field label="담당자 이름" value={managerName} onChange={setManagerName} placeholder="홍길동" error={managerNameError} />
                      <Field
                        label="담당자 이메일"
                        value={managerEmail}
                        onChange={(v) => { setManagerEmail(v); setManagerEmailTaken(false); }}
                        onBlur={checkManagerEmailDuplicate}
                        placeholder="manager@agency.com"
                        error={managerEmailError}
                      />
                      <Field
                        label="담당자 전화번호"
                        value={managerPhone}
                        onChange={(v) => { setManagerPhone(v); setManagerPhoneTaken(false); }}
                        onBlur={checkManagerPhoneDuplicate}
                        placeholder="010-0000-0000"
                        error={managerPhoneError}
                      />
                    </>
                  ) : (
                    <>
                      <Field label="이름" value={name} onChange={setName} placeholder="홍길동" error={nameError} />
                      <div>
                        <p className="text-[12px] mb-1.5" style={{ color: C.muted }}>현재 이후로도 가입이 가능해요.</p>
                        <Field
                          label="생년월일"
                          value={birthDate}
                          onChange={(v) => { setBirthDate(formatBirthDateInput(v)); setBirthDateTouched(false); }}
                          onBlur={() => setBirthDateTouched(true)}
                          placeholder="1945.03.15"
                          error={birthDateError}
                        />
                      </div>
                      {pRole === "patient" && (
                        <div>
                          <label className="block text-[13px] font-bold mb-1.5" style={{ color: C.dark }}>성별</label>
                          <div className="flex gap-3">
                            {(["female", "male"] as const).map((g) => (
                              <button
                                key={g}
                                type="button"
                                onClick={() => setGender(g)}
                                className="flex-1 py-3 rounded-xl font-bold text-[14px] transition-all"
                                style={{
                                  background: gender === g ? C.terracotta : C.ivory,
                                  color: gender === g ? C.white : C.dark,
                                  border: `1.5px solid ${gender === g ? C.terracotta : "rgba(30,26,23,0.12)"}`,
                                }}
                              >
                                {g === "female" ? "여성" : "남성"}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      <Field
                        label="이메일"
                        value={email}
                        onChange={(v) => { setEmail(v); setEmailTaken(false); }}
                        onBlur={checkEmailDuplicate}
                        placeholder="example@email.com"
                        type="email"
                        error={emailError}
                      />
                      <Field
                        label="전화번호"
                        value={phone}
                        onChange={(v) => { setPhone(v); setPhoneTaken(false); }}
                        onBlur={checkPhoneDuplicate}
                        placeholder="010-0000-0000"
                        error={phoneError}
                      />
                    </>
                  )}

                  <Field label="비밀번호" value={password} onChange={setPassword} placeholder="비밀번호 입력" type="password" error={passwordError} />
                  <p className="text-[12px] -mt-2" style={{ color: C.muted }}>8자 이상</p>
                  <Field label="비밀번호 확인" value={passwordConfirm} onChange={setPasswordConfirm} placeholder="비밀번호 재입력" type="password" error={passwordConfirmError} />

                  {memberType === "personal" && (
                    <div>
                      <label className="block text-[13px] font-bold mb-2" style={{ color: C.dark }}>가입 유형</label>
                      <div className="flex gap-3">
                        {(["patient", "guardian"] as PatientRole[]).map((r) => (
                          <button
                            key={r}
                            onClick={() => setPRole(r)}
                            className="flex items-center gap-2 px-5 py-3 rounded-full font-bold text-[14px] transition-all"
                            style={{ background: pRole === r ? C.terracotta : C.white, color: pRole === r ? C.white : C.dark, border: `1.5px solid ${pRole === r ? C.terracotta : "rgba(30,26,23,0.12)"}` }}
                          >
                            <div className="w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0" style={{ borderColor: pRole === r ? C.white : "rgba(30,26,23,0.3)" }}>
                              {pRole === r && <div className="w-2 h-2 rounded-full" style={{ background: C.white }} />}
                            </div>
                            {r === "patient" ? "환자 본인" : "보호자(가족)"}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <NotificationSettings prefs={notifPrefs} setPrefs={setNotifPrefs} pushError={pushError} />

                <button
                  onClick={() => {
                    if (step3Valid && notifPrefs.push) setStep(4);
                    else setStep3Attempted(true);
                  }}
                  className="w-full py-4 rounded-full text-white font-black text-[16px] mt-6 transition-opacity"
                  style={{
                    background: C.terracotta,
                    opacity: duplicateBlocked || (step3Attempted && (!step3Valid || !notifPrefs.push)) ? 0.6 : 1,
                  }}
                >
                  다음 (본인인증)
                </button>
              </>
            ) : (
              <>
                <div className="text-center mb-6">
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: `${C.terracotta}12` }}>
                    <Phone className="w-7 h-7" style={{ color: C.terracotta }} />
                  </div>
                  <h2 className="text-[20px] font-black mb-1" style={{ color: C.dark }}>휴대폰 본인인증</h2>
                  <p className="text-[13px]" style={{ color: C.muted }}>
                    가입하신 전화번호로 인증코드를 보내드려요
                    <br />
                    <span style={{ color: C.terracottaLight }}>(데모: 실제 발송 없이 6자리 입력하면 통과돼요)</span>
                  </p>
                </div>
                <div className="flex items-center justify-between px-4 py-3.5 rounded-xl mb-4" style={{ background: C.ivory, border: "1.5px solid rgba(30,26,23,0.12)" }}>
                  <span className="text-[16px] font-bold" style={{ color: C.dark }}>{verifyPhone || "전화번호 없음"}</span>
                  <button onClick={() => setStep(3)} className="text-[13px] font-bold underline underline-offset-2" style={{ color: C.terracotta }}>수정</button>
                </div>
                <button onClick={sendCode} className="w-full py-3.5 rounded-full text-white font-bold text-[15px] mb-5" style={{ background: C.terracotta }}>
                  {codeSent ? "인증코드 재발송" : "인증코드 받기"}
                </button>
                {codeSent && (
                  <div className="mb-4">
                    <label className="block text-[13px] font-bold mb-2" style={{ color: C.dark }}>인증코드 6자리</label>
                    <div className="flex items-center gap-3">
                      <input
                        maxLength={6}
                        value={code}
                        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                        placeholder="······"
                        // [2026-07-23 수정] flex-1인데 min-width가 기본값(auto)이라, 6자리 +
                        // letterSpacing 만큼의 내용 너비가 flex row(타이머와 함께)보다 넓어지면
                        // 줄어들지 못하고 오른쪽 칸(타이머) 쪽으로 넘쳤다 — min-w-0으로 실제
                        // 줄어들 수 있게 하고, 글자 크기·자간도 여유 있게 살짝 줄였다.
                        className="flex-1 min-w-0 text-center text-[22px] font-black px-3 py-4 rounded-xl outline-none"
                        style={{ background: C.ivory, border: `2px solid ${code.length === 6 ? C.terracotta : "rgba(30,26,23,0.15)"}`, color: C.dark, letterSpacing: "0.35em" }}
                      />
                      <div className="shrink-0 font-black tabular-nums text-[17px]" style={{ color: C.terracotta, minWidth: 56, textAlign: "center" }}>
                        {mm}:{ss}
                      </div>
                    </div>
                    <p className="text-[13px] mt-2 text-center">
                      <span style={{ color: C.muted }}>코드를 받지 못하셨나요? </span>
                      <button onClick={sendCode} className="font-bold underline underline-offset-2" style={{ color: C.terracotta }}>재전송</button>
                    </p>
                  </div>
                )}
                {error && <p className="text-[13px] mb-4 text-center" style={{ color: "#D94F4F" }}>{error}</p>}
                <button
                  disabled={!codeSent || code.length !== 6 || submitting}
                  onClick={submit}
                  className="w-full py-4 rounded-full text-white font-black text-[16px] mt-2 disabled:opacity-40"
                  style={{ background: C.terracotta }}
                >
                  {submitting ? "가입 처리 중..." : "인증 완료하고 가입하기"}
                </button>
              </>
            )}
          </div>
          <p className="text-center text-[12px] mt-6" style={{ color: C.muted }}>
            이미 계정이 있으신가요?{" "}
            <button onClick={() => navigate("/login")} className="font-bold underline" style={{ color: C.terracotta }}>
              로그인
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}
