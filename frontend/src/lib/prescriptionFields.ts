import type { OcrMedication } from "../api/records";

// [2026-07-27 이동] PrescriptionReview.tsx(환자 처방확인 화면)와 MedGuide.tsx(보호자 검토
// 화면)가 같은 칸 구조를 써야 해서 공유하던 상수 — 원래 PrescriptionReview.tsx에
// export돼 있었는데, 컴포넌트 파일이 컴포넌트 외에 다른 것도 export하면 Vite의 Fast
// Refresh가 그 파일을 "호환 안 됨"으로 보고 저장할 때마다 상위 모듈까지 통째로 다시
// 로드한다(react-refresh/only-export-components) — 이게 반복되면서 개발 중인 탭에
// 낡은 모듈이 남아 "사진 보기" 버튼처럼 최근에 추가한 UI가 안 보이는 것처럼 보이는
// 원인이 됐다. 컴포넌트가 아닌 값이라 별도 파일로 뺐다.
export const FIELDS: { key: keyof OcrMedication; label: string }[] = [
  { key: "drug_name", label: "약품명" },
  { key: "dosage", label: "1회 사용량" },
  { key: "dose_amount", label: "1회 투여량" },
  { key: "frequency", label: "1일 투약횟수" },
  { key: "total_days", label: "총 투약일수" },
  { key: "diagnosis", label: "진단명" },
  { key: "drug_class", label: "약효분류" },
];
