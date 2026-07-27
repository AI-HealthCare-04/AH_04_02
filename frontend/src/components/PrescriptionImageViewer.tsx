import { useEffect, useRef, useState, type MouseEvent, type PointerEvent, type WheelEvent } from "react";
import { Camera, X, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { getRecordImageBlobUrl } from "../api/records";
import { C } from "../theme";

const MIN_SCALE = 1;
const MAX_SCALE = 4;

// [2026-07-25 추가] 확대/축소/이동 — 휠로 확대·축소, 확대된 상태에서 드래그로 이동.
// scale이 1로 돌아오면 이동값도 같이 리셋(안 그러면 다시 확대했을 때 사진이 화면 밖에
// 가 있는 것처럼 보임).
function ZoomableImage({ url }: { url: string }) {
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  const zoomBy = (delta: number) => {
    setScale((prev) => {
      const next = clampScale(prev + delta);
      if (next === MIN_SCALE) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  const handleWheel = (e: WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 0.3 : -0.3);
  };

  const handlePointerDown = (e: PointerEvent<HTMLImageElement>) => {
    if (scale === MIN_SCALE) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };

  const handlePointerMove = (e: PointerEvent<HTMLImageElement>) => {
    if (!dragRef.current) return;
    const d = dragRef.current;
    setPan({ x: d.panX + (e.clientX - d.x), y: d.panY + (e.clientY - d.y) });
  };

  const handlePointerUp = () => {
    dragRef.current = null;
  };

  const reset = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="flex flex-col h-full">
      <div
        className="relative flex-1 overflow-hidden rounded-xl"
        style={{ background: "rgba(30,26,23,0.03)", touchAction: "none" }}
        onWheel={handleWheel}
      >
        <img
          src={url}
          alt="처방전 원본"
          draggable={false}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className="w-full h-full object-contain select-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            cursor: scale > MIN_SCALE ? "grab" : "default",
            transition: dragRef.current ? "none" : "transform 0.15s ease-out",
          }}
        />
      </div>
      <div className="flex items-center justify-center gap-2 pt-3">
        <button
          onClick={() => zoomBy(-0.3)}
          disabled={scale === MIN_SCALE}
          aria-label="축소"
          className="w-9 h-9 rounded-full flex items-center justify-center disabled:opacity-40"
          style={{ background: `${C.terracotta}15`, color: C.terracotta }}
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-[12px] font-bold w-12 text-center tabular-nums" style={{ color: C.muted }}>
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={() => zoomBy(0.3)}
          disabled={scale === MAX_SCALE}
          aria-label="확대"
          className="w-9 h-9 rounded-full flex items-center justify-center disabled:opacity-40"
          style={{ background: `${C.terracotta}15`, color: C.terracotta }}
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={reset}
          disabled={scale === MIN_SCALE && pan.x === 0 && pan.y === 0}
          aria-label="원래 크기로"
          className="w-9 h-9 rounded-full flex items-center justify-center disabled:opacity-40"
          style={{ background: "rgba(30,26,23,0.06)", color: C.dark }}
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// [2026-07-25 추가] 처방전 원본 사진 팝업 — record_id로만 불러오므로 이 처방전에 연결된
// 사진만 열람된다(다른 기록의 사진이 섞일 수 없음). floating=true면 PrescriptionReview.tsx의
// 수정 화면에서 "챗봇처럼" 열었다 닫았다 할 수 있는 작은 패널로, 아니면 목록·상세 화면의
// 일반 버튼+화면을 거의 채우는 모달로 동작한다. 둘 다 휠로 확대·축소, 드래그로 이동 가능.
export default function PrescriptionImageViewer({
  recordId,
  floating = false,
}: {
  recordId: number;
  floating?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // [2026-07-27 버그수정] 전체화면 모달(floating=false)이 열려 있는 동안 뒤 페이지의
  // 스크롤을 잠그지 않고 있었다 — 사진 영역 밖(반투명 배경)에서 휠을 스크롤하면 화면에
  // 보이지 않는 뒤 페이지가 스크롤되면서 스크롤바가 나타났다 사라졌다 해 레이아웃이 흔들리고
  // (화면이 커졌다 작아졌다 하는 것처럼 보임), 그 와중에 닫기(X) 버튼의 실제 화면 위치도
  // 같이 흔들려 클릭이 빗나갔다. NavBar.tsx의 모바일 드로어와 동일한 패턴으로 잠근다.
  useEffect(() => {
    if (floating || !open) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [floating, open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setLoading(true);
    setError("");
    getRecordImageBlobUrl(recordId)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u;
        setUrl(u);
      })
      .catch(() => {
        if (!cancelled) setError("처방전 사진을 불러오지 못했어요.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setUrl(null);
    };
  }, [open, recordId]);

  const toggle = (e?: MouseEvent) => {
    e?.stopPropagation();
    setOpen((v) => !v);
  };

  const body = loading ? (
    <p className="text-[13px] text-center py-10" style={{ color: C.muted }}>불러오는 중...</p>
  ) : error ? (
    <p className="text-[13px] text-center py-10" style={{ color: "#D94F4F" }}>{error}</p>
  ) : url ? (
    <ZoomableImage url={url} />
  ) : null;

  if (floating) {
    return (
      <>
        {/* [2026-07-25] bottom-24 — ChatFab.tsx의 전역 챗봇 버튼(bottom-6, 56px)과
            겹치지 않게 그 위에 쌓는다. */}
        <button
          onClick={toggle}
          className="fixed bottom-24 right-6 z-50 rounded-full flex items-center justify-center"
          style={{ width: 52, height: 52, background: C.terracotta, boxShadow: "0 4px 16px rgba(193,101,61,0.35)" }}
          aria-label="처방전 원본 사진 보기"
        >
          {open ? <X className="w-5 h-5 text-white" /> : <Camera className="w-5 h-5 text-white" />}
        </button>
        {open && (
          <div
            className="fixed bottom-44 right-6 z-50 w-80 h-96 rounded-2xl overflow-hidden flex flex-col"
            style={{ background: C.surface, boxShadow: "0 8px 32px rgba(30,26,23,0.25)" }}
          >
            <div className="px-4 py-3 shrink-0" style={{ background: C.dark }}>
              <span className="text-[13px] font-bold text-white">처방전 원본 사진</span>
            </div>
            <div className="p-3 flex-1 min-h-0">{body}</div>
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[12px] font-bold"
        style={{ background: `${C.terracotta}15`, color: C.terracotta }}
      >
        <Camera className="w-3.5 h-3.5" /> 처방전 사진 보기
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-3"
          style={{ background: "rgba(30,26,23,0.7)" }}
          onClick={toggle}
        >
          <div
            className="rounded-3xl p-5 w-[95vw] h-[92vh] max-w-5xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
            style={{ background: C.surface }}
          >
            <div className="flex items-center justify-between mb-3 shrink-0">
              <span className="text-[15px] font-black" style={{ color: C.dark }}>처방전 원본 사진</span>
              <button onClick={toggle} aria-label="닫기">
                <X className="w-5 h-5" style={{ color: C.muted }} />
              </button>
            </div>
            <div className="flex-1 min-h-0">{body}</div>
          </div>
        </div>
      )}
    </>
  );
}
