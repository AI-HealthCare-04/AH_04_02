# 배포 환경 변경 시 체크리스트

`backend/.env`·`frontend/.env`·`rag/.env`는 `.gitignore`로 git에 올라가지 않는 **EC2 인스턴스
로컬 파일**입니다. 그래서 도메인/IP를 바꾸거나 인스턴스를 새로 만들 때 "이 값도 같이
바꿔야 한다"는 걸 아무도 기억하지 못하면 조용히 깨집니다 — 실제로 2026-07-27 도메인
전환 때 로그인이 갑자기 안 됐던 사고, 이후 Langfuse 추적이 안 됐던 사고 둘 다 이 문제였습니다
(자세한 경위는 `docs/TROUBLESHOOTING.md` 참고).

이 문서는 사고가 터진 *뒤에* 찾아보는 게 아니라, 배포 환경을 바꾸기 *전에* 먼저 펼쳐놓고
하나씩 확인하는 용도입니다.

## 언제 이 체크리스트를 봐야 하나

- EC2 인스턴스를 새로 만들거나(IP가 바뀜) 도메인을 바꿀 때
- HTTP → HTTPS로 전환할 때
- 팀 공통 개발 DB(Aiven MySQL) 접속 정보가 바뀔 때
- Langfuse/OpenAI/data.go.kr 같은 외부 서비스 키를 재발급하거나 프로젝트를 옮길 때
- `.env.example`에 새 항목이 추가됐는데 실제 서버 `.env`에는 아직 없을 때

## 1) 도메인/IP/HTTPS가 바뀔 때

| 파일 | 변수 | 확인할 것 |
|---|---|---|
| `backend/.env` | `CORS_ALLOWED_ORIGINS` | 새 프론트 도메인(`https://...`)이 포함돼 있는지. 로컬 개발용 origin은 코드에 이미 있어 여기 안 적어도 됨 |
| `frontend/.env` | `VITE_MONITORING_API_URL` | 새 백엔드 도메인/포트를 가리키는지. **Vite 환경변수는 빌드 시점에 값이 박히므로, `.env`만 고치고 `docker compose up -d --build`(프론트 재빌드)를 안 하면 반영 안 됨** |

> ⚠️ 주의: `sed`/`echo`로 값을 통째로 덮어쓰는 명령어는 다른 도메인이 콤마로 함께
> 등록돼 있거나 다른 변수가 같은 줄에 있으면 그것까지 지워버립니다. 파일을 직접 열어
> 해당 줄만 고치는 걸 권장합니다.

## 2) 팀 공통 DB(Aiven MySQL) 접속 정보가 바뀔 때

| 파일 | 변수 | 확인할 것 |
|---|---|---|
| `backend/.env` | `DATABASE_URL` | `mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE` 형식, 새 접속 정보로 |
| `backend/.env` | `DATABASE_SSL_REQUIRED` | Aiven 등 관리형 MySQL은 `true` 필수 — 안 그러면 연결 자체가 거부됨 |
| `backend/.env` | `DATABASE_SSL_CA` | Aiven 콘솔에서 받은 `ca.pem` 경로. `production`은 이 값이 없으면 서버가 기동을 거부함(의도된 안전장치) |

## 3) 외부 서비스 키가 바뀔 때

| 파일 | 변수 | 비고 |
|---|---|---|
| `rag/.env` | `OPENAI_API_KEY` | 없으면 RAG/챗봇이 stub(가짜 데이터)로 조용히 폴백 — 에러가 안 나서 "왜 답변이 이상하지"로만 보임 |
| `rag/.env` | `DATA_GO_KR_SERVICE_KEY` | 식약처 e약은요 API 키 |
| `backend/.env` | `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_BASE_URL` | 셋 중 하나라도 없으면 추적이 조용히 꺼짐(챗봇 자체는 안 죽음 — 의도된 설계). Langfuse Cloud 리전이 프로젝트별로 다를 수 있으니 `LANGFUSE_BASE_URL`은 실제 프로젝트가 만들어진 리전 URL인지 확인 |
| `backend/.env` | `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Web Push 발송 키 — 없으면 발송을 조용히 스킵 |
| `backend/.env` | `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`SMTP_FROM` | `EMAIL_PROVIDER=smtp`일 때만 필요. 넷 중 하나라도 비어있으면(다른 항목과 달리) 서버가 즉시 에러를 냄 — 비밀번호 재설정 메일이 영영 안 나가는 상황을 숨기지 않기 위한 의도된 설계 |

## 4) 인스턴스를 통째로 새로 만들 때(가장 위험)

위 1~3번 전부 + 아래 항목까지 **전부 처음부터 다시 채워야 합니다** — 새 인스턴스는
`backend/.env`/`frontend/.env`/`rag/.env`가 전부 빈 파일(또는 `.env.example` 그대로)입니다.

- `SECRET_KEY` (JWT 서명 키)
- `PII_ENCRYPTION_KEY` / `PII_HASH_SECRET` (개인정보 암복호화 — 이 값이 바뀌면 기존에 암호화 저장된 이름/전화번호를 더 이상 복호화 못 하게 되므로, 기존 DB를 계속 쓸 거라면 **반드시 이전 값 그대로 옮겨와야 함**, 새로 생성하면 안 됨)
- `CLOVA_OCR_API_URL` / `CLOVA_OCR_SECRET_KEY`
- 위 1~3번 전체

## 확인 방법

값을 채운 뒤에는 그냥 "설정했다"로 끝내지 말고, 실제로 그 기능을 한 번 써서 확인합니다:

- CORS/API URL → 실제 프론트에서 로그인 시도
- Langfuse → 챗봇 질문 1개 → `docker compose logs backend --tail 50 | grep -i langfuse`로 "disabled" 로그가 없는지 + Langfuse Cloud 대시보드에서 실제 trace 확인
- Web Push → 알림 설정 화면에서 "이 기기로 알림 받기" 켜보고 실제 알림이 오는지
- SMTP → 비밀번호 재설정 요청 후 메일 수신 확인
