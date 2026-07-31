import { useState } from "react";
import { Link2, MessageSquare, Phone, QrCode, RotateCw } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { createInvitation, deleteInvitation } from "../api/care";
import { copyTextToClipboard } from "../lib/clipboard";
import InfoModal from "./InfoModal";

/** [2026-07-30 추가] Connect.tsx의 describeError와 동일한 패턴 — 백엔드가 내려준 구체적인
 * 사유(예: "이미 연결된 사용자입니다.")를 뭉개지 않고 그대로 보여준다. */
function describeError(e: unknown, fallback: string): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

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
  const [inviteId, setInviteId] = useState<number | null>(null);
  const [inviteUrl, setInviteUrl] = useState("");
  const [urlCopied, setUrlCopied] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  // [2026-07-30 추가] 이미 연결된 환자를 다시 초대하면(409) 인라인 에러 문구로는 놓치기
  // 쉬워서 팝업으로 확실히 알려준다.
  const [alreadyConnectedMessage, setAlreadyConnectedMessage] = useState("");

  const handleInvite = async () => {
    setSending(true);
    setError("");
    try {
      const created = await createInvitation({
        relation_type: "patient",
        inviter_caregiver_id: caregiverId,
        invited_phone: phone || undefined,
      });
      setInviteId(created.id);
      setInviteUrl(window.location.origin + created.invite_url);
      onCreated?.();
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setAlreadyConnectedMessage(describeError(e, "이미 연결된 사용자입니다."));
      } else {
        setError("초대를 만들지 못했어요.");
      }
    } finally {
      setSending(false);
    }
  };

  // [2026-07-24 추가] 기존 초대 링크를 무효화하고 새 코드를 발급한다 — 링크가 유출됐거나
  // 오래돼서 새로 받고 싶을 때 쓴다.
  const handleRegenerate = async () => {
    if (sending) return;
    setSending(true);
    setError("");
    try {
      if (inviteId != null) {
        await deleteInvitation(inviteId);
        // [2026-07-24 추가] delete는 성공했는데 바로 아래 create가 실패하면, inviteId가
        // 이미 cancelled된 옛 초대를 계속 가리켜서 다음 재발급 시도가 "이미 cancelled
        // 처리된 초대예요"(409)로 영원히 막힌다 — delete 성공 즉시 비워서 깨끗한 상태로
        // 만든다.
        setInviteId(null);
        setInviteUrl("");
      }
      const created = await createInvitation({
        relation_type: "patient",
        inviter_caregiver_id: caregiverId,
        invited_phone: phone || undefined,
      });
      setInviteId(created.id);
      setInviteUrl(window.location.origin + created.invite_url);
      setUrlCopied(false);
      onCreated?.();
    } catch (e) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setAlreadyConnectedMessage(describeError(e, "이미 연결된 사용자입니다."));
      } else {
        setError("초대를 다시 만들지 못했어요.");
      }
    } finally {
      setSending(false);
    }
  };

  const copyUrl = async () => {
    const copied = await copyTextToClipboard(inviteUrl);
    if (!copied) {
      setError("초대 링크를 복사하지 못했어요. 링크를 길게 눌러 직접 복사해 주세요.");
      return;
    }
    setError("");
    setUrlCopied(true);
    setTimeout(() => setUrlCopied(false), 2000);
  };

  return (
    <div className="bg-[#F9F4EB] border border-[rgba(30,26,23,0.12)] rounded-2xl p-6">
      <h2 className="text-[16px] font-black text-[#1E1A17] mb-1">환자 연결하기</h2>
      <p className="text-[13px] text-[#6E6259] mb-4">
        환자에게 초대 링크를 보내면, 환자가 직접 계정을 만들어 연결돼요.
      </p>

      {error && <p className="text-[13px] text-[#D94F4F] mb-3">{error}</p>}

      <div className="flex gap-2 mb-4 p-1 rounded-xl bg-[#F4F0EA]">
        {[
          { key: "sms" as const, icon: MessageSquare, label: "문자" },
          { key: "url" as const, icon: Link2, label: "URL" },
          { key: "qr" as const, icon: QrCode, label: "QR" },
        ].map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            onClick={() => setMethod(key)}
            className={`flex-1 py-2.5 rounded-lg text-[13px] font-bold transition-all flex items-center justify-center gap-1.5 ${
              method === key ? "bg-white text-[#1E1A17] shadow-sm" : "text-[#6E6259]"
            }`}
          >
            <Icon className="w-3.5 h-3.5" strokeWidth={2.2} /> {label}
          </button>
        ))}
      </div>

      {method === "sms" && (
        <div className="space-y-3">
          <div className="relative">
            <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6E6259]" />
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="환자 전화번호 (010-0000-0000)"
              className="w-full pl-11 pr-4 py-3.5 rounded-xl border border-[rgba(30,26,23,0.12)] bg-[#F2E8D8] text-[15px] outline-none"
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
              <div className="rounded-xl px-4 py-3 bg-[#F2E8D8] border border-[rgba(30,26,23,0.08)]">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-bold text-[#6E6259]">생성된 초대 링크</p>
                  <button
                    onClick={handleRegenerate}
                    disabled={sending}
                    className="flex items-center gap-1 text-[11px] font-bold text-[#C1653D] disabled:opacity-50"
                  >
                    <RotateCw className="w-3 h-3" /> 재발급
                  </button>
                </div>
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
          <p className="text-[13px] text-[#6E6259]">초대 링크를 만들고 복사해서 전달하세요.</p>
          {!inviteUrl ? (
            <button
              onClick={handleInvite}
              disabled={sending}
              className="w-full py-3.5 rounded-full text-white font-bold text-[16px] bg-[#C1653D] disabled:opacity-60"
            >
              {sending ? "생성 중..." : "초대 링크 만들기"}
            </button>
          ) : (
            <div className="flex items-center gap-2 px-4 py-3.5 rounded-xl bg-[#F2E8D8] border border-[rgba(30,26,23,0.10)]">
              <span className="flex-1 text-[13px] font-mono truncate text-[#1E1A17]">{inviteUrl}</span>
              <button
                onClick={handleRegenerate}
                disabled={sending}
                aria-label="초대 링크 재발급"
                className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-[#C1653D]/15 text-[#C1653D] disabled:opacity-50"
              >
                <RotateCw className="w-4 h-4" />
              </button>
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
              <p className="text-[13px] text-center text-[#6E6259]">
                환자가 이 QR을 스캔하면 초대 링크로 이동해요.
              </p>
              <div className="p-4 rounded-2xl bg-[#F9F4EB] border-2 border-[rgba(30,26,23,0.08)]">
                <QRCodeSVG value={inviteUrl} size={160} />
              </div>
              <p className="text-[12px] font-mono break-all text-center text-[#1E1A17]">{inviteUrl}</p>
              <button
                onClick={handleRegenerate}
                disabled={sending}
                className="flex items-center gap-1.5 text-[13px] font-bold text-[#C1653D] disabled:opacity-50"
              >
                <RotateCw className="w-3.5 h-3.5" /> 재발급
              </button>
            </>
          )}
        </div>
      )}

      <InfoModal
        open={!!alreadyConnectedMessage}
        message={alreadyConnectedMessage}
        onClose={() => setAlreadyConnectedMessage("")}
      />
    </div>
  );
}
