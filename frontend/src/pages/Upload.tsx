import { useState, type DragEvent, type ChangeEvent } from "react";

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) setFile(selected);
  };

  const handleUpload = () => {
    if (!file) return;
    // TODO: ③ 백엔드 연동 - POST /api/v1/medical-records
    console.log("업로드할 파일:", file.name);
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

        <button
          style={{
            ...styles.uploadButton,
            ...(file ? {} : styles.uploadButtonDisabled),
          }}
          disabled={!file}
          onClick={handleUpload}
        >
          업로드
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
