import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";
import NavBar from "../components/NavBar";
import { login } from "../api/auth";
import { getCaregiverPatients, type Caregiver, type Patient } from "../api/monitoring";
import {
  clearRememberedIdentifier,
  getRecentAccounts,
  getRememberedIdentifier,
  removeRecentAccount,
  saveRecentAccount,
  setRememberedIdentifier,
  switchToRecentAccount,
  type RecentAccount,
} from "../lib/session";
import { C } from "../theme";

export default function Login() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState(getRememberedIdentifier);
  const [password, setPassword] = useState("");
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // [2026-07-21 추가] "다른 사용자로 전환" — 이 기기에서 로그인했던 계정 목록
  const [recentAccounts, setRecentAccounts] = useState<RecentAccount[]>(getRecentAccounts());
  // 보호자가 케어하는 환자가 여럿이라 선택 화면을 거칠 때, 그 사이에 로그인 응답의
  // access_token을 들고 있다가 환자를 고른 시점에 saveRecentAccount에 같이 넘긴다.
  const [pendingAccessToken, setPendingAccessToken] = useState("");
  // [2026-07-21 추가] 아이디 저장(이메일/전화번호만 미리 채움) vs 자동 로그인(비밀번호 없이
  // 바로 전환되는 계정 목록에 추가) — 이미 저장된 아이디가 있으면 체크박스도 켜서 보여준다.
  const [rememberId, setRememberId] = useState(() => getRememberedIdentifier() !== "");
  const [autoLogin, setAutoLogin] = useState(false);

  // [2026-07-22 추가] monitoringClient.ts의 401 인터셉터가 남겨둔 안내 메시지 — 저장된
  // 계정을 클릭했는데 토큰이 만료돼 있으면 여기로 튕겨오면서 이 메시지가 뜬다("눌러도
  // 반응 없음"처럼 보이던 문제 수정). useState 초기화 함수 안에서 읽고 지우면 StrictMode가
  // 개발 모드에서 그 함수를 두 번 호출해 두 번째 호출 때는 이미 지워진 뒤라 메시지가
  // 조용히 사라지는 문제가 있어 — 실제로 한 번만 도는 useEffect로 옮겼다.
  useEffect(() => {
    const notice = sessionStorage.getItem("login_notice");
    if (notice) {
      sessionStorage.removeItem("login_notice");
      setError(notice);
    }
  }, []);

  // 로그인 성공 직후 공통 처리 — 체크박스 상태에 따라 아이디/계정을 기억하거나 지운다.
  const persistLoginChoice = (account: RecentAccount) => {
    if (rememberId) setRememberedIdentifier(account.identifier);
    else clearRememberedIdentifier();

    // [사용자 요청] "자동로그인에 체크하는 계정만 저장되게" — 체크 안 하면 계정 전환
    // 목록에도 안 남아야 하므로, 이전에 체크해서 저장돼있었더라도 지금 체크를 껐으면 제거한다.
    if (autoLogin) saveRecentAccount(account);
    else removeRecentAccount(account.identifier);
    setRecentAccounts(getRecentAccounts());
  };

  const proceedWithPatient = (caregiverId: number, patient: Patient, name: string, accessToken: string) => {
    localStorage.setItem("caregiver_id", String(caregiverId));
    localStorage.setItem("patient_id", String(patient.id));
    persistLoginChoice({ identifier: identifier.trim(), name, accessToken, patientId: patient.id, caregiverId });
    navigate("/dashboard");
  };

  const handleLogin = async () => {
    if (!identifier.trim() || !password) return;
    setError("");
    setLoading(true);
    try {
      const { access_token, caregiver_id, name, role } = await login(identifier.trim(), password);
      localStorage.setItem("access_token", access_token);
      // [2026-07-19 추가] NavBar가 화면마다 "김건강"으로 하드코딩돼있던 문제 수정 —
      // 로그인 시점에 실제 이름을 저장해서 NavBar가 이걸 쓰게 한다.
      localStorage.setItem("user_name", name);

      // 환자 본인 로그인은 "케어하는 환자 목록"이 없어서 보호자 흐름을 못 탄다 —
      // 자기 자신을 바로 대시보드로 보낸다 (SignUp.tsx의 환자 본인 가입 흐름과 동일).
      if (role === "patient") {
        localStorage.setItem("patient_id", String(caregiver_id));
        localStorage.removeItem("caregiver_id");
        persistLoginChoice({ identifier: identifier.trim(), name, accessToken: access_token, patientId: caregiver_id });
        navigate("/dashboard");
        return;
      }

      localStorage.setItem("caregiver_id", String(caregiver_id));
      setSelectedCaregiver({ id: caregiver_id, name } as Caregiver);

      const list = await getCaregiverPatients(caregiver_id);
      if (list.length === 0) {
        // [2026-07-15] 케어하는 환자가 없으면 여기서 막다른 길이었음 — SignUp.tsx의
        // 보호자 가입 직후 흐름과 동일하게 환자 등록 화면으로 바로 보낸다.
        // [2026-07-22 수정] 이 분기가 persistLoginChoice를 안 거치고 바로 return해버려서
        // "자동 로그인 체크했는데 계정 목록에 안 뜬다" 버그의 원인이었다 — 환자가 아직
        // 없어도 로그인 자체는 성공이니 체크박스 선택은 그대로 반영해야 한다.
        persistLoginChoice({ identifier: identifier.trim(), name, accessToken: access_token, caregiverId: caregiver_id });
        navigate("/patients");
        return;
      } else if (list.length === 1) {
        proceedWithPatient(caregiver_id, list[0], name, access_token);
        return;
      } else {
        setPendingAccessToken(access_token);
        setPatients(list);
      }
    } catch {
      setError("이메일/전화번호 또는 비밀번호가 올바르지 않아요.");
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchAccount = (account: RecentAccount) => {
    switchToRecentAccount(account);
    // [2026-07-22 수정] 케어하는 환자가 없던 보호자 계정은 patientId가 없다 — 그대로
    // /dashboard로 보내면 엉뚱한 환자로 진입하니, 환자 등록 화면으로 보낸다.
    navigate(account.patientId ? "/dashboard" : "/patients");
  };

  const handleRemoveRecent = (e: MouseEvent, identifierToRemove: string) => {
    e.stopPropagation();
    removeRecentAccount(identifierToRemove);
    setRecentAccounts(getRecentAccounts());
  };

  const handleBack = () => {
    setSelectedCaregiver(null);
    setPatients([]);
    setError("");
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}
    >
      <NavBar />

      <main className="max-w-[480px] mx-auto flex flex-col items-center px-5 pt-10 pb-16 sm:px-6 sm:pt-[60px] sm:pb-20">
        <div className="text-center mb-7 sm:mb-9">
          <h1 className="text-[26px] sm:text-[32px] font-bold mb-2 tracking-[-0.5px]" style={{ color: C.dark }}>
            안녕하세요
          </h1>
          <p className="text-[15px] sm:text-base" style={{ color: C.muted }}>
            {patients.length > 0 ? "케어하실 환자를 선택해 주세요" : "이메일(또는 전화번호)과 비밀번호를 입력해 주세요"}
          </p>
        </div>

        {/* [2026-07-21 추가] "다른 사용자로 전환"(MyPage.tsx)에서 온 경우 이 기기에 로그인했던
            계정을 눌러서 바로 전환할 수 있게 — 네이버 등의 계정 전환과 동일한 패턴. */}
        {!selectedCaregiver && recentAccounts.length > 0 && (
          <div className="w-full mb-4">
            <p className="text-[12px] font-bold mb-2 px-1" style={{ color: C.muted }}>이 기기에 로그인했던 계정</p>
            <div className="flex flex-col gap-2">
              {recentAccounts.map((account) => (
                <button
                  key={account.identifier}
                  onClick={() => handleSwitchAccount(account)}
                  className="flex items-center gap-3 w-full px-4 py-3 rounded-[10px] border-[1.5px] text-left"
                  style={{ background: C.white, borderColor: "rgba(30,26,23,0.12)" }}
                >
                  <div
                    className="w-9 h-9 rounded-full flex items-center justify-center text-white text-[15px] font-bold shrink-0"
                    style={{ background: C.terracotta }}
                  >
                    {account.name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[14px] font-bold truncate" style={{ color: C.dark }}>{account.name}</p>
                    <p className="text-[12px] truncate" style={{ color: C.muted }}>{account.identifier}</p>
                  </div>
                  <span
                    onClick={(e) => handleRemoveRecent(e, account.identifier)}
                    className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 hover:opacity-70"
                    style={{ background: "rgba(30,26,23,0.06)" }}
                    aria-label={`${account.name} 계정 목록에서 제거`}
                  >
                    <X className="w-3.5 h-3.5" style={{ color: C.muted }} />
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div
          className="w-full rounded-2xl px-5 py-6 sm:px-6 sm:py-7"
          style={{ background: C.white, boxShadow: "0 2px 16px rgba(0,0,0,0.06)", border: "1px solid rgba(30,26,23,0.12)" }}
        >
          {!selectedCaregiver && (
            <form
              className="flex flex-col gap-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                handleLogin();
              }}
            >
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="이메일 또는 전화번호"
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none border-[1.5px] box-border"
                style={{ color: C.dark, background: C.ivory, borderColor: "rgba(30,26,23,0.12)" }}
                autoComplete="username"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호"
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none border-[1.5px] box-border"
                style={{ color: C.dark, background: C.ivory, borderColor: "rgba(30,26,23,0.12)" }}
                autoComplete="current-password"
              />

              <div className="flex items-center gap-4 px-1">
                <label className="flex items-center gap-1.5 text-[13px] cursor-pointer" style={{ color: C.muted }}>
                  <input
                    type="checkbox"
                    checked={rememberId}
                    onChange={(e) => setRememberId(e.target.checked)}
                    className="w-4 h-4 accent-current"
                    style={{ color: C.terracotta }}
                  />
                  아이디 저장
                </label>
                <label className="flex items-center gap-1.5 text-[13px] cursor-pointer" style={{ color: C.muted }}>
                  <input
                    type="checkbox"
                    checked={autoLogin}
                    onChange={(e) => setAutoLogin(e.target.checked)}
                    className="w-4 h-4 accent-current"
                    style={{ color: C.terracotta }}
                  />
                  이 기기에서 자동 로그인
                </label>
              </div>

              {error && <p className="text-[14px] text-center py-3" style={{ color: C.danger }}>{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 text-[15px] font-bold rounded-[10px] cursor-pointer border-none"
                style={{ color: C.white, background: C.terracotta }}
              >
                {loading ? "로그인 중..." : "로그인"}
              </button>
              <button
                type="button"
                onClick={() => navigate("/reset-password")}
                className="mt-1 p-2.5 text-[13px] bg-transparent border-none cursor-pointer text-center self-center"
                style={{ color: C.muted }}
              >
                비밀번호를 잊으셨나요?
              </button>
            </form>
          )}

          {selectedCaregiver && (
            <div className="flex flex-col gap-2.5">
              {error && <p className="text-[14px] text-center py-3" style={{ color: C.danger }}>{error}</p>}
              {patients.map((p) => (
                <button
                  key={p.id}
                  className="flex justify-between items-center w-full px-[18px] py-4 text-[15px] font-semibold rounded-[10px] cursor-pointer text-left border-[1.5px]"
                  style={{ color: C.dark, background: C.ivory, borderColor: "rgba(30,26,23,0.12)" }}
                  onClick={() => proceedWithPatient(selectedCaregiver.id, p, selectedCaregiver.name, pendingAccessToken)}
                >
                  <span className="text-[15px] font-bold" style={{ color: C.dark }}>{p.name}</span>
                  {p.note && (
                    <span className="text-[12px] font-semibold rounded-xl px-2.5 py-1" style={{ color: C.terracotta, background: C.bubbleBg }}>
                      {p.note}
                    </span>
                  )}
                </button>
              ))}
              <button
                className="mt-1 p-2.5 text-[13px] bg-transparent border-none cursor-pointer text-left"
                style={{ color: C.muted }}
                onClick={handleBack}
              >
                ← 다시 로그인
              </button>
            </div>
          )}
        </div>

        <p className="mt-3 text-[13px] text-center" style={{ color: C.muted }}>
          처음이신가요?{" "}
          <button
            onClick={() => navigate("/register")}
            className="font-bold bg-transparent border-none cursor-pointer underline"
            style={{ color: C.terracotta }}
          >
            회원가입
          </button>
        </p>
      </main>
    </div>
  );
}
