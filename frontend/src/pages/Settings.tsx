import { useEffect, useState } from "react";
import NavBar from "../components/NavBar";
import PatientContextBanner from "../components/PatientContextBanner";
import { getNotificationSettings, updateNotificationSettings, type NotificationSettings } from "../api/care";
import { applyFontScale, getCurrentUserName, getFontScale, type FontScale, useGuardedPatientId } from "../lib/session";

const DEFAULT_CHATBOT_NAME = "약콩이";

const FONT_SCALE_OPTIONS: { value: FontScale; label: string }[] = [
  { value: "small", label: "작게" },
  { value: "medium", label: "보통" },
  { value: "large", label: "크게" },
];

export default function Settings() {
  // [2026-07-23 수정] 글자 크기는 환자와 무관한 설정이라, 케어하는 환자가 아직 없거나
  // 여러 명 중 하나를 고르지 않은 지원인력/보호자도 이 화면 자체는 볼 수 있어야 한다 —
  // silent: true로 강제 이동을 끄고, 챗봇 이름 카드만 환자가 정해졌을 때 보여준다.
  const patientId = useGuardedPatientId({ silent: true });
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [chatbotName, setChatbotName] = useState("");
  const [fontScale, setFontScale] = useState<FontScale>(() => getFontScale());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (patientId == null) {
      setLoading(false);
      return;
    }
    getNotificationSettings(patientId)
      .then((s) => {
        setSettings(s);
        setChatbotName(s.chatbot_name || DEFAULT_CHATBOT_NAME);
      })
      .catch(() => setError("설정을 불러오지 못했어요."))
      .finally(() => setLoading(false));
  }, [patientId]);

  const saveChatbotName = async () => {
    if (!settings || patientId == null) return;
    const name = chatbotName.trim() || DEFAULT_CHATBOT_NAME;
    setChatbotName(name);
    setSaving(true);
    try {
      await updateNotificationSettings(patientId, { chatbot_name: name });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("저장하지 못했어요.");
    } finally {
      setSaving(false);
    }
  };

  const changeFontScale = (scale: FontScale) => {
    setFontScale(scale);
    applyFontScale(scale);
  };

  return (
    <div className="min-h-screen bg-[#F2E8D8]">
      <NavBar isLoggedIn userName={getCurrentUserName()} />
      <main className="max-w-xl mx-auto px-6 sm:px-8 py-10">
        <PatientContextBanner />
        <h1 className="text-[26px] font-black text-[#1E1A17] mb-1">화면·챗봇 설정</h1>
        <p className="text-[14px] text-[#8A7E75] mb-7">챗봇 이름과 글자 크기를 원하는 대로 바꿀 수 있어요.</p>

        {loading && <p className="text-[14px] text-[#8A7E75]">불러오는 중이에요...</p>}
        {error && <p className="text-[13px] text-[#D94F4F] mb-4">{error}</p>}

        {settings && (
          <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6 mb-6">
            <p className="text-[16px] font-bold text-[#1E1A17] mb-1">챗봇 이름</p>
            <p className="text-[14px] text-[#8A7E75] mb-4">기본값은 "{DEFAULT_CHATBOT_NAME}"예요. 원하는 이름으로 바꿔보세요.</p>
            <div className="flex gap-2">
              <input
                value={chatbotName}
                onChange={(e) => setChatbotName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && saveChatbotName()}
                placeholder={DEFAULT_CHATBOT_NAME}
                maxLength={20}
                className="flex-1 px-4 py-3 rounded-xl text-[15px] outline-none border border-[rgba(30,26,23,0.15)] text-[#1E1A17]"
              />
              <button
                onClick={saveChatbotName}
                disabled={saving}
                className="px-5 py-3 rounded-xl text-white font-bold text-[14px] shrink-0 bg-[#C1653D] hover:opacity-88 transition-all disabled:opacity-60"
              >
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
            {saved && <p className="text-[12px] font-semibold text-[#4A7A47] mt-2">✓ 저장됐어요</p>}
          </div>
        )}

        <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6">
          <p className="text-[16px] font-bold text-[#1E1A17] mb-1">글자 크기</p>
          <p className="text-[14px] text-[#8A7E75] mb-4">화면 전체의 글자와 여백 크기가 함께 조절돼요.</p>
          <div className="flex gap-2">
            {FONT_SCALE_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => changeFontScale(value)}
                className="flex-1 py-3 rounded-xl font-bold text-[15px] border transition-all"
                style={
                  fontScale === value
                    ? { background: "#C1653D", color: "#FFFFFF", borderColor: "#C1653D" }
                    : { background: "#FFFFFF", color: "#1E1A17", borderColor: "rgba(30,26,23,0.15)" }
                }
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
