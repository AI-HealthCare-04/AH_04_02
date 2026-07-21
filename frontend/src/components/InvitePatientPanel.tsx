import { useState } from "react";
import { Phone } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { createInvitation } from "../api/care";

/**
 * 문자 앱(sms:)으로 초대 링크를 보내기 위한 href를 만든다.
 * [한계] iOS/Android가 본문 구분자를 다르게 처리(iOS는 '&body=', Android는 '?body=')하는
 * 이슈가 있으나 실기기 테스트가 불가해 표준 '?body='로 통일한다.
 */
export function buildSmsHref(phone: string, body: string): string {
  const target = phone.trim();
  return `sms:${target}?body=${encodeURIComponent(body)}`;
}

type InviteMethod = "sms" | "url" | "qr";

/**
 * 보호자가 "아직 계정이 없는 환자"를 초대(연결)하는 패널.
 * relation_type을 "patient"로 고정하고 patient_id 없이 inviter_caregiver_id만 실어서
 * 초대를 만든다. 만들어진 링크는 문자·URL·실제 QR 세 방식으로 전달할 수 있다.
 */
export default function InvitePatientPanel({
  caregiverId,
  onCreated,
}: {
  caregiverId: number;
  onCreated?: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [method, setMethod] = useState<InviteMethod>("url");
  const [inviteUrl, setInviteUrl] = useState("");
  const [urlCopied, setUrlCopied] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const handleInvite = async () => {
    setSending(true);
    setError("");
    try {
      const created = await createInvitation({
        relation_type: "patient",
        inviter_caregiver_id: caregiverId,
        invited_phone: phone || undefined,
      });
      setInviteUrl(window.location.origin + created.invite_url);
      onCreated?.();
    } catch {
      setError("초대를 만들지 못했어요.");
    } finally {
      setSending(false);
    }
  };

  const copyUrl = () => {
    navigator.clipboard?.writeText(inviteUrl);
    setUrlCopied(true);
    setTimeout(() => setUrlCopied(false), 2000);
  };

  return (
    <div className="bg-white border border-[rgba(30,26,23,0.12)] rounded-2xl p-6">
      <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">환자 연결하기</h2>
      <p className="text-[13px] text-[#8A7E75] mb-4">
        환자에게 초대 링크를 보내면, 환자가 직접 계정을 만들어 연결돼요.
      </p>

      {error && <p className="text-[13px] text-[#D94F4F] mb-3">{error}</p>}

      <div className="flex gap-2 mb-4 p-1 rounded-xl bg-[#F4F0EA]">
        {[
          { key: "sms" as const, label: "💬 문자" },
          { key: "url" as const, label: "🔗 URL" },
          { key: "qr" as const, label: "📷 QR" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setMethod(key)}
            className={`flex-1 py-2.5 rounded-lg text-[13px] font-bold transition-all ${
              method === key ? "bg-white text-[#1E1A17] shadow-sm" : "text-[#8A7E75]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {method === "sms" && (
        <div className="space-y-3">
          <div className="relative">
            <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8A7E75]" />
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="환자 전화번호 (010-0000-0000)"
              className="w-full pl-11 pr-4 py-3.5 rounded-xl border border-[rgba(30,26,23,0.12)] bg-[#FAF6F1] text-[15px] outline-none"
            />
          </div>
          {!inviteUrl ? (
            <button
              onClick={handleInvite}
              disabled={sending}
              className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
            >
              {sending ? "생성 중..." : "초대 만들기"}
            </button>
          ) : (
            <>
              <div className="rounded-xl px-4 py-3 bg-[#FAF6F1] border border-[rgba(30,26,23,0.08)]">
                <p className="text-[12px] font-bold text-[#8A7E75] mb-1">생성된 초대 링크</p>
                <p className="text-[13px] break-all text-[#1E1A17]">{inviteUrl}</p>
              </div>
              <a
                href={buildSmsHref(phone, inviteUrl)}
                className={`block w-full py-3.5 rounded-full text-center text-white font-bold text-[16px] bg-[#C1653D] ${
                  phone.trim() ? "" : "opacity-60 pointer-events-none"
                }`}
              >
                문자 앱으로 보내기
              </a>
            </>
          )}
        </div>
      )}

      {method === "url" && (
        <div className="space-y-3">
          <p className="text-[13px] text-[#8A7E75]">초대 링크를 만들고 복사해서 전달하세요.</p>
          {!inviteUrl ? (
            <button
              onClick={handleInvite}
              disabled={sending}
              className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
            >
              {sending ? "생성 중..." : "초대 링크 만들기"}
            </button>
          ) : (
            <div className="flex items-center gap-2 px-4 py-3.5 rounded-xl bg-[#FAF6F1] border border-[rgba(30,26,23,0.10)]">
              <span className="flex-1 text-[13px] font-mono truncate text-[#1E1A17]">{inviteUrl}</span>
              <button
                onClick={copyUrl}
                className={`shrink-0 px-4 py-2 rounded-full text-[13px] font-bold ${
                  urlCopied ? "bg-[#8FAE8B]/20 text-[#4A7A47]" : "bg-[#C1653D]/15 text-[#C1653D]"
                }`}
              >
                {urlCopied ? "복사됨 ✓" : "복사"}
              </button>
            </div>
          )}
        </div>
      )}

      {method === "qr" && (
        <div className="flex flex-col items-center py-4 gap-4">
          {!inviteUrl ? (
            <button
              onClick={handleInvite}
              disabled={sending}
              className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
            >
              {sending ? "생성 중..." : "QR용 초대 만들기"}
            </button>
          ) : (
            <>
              <p className="text-[13px] text-center text-[#8A7E75]">
                환자가 이 QR을 스캔하면 초대 링크로 이동해요.
              </p>
              <div className="p-4 rounded-2xl bg-white border-2 border-[rgba(30,26,23,0.08)]">
                <QRCodeSVG value={inviteUrl} size={160} />
              </div>
              <p className="text-[12px] font-mono break-all text-center text-[#1E1A17]">{inviteUrl}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
