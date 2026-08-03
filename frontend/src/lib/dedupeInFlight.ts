/**
 * [2026-08-03 추가] api/monitoring.ts의 getCaregiverPatients가 이미 쓰던 "진행 중인 요청을
 * 캐시해서 동시 호출은 실제 네트워크 요청 하나만 공유" 패턴을 여러 함수에 재사용할 수
 * 있게 일반화한 것 — 같은 페이지에 마운트된 서로 다른 컴포넌트(예: NavBar + 그 페이지
 * 자신)가 각자 같은 API를 부르더라도, 응답이 아직 안 온 동안엔 새 HTTP 요청을 또
 * 내보내지 않고 이미 나가 있는 요청의 Promise를 그대로 돌려준다. 응답이 오면(성공/실패
 * 상관없이) 캐시를 비워서, 다음 호출은 항상 최신 데이터를 다시 받아온다 — 이 함수는
 * "동시에 몰린 중복 호출"만 합치는 것이지 별도의 staleness/캐시 레이어가 아니다.
 */
export function dedupeInFlight<Args extends unknown[], T>(
  fn: (...args: Args) => Promise<T>,
  keyFn: (...args: Args) => string = (...args) => JSON.stringify(args)
): (...args: Args) => Promise<T> {
  const inFlight = new Map<string, Promise<T>>();

  return (...args: Args): Promise<T> => {
    const key = keyFn(...args);
    const existing = inFlight.get(key);
    if (existing) return existing;

    const promise = fn(...args).finally(() => {
      inFlight.delete(key);
    });
    inFlight.set(key, promise);
    return promise;
  };
}
