// [2026-07-24 추가] PatientManagement.tsx에 있던 만 나이 계산을 MyPage.tsx도 써야 해서
// 공용 유틸로 뺐다. birth_date는 자유 텍스트 입력이라("1945.03.15" 같은) 흔한 구분자
// (.,-,/)만 관대하게 파싱하고, 못 읽으면 나이를 지어내지 않고 null로 둔다. 구분자 없는
// "19450315"(DB에 직접 넣은 값 등)도 같이 인식한다.
export function computeAge(birthDate: string | null | undefined): number | null {
  if (!birthDate) return null;
  // 구분자 있는 형식(월/일 한 자리도 허용)을 우선 시도하고, 안 되면 구분자 없는
  // "19450315" 형식(월/일 반드시 두 자리)으로 한 번 더 시도한다.
  const match = birthDate.match(/(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})/) ?? birthDate.match(/(\d{4})(\d{2})(\d{2})/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const birth = new Date(year, month - 1, day);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const hadBirthdayThisYear =
    now.getMonth() > birth.getMonth() || (now.getMonth() === birth.getMonth() && now.getDate() >= birth.getDate());
  if (!hadBirthdayThisYear) age -= 1;
  return age;
}

export const GENDER_LABEL: Record<string, string> = { male: "남성", female: "여성" };
