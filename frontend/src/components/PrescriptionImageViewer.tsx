import { useEffect, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { createPortal } from "react-dom";
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
  const containerRef = useRef<HTMLDivElement>(null);

  const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  const zoomBy = (delta: number) => {
    setScale((prev) => {
      const next = clampScale(prev + delta);
      if (next === MIN_SCALE) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  // [2026-07-27 버그수정] React의 onWheel(합성 이벤트)로 등록하면 리액트가 내부적으로
  // 이 리스너를 passive로 붙여서 e.preventDefault()가 브라우저에 씹힐 수 있다 — 그러면
  // 우리 JS가 사진의 scale을 바꾸는 것과 "동시에" 브라우저 자체의 트랙패드 핀치줌
  // (ctrl+wheel)·페이지 스크롤도 함께 일어나서, 사진과 화면이 서로 다른 배율로 움직이며
  // 확대/축소가 깜빡이는 것처럼 보였다(스크롤 잠금만으로는 해결 안 됨). ref로 DOM에
  // 직접 { passive: false } 리스너를 붙여야 preventDefault가 확실히 먹는다.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoomBy(e.deltaY < 0 ? 0.3 : -0.3);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePointerDown = (e: PointerEvent<HTMLImageElement>) => {
    if (scale === MIN_SCALE) return;
    // [2026-07-27 추가] 이걸 안 부르면 확대된 사진을 드래그하다 커서가 사진 밖(제목·닫기
    // 버튼 등 텍스트가 있는 영역)으로 나가는 순간 브라우저가 그 텍스트를 네이티브
    // 드래그-선택으로 잡아버려서 화면이 깜빡이고, 마우스를 떼도 선택이 남아 있어서
    // 닫기 버튼 클릭이 씹히는 원인이었다.
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };

  const handlePointerMove = (e: PointerEvent<HTMLImageElement>) => {
    if (!dragRef.current) return;
    const d = dragRef.current;
    setPan({ x: d.panX + (e.clientX - d.x), y: d.panY + (e.clientY - d.y) });
  };

  const handlePointerUp = (e: PointerEvent<HTMLImageElement>) => {
    dragRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };

  const reset = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="flex flex-col h-full">
      <div
        ref={containerRef}
        className="relative flex-1 overflow-hidden rounded-xl"
        style={{ background: "rgba(30,26,23,0.03)", touchAction: "none" }}
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

// [2026-07-25 추가, 2026-07-27 수정] 처방전 원본 사진 팝업 — record_id로만 불러오므로 이
// 처방전에 연결된 사진만 열람된다(다른 기록의 사진이 섞일 수 없음). floating=true면 트리거가
// 챗봇 버튼 위에 뜨는 작은 카메라 아이콘(PrescriptionReview.tsx 수정 화면, MedGuide.tsx 검토
// 화면), 아니면 "처방전 사진 보기" 일반 버튼(목록·상세 화면)이다 — 어느 쪽이든 눌렀을 때
// 열리는 화면은 항상 같은, 화면 대부분을 채우는 모달(휠 확대·축소, 드래그 이동 가능). 처음엔
// floating 트리거가 작은 패널을 따로 열었는데, 편집 중 세부 내용을 확인하기엔 너무 작다는
// 피드백을 반영해 다른 화면들과 동일한 큰 모달로 통일했다.
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

  // [2026-07-27 버그수정] 스크롤 잠금(위)과 ZoomableImage 내부의 { passive: false } 휠
  // 리스너 두 가지를 고쳤는데도 확대/축소 깜빡임이 재현됐다 — 진짜 원인은 트랙패드
  // 핀치줌(ctrl+wheel로 브라우저에 전달됨)이었다. 이 제스처는 커서가 사진 위(ZoomableImage
  // 내부 리스너가 있는 곳)를 벗어나 팝업의 다른 부분(제목줄·여백·닫기 버튼 등) 위에 있을
  // 때는 아무도 막지 않아서 브라우저 자체의 페이지 확대/축소가 그대로 일어났다 —
  // overflow:hidden은 "스크롤"만 막지 "페이지 줌"은 막지 못한다(서로 다른 브라우저
  // 기능). 팝업이 열려 있는 동안은 document 전체에서 ctrlKey가 있는 휠 이벤트(핀치줌)만
  // 콕 집어 막는다 — 일반 스크롤(ctrlKey 없음)은 그대로 둬도 body가 이미 잠겨 있어 안전하다.
  useEffect(() => {
    if (!open) return;
    const blockPinchZoom = (e: WheelEvent) => {
      if (e.ctrlKey) e.preventDefault();
    };
    document.addEventListener("wheel", blockPinchZoom, { passive: false });
    return () => document.removeEventListener("wheel", blockPinchZoom);
  }, [open]);

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
      .catch((e) => {
        if (cancelled) return;
        // [2026-07-28 버그수정] 지금까지는 원인과 무관하게 항상 같은 문구였다 — 실제
        // 배포 환경에서 이 요청이 실패하는 흔한 원인 두 가지(사진 파일이 서버 디스크에
        // 없음 vs 그 외 네트워크/타임아웃)를 구분해서 보여주면, 재현 시 원인 파악이
        // 훨씬 쉬워진다.
        const status = (e as { response?: { status?: number } })?.response?.status;
        setError(
          status === 404
            ? "저장된 처방전 사진을 찾을 수 없어요. 다시 문의해 주세요."
            : "처방전 사진을 불러오지 못했어요."
        );
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

  // [2026-07-27] fixed 요소를 document.body로 포탈 — 목록 화면(Records.tsx/
  // MedGuideList.tsx)의 카드에 hover:-translate-y-0.5 같은 transform이 있으면, 그
  // transform이 걸린 조상이 fixed 자식의 컨테이닝 블록이 돼버려서(CSS 스펙) 팝업이
  // 뷰포트가 아니라 카드 기준으로 배치되고, 카드의 :hover가 드래그 중 켜졌다 꺼졌다
  // 하면서 화면이 깜빡였다. body에 직접 포탈하면 어느 화면에 놓이든 항상 뷰포트
  // 기준으로 고정된다.
  const modal = open
    ? createPortal(
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
        </div>,
        document.body
      )
    : null;

  if (floating) {
    return createPortal(
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
        {modal}
      </>,
      document.body
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
      {modal}
    </>
  );
}
