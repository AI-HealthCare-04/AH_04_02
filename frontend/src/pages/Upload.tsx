import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Camera, Check, FileText, Image as ImageIcon, X } from "lucide-react";
import NavBar from "../components/NavBar";
import { getCurrentPatientId } from "../lib/session";
import { C } from "../theme";

const TIPS = [
  "처방전 전체가 화면에 들어오게 찍어주세요",
  "밝은 곳에서 그림자 없이 찍어주세요",
  "처방전을 평평하게 펴주세요",
  "초점이 선명하게 맞은 뒤 촬영해주세요",
];

export default function Upload() {
  const navigate = useNavigate();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const albumInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const applyFile = (selected: File | undefined) => {
    if (!selected) return;
    if (selected.size > 10 * 1024 * 1024) {
      setError("파일 용량이 너무 커요. 10MB 이하 이미지로 올려주세요.");
      return;
    }
    setError("");
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => applyFile(e.target.files?.[0]);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    applyFile(e.dataTransfer.files?.[0]);
  };

  const removeFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
  };

  const handleUpload = () => {
    if (!file) return;
    // 실제 업로드 요청은 Processing.tsx에서 보냄 (동기 방식이라 몇 초 걸릴 수 있어서
    // 애니메이션이 있는 화면으로 넘어간 다음 거기서 기다리는 구조)
    navigate("/processing", { state: { file, patientId: getCurrentPatientId() } });
  };

  return (
    <div className="min-h-screen" style={{ background: C.ivory }}>
      <NavBar isLoggedIn userName="김건강" />
      <main className="max-w-2xl mx-auto px-6 sm:px-8 py-10">
        <p className="text-[13px] font-bold mb-1" style={{ color: C.terracotta }}>복약 안내 만들기</p>
        <h1 className="text-[26px] font-black mb-1" style={{ color: C.dark }}>처방전을 올려주세요</h1>
        <p className="text-[14px] mb-7" style={{ color: C.muted }}>
          처방전이나 약봉투 사진을 올려주시면 복약 안내를 만들어드려요
        </p>

        <div className="grid grid-cols-2 gap-4 mb-5">
          <button
            onClick={() => cameraInputRef.current?.click()}
            className="flex flex-col items-center text-center p-6 rounded-2xl transition-all hover:shadow-md"
            style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)", border: "1.5px solid rgba(30,26,23,0.08)" }}
          >
            <Camera className="w-9 h-9 mb-3" style={{ color: C.terracotta }} />
            <p className="text-[15px] font-black mb-1" style={{ color: C.dark }}>사진 바로 찍기</p>
            <p className="text-[12px]" style={{ color: C.muted }}>카메라로 처방전을 촬영해요</p>
          </button>
          <button
            onClick={() => albumInputRef.current?.click()}
            className="flex flex-col items-center text-center p-6 rounded-2xl transition-all hover:shadow-md"
            style={{ background: C.white, boxShadow: "0 2px 16px rgba(30,26,23,0.07)", border: "1.5px solid rgba(30,26,23,0.08)" }}
          >
            <ImageIcon className="w-9 h-9 mb-3" style={{ color: C.terracotta }} />
            <p className="text-[15px] font-black mb-1" style={{ color: C.dark }}>앨범에서 선택</p>
            <p className="text-[12px]" style={{ color: C.muted }}>저장된 사진을 첨부해요</p>
          </button>
          <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleInputChange} className="hidden" />
          <input ref={albumInputRef} type="file" accept="image/*" onChange={handleInputChange} className="hidden" />
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className="rounded-2xl flex flex-col items-center justify-center py-8 mb-6 transition-all"
          style={{ border: `2px dashed ${dragging ? C.terracotta : "rgba(30,26,23,0.2)"}`, background: dragging ? `${C.terracotta}05` : "transparent" }}
        >
          <FileText className="w-7 h-7 mb-2" style={{ color: dragging ? C.terracotta : C.muted }} />
          <p className="text-[13px]" style={{ color: C.muted }}>여기로 파일을 끌어다 놓아도 돼요</p>
        </div>

        <div className="rounded-2xl p-6 mb-6" style={{ background: "#FBF8F3", border: "1px solid rgba(30,26,23,0.08)" }}>
          <p className="text-[15px] font-black mb-4" style={{ color: C.dark }}>잘 인식되는 사진 팁</p>
          {TIPS.map((tip) => (
            <div key={tip} className="flex items-start gap-2.5 mb-2.5 last:mb-0">
              <Check className="w-4 h-4 shrink-0 mt-0.5" style={{ color: C.success }} />
              <p className="text-[14px]" style={{ color: C.dark }}>{tip}</p>
            </div>
          ))}
        </div>

        {file && previewUrl && (
          <div
            className="rounded-2xl p-5 mb-5 flex items-center gap-4"
            style={{ background: C.white, border: `1.5px solid ${C.terracotta}40`, boxShadow: "0 2px 12px rgba(30,26,23,0.06)" }}
          >
            <div className="w-16 h-16 rounded-xl overflow-hidden shrink-0" style={{ background: "#EDE8DF" }}>
              <img src={previewUrl} alt="처방전 미리보기" className="w-full h-full object-cover" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[14px] font-bold truncate" style={{ color: C.dark }}>{file.name}</p>
              <p className="text-[12px]" style={{ color: C.muted }}>{(file.size / 1024 / 1024).toFixed(1)}MB</p>
            </div>
            <button onClick={removeFile} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-black/5 shrink-0" style={{ color: C.muted }}>
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {error && <p className="text-[13px] mb-4" style={{ color: "#D94F4F" }}>{error}</p>}

        <button
          disabled={!file}
          onClick={handleUpload}
          className="w-full py-4 rounded-full text-white font-black text-[17px] transition-all disabled:cursor-not-allowed"
          style={{ background: file ? C.terracotta : "#C8BFB8" }}
        >
          업로드
        </button>
      </main>
    </div>
  );
}
