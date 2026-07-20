import { useState } from "react";
import { useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { login } from "../api/auth";
import { getCaregiverPatients, type Caregiver, type Patient } from "../api/monitoring";
import { C } from "../theme";

export default function Login() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [selectedCaregiver, setSelectedCaregiver] = useState<Caregiver | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const proceedWithPatient = (caregiverId: number, patient: Patient) => {
    localStorage.setItem("caregiver_id", String(caregiverId));
    localStorage.setItem("patient_id", String(patient.id));
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
        navigate("/dashboard");
        return;
      }

      localStorage.setItem("caregiver_id", String(caregiver_id));
      setSelectedCaregiver({ id: caregiver_id, name } as Caregiver);

      const list = await getCaregiverPatients(caregiver_id);
      if (list.length === 0) {
        // [2026-07-15] 케어하는 환자가 없으면 여기서 막다른 길이었음 — SignUp.tsx의
        // 보호자 가입 직후 흐름과 동일하게 환자 등록 화면으로 바로 보낸다.
        navigate("/patients");
        return;
      } else if (list.length === 1) {
        proceedWithPatient(caregiver_id, list[0]);
        return;
      } else {
        setPatients(list);
      }
    } catch {
      setError("이메일/전화번호 또는 비밀번호가 올바르지 않아요.");
    } finally {
      setLoading(false);
    }
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
                  onClick={() => proceedWithPatient(selectedCaregiver.id, p)}
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
