
---

| 날짜 | 2026.07.02 |
|---|---|
| **이슈** | 토글 버튼 클릭 후 검은 테두리(outline)가 사라지지 않고 잔류 |
| **발생 위치** | `Check.tsx` 자가진단 버튼, `Dashboard.tsx` 복약 상태 버튼, `Connect.tsx` 관계 유형 버튼 |
| **원인** | React 인라인 스타일에서 `border` 단축속성과 `borderColor` 개별속성을 **동시에 사용**하면, 상태 전환 시 React가 이전 `border` 값을 제거하면서 브라우저 기본 `outline`(2.85px)이 노출됨. 크롬 DevTools Computed 탭에서 `outline-style: none` 이지만 `outline-width: 2.85714px` 가 남아있는 것으로 확인. 추가로 콘솔에 `"Removing a style property during rerender (borderColor)"` 경고 발생 |
| **시도한 방법 (실패)** | ① `index.css`에 `button:focus { outline: none }` 추가 → 효과 없음 ② `!important` 추가 → 효과 없음 ③ `onMouseDown={(e) => e.preventDefault()}` 단독 적용 → 효과 없음 ④ `borderWidth/borderStyle/borderColor` 개별속성으로 분리 → 오히려 테두리 두꺼워짐 |
| **해결** | `styles` 객체에서 버튼 스타일을 분리하고, JSX 렌더링 시 **`isActive` 조건으로 모든 border 속성을 인라인으로 직접 계산**하여 적용. spread(`...`) 병합 없이 하나의 style 객체로 완성해서 React rerender 시 속성 충돌 원천 차단 |
| **핵심 패턴** | `border` 단축속성과 개별속성(`borderColor` 등)을 같은 컴포넌트에서 섞지 말 것. 상태에 따라 스타일이 바뀌는 버튼은 반드시 JSX 인라인 계산 방식 사용 |

```tsx
// ❌ 잘못된 패턴 — border 단축속성 + borderColor 개별속성 혼용
const styles = {
  btn: { border: "1px solid #E0D3C4" },
  btnActive: { borderColor: "#C16A45" },  // 충돌 발생!
}

// ✅ 올바른 패턴 — isActive로 전체 속성을 한번에 계산
<button style={{
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: isActive ? "#C16A45" : "#E0D3C4",
  background: isActive ? "#C16A45" : "#F5F0EA",
  outline: "none",
}}>
```
