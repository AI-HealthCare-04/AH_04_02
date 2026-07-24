import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Lock } from "lucide-react";
import NavBar from "../components/NavBar";
import LoadingDots from "../components/LoadingDots";
import { verifyPassword } from "../api/auth";
import {
  getCaregivers,
  getPatients,
  updateCaregiver,
  updatePatient,
  type Caregiver,
  type Patient,
} from "../api/monitoring";
import { getCurrentCaregiverId, getCurrentPatientId, getCurrentUserName } from "../lib/session";
import { C } from "../theme";

const ORG_TYPE_OPTIONS = ["요양원", "정부기관", "협회", "보건소", "기타"];

const inputCss = "w-full px-4 py-3.5 rounded-xl border text-[15px] outline-none";
const inputStyle = { borderColor: "rgba(30,26,23,0.12)", color: C.dark, background: C.ivory };

function Field({
  label, value, onChange, placeholder, type = "text",
}: { label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string }) {
  return (
    <div>
      <label className="block text-[13px] font-bold mb-1.5" style={{ color: C.dark }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={inputCss}
        style={inputStyle}
      />
    </div>
  );
}

function PrefToggle({ label, checked, onClick }: { label: string; checked: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-3 w-full px-4 py-3 rounded-xl transition-all text-left"
      style={{
        background: checked ? `${C.success}10` : "rgba(30,26,23,0.03)",
        border: `1.5px solid ${checked ? C.success : "rgba(30,26,23,0.09)"}`,
      }}
    >
      <div
        className="w-5 h-5 flex items-center justify-center shrink-0"
        style={{ background: checked ? C.success : C.white, border: `2px solid ${checked ? C.success : "rgba(30,26,23,0.2)"}`, borderRadius: 5 }}
      >
        {checked && <Check className="w-3 h-3 text-white" />}
      </div>
      <span className="text-[14px] font-semibold" style={{ color: C.dark }}>{label}</span>
    </button>
  );
}

/**
 * "내 정보" — 회원가입 때 받은 정보를 확인·수정하는 화면(MyPage.tsx "내 정보"에서 진입).
 * [사용자 요청] 열람 전 비밀번호 재확인을 거친다 — verify-password는 상태를 바꾸지 않고
 * 현재 비밀번호가 맞는지만 본다. 확인된 상태는 이 화면을 벗어나면(새로고침 포함) 다시 요구된다.
 */
export default function MyInfo() {
  const navigate = useNavigate();
  const caregiverId = getCurrentCaregiverId();
  const patientId = getCurrentPatientId();

  const [verified, setVerified] = useState(false);
  const [password, setPassword] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState("");

  const [patient, setPatient] = useState<Patient | null>(null);
  const [caregiver, setCaregiver] = useState<Caregiver | null>(null);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState<"male" | "female" | "">("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgType, setOrgType] = useState(ORG_TYPE_OPTIONS[0]);
  const [businessRegNo, setBusinessRegNo] = useState("");
  const [managerName, setManagerName] = useState("");
  const [managerPhone, setManagerPhone] = useState("");
  const [pushEnabled, setPushEnabled] = useState(true);
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [emailOptIn, setEmailOptIn] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);

  const isOrganization = caregiver?.relation_type === "organization";

  useEffect(() => {
    if (!verified) return;
    const load = async () => {
      try {
        if (caregiverId) {
          const list = await getCaregivers();
          const me = list.find((c) => c.id === caregiverId) ?? null;
          setCaregiver(me);
          if (me) {
            setName(me.name);
            setBirthDate(me.birth_date ?? "");
            setEmail(me.email ?? "");
            setPhone(me.phone ?? "");
            setOrgName(me.org_name ?? "");
            setOrgType(me.org_type ?? ORG_TYPE_OPTIONS[0]);
            setBusinessRegNo(me.business_reg_no ?? "");
            setManagerName(me.manager_name ?? "");
            setManagerPhone(me.manager_phone ?? "");
            setPushEnabled(me.push_enabled);
            setSmsEnabled(me.sms_enabled);
            setEmailOptIn(me.email_opt_in);
          }
        } else {
          const patients = await getPatients();
          const me = patients.find((p) => p.id === patientId) ?? null;
          setPatient(me);
          if (me) {
            setName(me.name);
            setBirthDate(me.birth_date ?? "");
            setGender(me.gender ?? "");
            setEmail(me.email ?? "");
            setPhone(me.phone ?? "");
            setPushEnabled(me.push_enabled);
            setSmsEnabled(me.sms_enabled);
            setEmailOptIn(me.email_opt_in);
          }
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [verified, caregiverId, patientId]);

  const handleVerify = async () => {
    if (!password) return;
    setVerifying(true);
    setVerifyError("");
    try {
      await verifyPassword(password);
      setVerified(true);
    } catch {
      setVerifyError("비밀번호가 올바르지 않아요.");
    } finally {
      setVerifying(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveError("");
    setSaved(false);
    try {
      if (caregiverId) {
        await updateCaregiver(caregiverId, {
          name: isOrganization ? orgName.trim() : name.trim(),
          // [2026-07-23 수정, 팀원 리뷰 반영] `|| undefined`를 쓰면 axios가 JSON으로
          // 직렬화할 때 이 키 자체를 통째로 빼버려서(undefined는 JSON에 안 실림), 백엔드의
          // model_dump(exclude_unset=True)가 "안 건드림"으로 해석했다 — 필드를 지우고
          // 저장해도 기존 값이 그대로 남는 버그였다. 빈 문자열도 그대로 보내야 실제로 지워진다.
          phone: phone.trim(),
          email: email.trim(),
          birth_date: birthDate.trim(),
          push_enabled: pushEnabled,
          sms_enabled: smsEnabled,
          email_opt_in: emailOptIn,
          ...(isOrganization
            ? {
                org_name: orgName.trim(),
                org_type: orgType,
                business_reg_no: businessRegNo.trim(),
                manager_name: managerName.trim(),
                manager_phone: managerPhone.trim(),
              }
            : {}),
        });
      } else if (patientId != null) {
        await updatePatient(patientId, {
          name: name.trim(),
          phone: phone.trim(),
          email: email.trim(),
          birth_date: birthDate.trim(),
          gender: gender || undefined,
          push_enabled: pushEnabled,
          sms_enabled: smsEnabled,
          email_opt_in: emailOptIn,
        });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSaveError(detail || "저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  };

  if (!verified) {
    return (
      <div className="min-h-screen" style={{ background: C.ivory }}>
        <NavBar isLoggedIn userName={getCurrentUserName()} />
        <main className="max-w-md mx-auto px-6 sm:px-8 py-16">
          <div className="rounded-2xl p-8 text-center" style={{ background: C.surface, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5"
              style={{ background: `${C.terracotta}15` }}
            >
              <Lock className="w-6 h-6" style={{ color: C.terracotta }} />
            </div>
            <h1 className="text-[20px] font-black mb-1.5" style={{ color: C.dark }}>본인 확인이 필요해요</h1>
            <p className="text-[14px] mb-6" style={{ color: C.muted }}>
              내 정보를 보려면 비밀번호를 다시 입력해 주세요.
            </p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleVerify()}
              placeholder="비밀번호"
              className="w-full px-4 py-3.5 rounded-xl border text-[15px] outline-none mb-3 text-center"
              style={inputStyle}
              autoFocus
            />
            {verifyError && <p className="text-[13px] mb-3" style={{ color: "#D94F4F" }}>{verifyError}</p>}
            <button
              onClick={handleVerify}
              disabled={!password || verifying}
              className="w-full py-3.5 rounded-full text-white font-black text-[15px] disabled:opacity-50"
              style={{ background: C.terracotta }}
            >
              {verifying ? "확인 중..." : "확인"}
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-xl mx-auto px-6 sm:px-8 py-10">
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>내 정보</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>회원가입 때 입력한 정보를 확인하고 수정할 수 있어요.</p>

        {loading ? (
          <p className="text-center py-16 text-[14px]" style={{ color: C.muted }}><LoadingDots /></p>
        ) : (
          <div className="rounded-2xl p-6" style={{ background: C.surface, boxShadow: "0 2px 20px rgba(30,26,23,0.07)" }}>
            <div className="space-y-4">
              {isOrganization ? (
                <>
                  <Field label="기관명" value={orgName} onChange={setOrgName} placeholder="예: 행복요양원" />
                  <div>
                    <label className="block text-[13px] font-bold mb-1.5" style={{ color: C.dark }}>기관 유형</label>
                    <select value={orgType} onChange={(e) => setOrgType(e.target.value)} className={inputCss} style={inputStyle}>
                      {ORG_TYPE_OPTIONS.map((t) => <option key={t}>{t}</option>)}
                    </select>
                  </div>
                  <Field label="사업자등록번호" value={businessRegNo} onChange={setBusinessRegNo} placeholder="000-00-00000" />
                  <Field label="담당자 이름" value={managerName} onChange={setManagerName} placeholder="홍길동" />
                  <Field label="담당자 이메일" value={email} onChange={setEmail} placeholder="manager@agency.com" type="email" />
                  <Field label="담당자 전화번호" value={managerPhone} onChange={setManagerPhone} placeholder="010-0000-0000" />
                </>
              ) : (
                <>
                  <Field label="이름" value={name} onChange={setName} placeholder="홍길동" />
                  <Field label="생년월일" value={birthDate} onChange={setBirthDate} placeholder="1945.03.15" />
                  {patient && (
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
                  <Field label="이메일" value={email} onChange={setEmail} placeholder="example@email.com" type="email" />
                  <Field label="전화번호" value={phone} onChange={setPhone} placeholder="010-0000-0000" />
                </>
              )}

              <div className="pt-2">
                <p className="text-[13px] font-bold mb-2" style={{ color: C.dark }}>알림 수신 설정</p>
                <div className="space-y-2">
                  <PrefToggle label="🔔 Push 알림 허용" checked={pushEnabled} onClick={() => setPushEnabled((v) => !v)} />
                  <PrefToggle label="💬 문자(SMS) 수신 허용" checked={smsEnabled} onClick={() => setSmsEnabled((v) => !v)} />
                  <PrefToggle label="📧 이메일 수신 허용" checked={emailOptIn} onClick={() => setEmailOptIn((v) => !v)} />
                </div>
              </div>

              {saveError && <p className="text-[13px]" style={{ color: "#D94F4F" }}>{saveError}</p>}
              {saved && <p className="text-[13px] font-bold" style={{ color: "#4A7A47" }}>저장했어요.</p>}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => navigate("/mypage")}
                  className="flex-1 py-3.5 rounded-full font-bold text-[14px] border-2"
                  style={{ borderColor: "rgba(30,26,23,0.15)", color: C.dark }}
                >
                  뒤로
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 py-3.5 rounded-full font-black text-[14px] text-white disabled:opacity-50"
                  style={{ background: C.terracotta }}
                >
                  {saving ? "저장 중..." : "저장"}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
