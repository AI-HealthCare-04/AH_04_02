import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { confirmPasswordReset, requestPasswordReset, verifyPasswordReset } from "../api/auth";
import { C } from "../theme";

type Step = "identifier" | "code" | "password" | "done";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("identifier");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const handleRequestCode = async () => {
    if (!identifier.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { message } = await requestPasswordReset(identifier.trim());
      setNotice(message);
      setStep("code");
    } catch {
      setError("요청에 실패했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { reset_token } = await verifyPasswordReset(identifier.trim(), code.trim());
      setResetToken(reset_token);
      setNotice("");
      setStep("password");
    } catch {
      setError("인증코드가 올바르지 않거나 만료되었어요.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPassword = async () => {
    if (!newPassword || newPassword !== newPasswordConfirm) return;
    setLoading(true);
    setError("");
    try {
      await confirmPasswordReset(resetToken, newPassword);
      setStep("done");
    } catch {
      setError("재설정에 실패했어요. 처음부터 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: C.ivory, fontFamily: "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif" }}
    >
      <NavBar />
      <main className="max-w-[480px] mx-auto px-5 pt-10 pb-16 flex flex-col items-center sm:px-6 sm:pt-[60px] sm:pb-20">
        <div className="text-center mb-8 sm:mb-9">
          <h1 className="text-[26px] sm:text-[32px] font-bold mb-2 tracking-[-0.5px]" style={{ color: C.dark }}>
            비밀번호 찾기
          </h1>
          <p className="text-[15px] sm:text-base" style={{ color: C.muted }}>
            {step === "identifier" && "가입하신 이메일 또는 전화번호를 입력해 주세요"}
            {step === "code" && "가입 이메일로 보낸 6자리 인증코드를 입력해 주세요"}
            {step === "password" && "새 비밀번호를 설정해 주세요"}
            {step === "done" && "비밀번호가 재설정됐어요"}
          </p>
        </div>

        <div
          className="w-full rounded-2xl px-5 py-6 sm:px-6 sm:py-7"
          style={{ background: C.white, boxShadow: "0 2px 16px rgba(0,0,0,0.06)", border: "1px solid rgba(30,26,23,0.12)" }}
        >
          {step === "identifier" && (
            <form
              className="flex flex-col gap-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                handleRequestCode();
              }}
            >
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="이메일 또는 전화번호"
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none box-border"
                style={{ color: C.dark, background: C.ivory, border: "1.5px solid rgba(30,26,23,0.12)" }}
                autoComplete="username"
              />
              {error && <p className="text-[13px] py-1" style={{ color: C.danger }}>{error}</p>}
              <button
                type="submit"
                disabled={loading || !identifier.trim()}
                className="w-full py-3.5 text-[15px] font-bold rounded-[10px] border-none cursor-pointer"
                style={{ color: C.white, background: C.terracotta }}
              >
                {loading ? "요청 중..." : "인증코드 받기"}
              </button>
            </form>
          )}

          {step === "code" && (
            <form
              className="flex flex-col gap-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                handleVerifyCode();
              }}
            >
              {notice && <p className="text-[13px] py-1 leading-normal" style={{ color: C.muted }}>{notice}</p>}
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6자리 인증코드"
                maxLength={6}
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none box-border"
                style={{ color: C.dark, background: C.ivory, border: "1.5px solid rgba(30,26,23,0.12)" }}
                autoComplete="one-time-code"
              />
              {error && <p className="text-[13px] py-1" style={{ color: C.danger }}>{error}</p>}
              <button
                type="submit"
                disabled={loading || !code.trim()}
                className="w-full py-3.5 text-[15px] font-bold rounded-[10px] border-none cursor-pointer"
                style={{ color: C.white, background: C.terracotta }}
              >
                {loading ? "확인 중..." : "확인"}
              </button>
              <button
                type="button"
                className="mt-1 p-2 text-[13px] bg-transparent border-none cursor-pointer underline"
                style={{ color: C.muted }}
                onClick={() => {
                  setStep("identifier");
                  setCode("");
                  setError("");
                }}
              >
                이메일/전화번호 다시 입력
              </button>
            </form>
          )}

          {step === "password" && (
            <form
              className="flex flex-col gap-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                handleConfirmPassword();
              }}
            >
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="새 비밀번호"
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none box-border"
                style={{ color: C.dark, background: C.ivory, border: "1.5px solid rgba(30,26,23,0.12)" }}
                autoComplete="new-password"
              />
              <input
                type="password"
                value={newPasswordConfirm}
                onChange={(e) => setNewPasswordConfirm(e.target.value)}
                placeholder="새 비밀번호 확인"
                className="w-full px-4 py-3.5 text-[15px] rounded-[10px] outline-none box-border"
                style={{ color: C.dark, background: C.ivory, border: "1.5px solid rgba(30,26,23,0.12)" }}
                autoComplete="new-password"
              />
              {newPassword && newPasswordConfirm && newPassword !== newPasswordConfirm && (
                <p className="text-[13px] py-1" style={{ color: C.danger }}>비밀번호가 일치하지 않아요.</p>
              )}
              {error && <p className="text-[13px] py-1" style={{ color: C.danger }}>{error}</p>}
              <button
                type="submit"
                disabled={loading || !newPassword || newPassword !== newPasswordConfirm}
                className="w-full py-3.5 text-[15px] font-bold rounded-[10px] border-none cursor-pointer"
                style={{ color: C.white, background: C.terracotta }}
              >
                {loading ? "저장 중..." : "비밀번호 재설정"}
              </button>
            </form>
          )}

          {step === "done" && (
            <div className="flex flex-col gap-2.5">
              <p className="text-[14px] text-center mb-2" style={{ color: C.muted }}>새 비밀번호로 로그인해 주세요.</p>
              <button
                className="w-full py-3.5 text-[15px] font-bold rounded-[10px] border-none cursor-pointer"
                style={{ color: C.white, background: C.terracotta }}
                onClick={() => navigate("/login")}
              >
                로그인하러 가기
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
