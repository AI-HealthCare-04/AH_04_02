import { useState, type DragEvent, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { uploadMedicalRecord } from "../api/medicalRecords";

export default function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      setFile(dropped);
      setError("");
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setError("");
    }
  };

  const handleUpload = async () => {
    if (!file || uploading) return;

    // 413 방지용 클라이언트 사전 체크 (API명세서: 10MB 초과 거부)
    if (file.size > 10 * 1024 * 1024) {
      setError("파일 용량이 너무 커요. 10MB 이하 이미지로 올려주세요.");
      return;
    }

    setUploading(true);
    setError("");

    try {
      // TODO: 로그인 연동 완료 전까지는 localStorage user_id 임시 사용 (기본값 1)
      const uploadedFor = Number(localStorage.getItem("user_id") ?? 1);
      const { record_id } = await uploadMedicalRecord(file, uploadedFor);
      navigate("/processing", { state: { recordId: record_id } });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ?? "업로드 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요.";
      setError(message);
      setUploading(false);
    }
  };

  return (
    <div style={styles.page}>
      <nav style={styles.nav}>
        <span style={styles.logo}>건강동행</span>
      </nav>

      <main style={styles.main}>
        <h1 style={styles.title}>처방전 업로드</h1>
        <p style={styles.subtitle}>
          처방전이나 약봉투 사진을 올려주시면 복약 안내를 만들어드려요.
        </p>

        <div
          style={{
            ...styles.dropzone,
            ...(isDragging ? styles.dropzoneActive : {}),
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          {file ? (
            <p style={styles.fileName}>{file.name}</p>
          ) : (
            <>
              <p style={styles.dropzoneText}>
                여기로 파일을 끌어다 놓거나
              </p>
              <label style={styles.fileLabel}>
                파일 선택하기
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  style={{ display: "none" }}
                />
              </label>
            </>
          )}
        </div>

        {error && <p style={styles.errorText}>{error}</p>}

        <button
          style={{
            ...styles.uploadButton,
            ...(file && !uploading ? {} : styles.uploadButtonDisabled),
          }}
          disabled={!file || uploading}
          onClick={handleUpload}
        >
          {uploading ? "업로드 중..." : "업로드"}
        </button>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#FAF6F1",
    fontFamily: "'Apple SD Gothic Neo', sans-serif",
  },
  nav: {
    padding: "16px 24px",
    background: "#FFFFFF",
    borderBottom: "1px solid #EEE6DC",
  },
  logo: {
    fontSize: 18,
    fontWeight: 700,
    color: "#C16A45",
  },
  main: {
    maxWidth: 600,
    margin: "0 auto",
    padding: "60px 24px",
    textAlign: "center",
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "#2A2A2A",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: "#888888",
    marginBottom: 32,
  },
  dropzone: {
    border: "2px dashed #D9C8B8",
    borderRadius: 16,
    padding: "60px 20px",
    background: "#FFFFFF",
    marginBottom: 24,
    transition: "border-color 0.2s",
  },
  dropzoneActive: {
    borderColor: "#C16A45",
    background: "#FFF8F3",
  },
  dropzoneText: {
    fontSize: 14,
    color: "#999999",
    marginBottom: 16,
  },
  fileLabel: {
    display: "inline-block",
    padding: "10px 20px",
    background: "#F0E5D8",
    borderRadius: 8,
    fontSize: 14,
    color: "#2A2A2A",
    cursor: "pointer",
  },
  fileName: {
    fontSize: 15,
    color: "#2A2A2A",
    fontWeight: 500,
  },
  errorText: {
    fontSize: 13,
    color: "#D94F4F",
    marginBottom: 16,
    marginTop: -12,
  },
  uploadButton: {
    width: "100%",
    padding: "14px",
    fontSize: 16,
    fontWeight: 600,
    color: "#FFFFFF",
    background: "#C16A45",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
  },
  uploadButtonDisabled: {
    background: "#D9C8B8",
    cursor: "not-allowed",
  },
};
