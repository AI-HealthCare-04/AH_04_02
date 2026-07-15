"""
models.py — 테이블 정의

⚠️ 이 파일은 기존 ERD(7/6 검토 완료본)를 SQLite에 맞게 옮긴 "초안"입니다.
Day 2에 각자 자기 테이블을 검토하고 필요하면 컬럼을 고쳐서 확정하세요:
  - ocr_results, medical_records → 권순현
  - guide_results → 김영혜
  - patients, caregivers, caregiver_patients, medication_schedules, medication_logs → 박소정

컬럼 추가/삭제 후 서버를 재시작하면... SQLite는 기존 테이블을 자동 변경하지 않으므로
개발 중엔 app.db 파일을 지우고 재시작하는 게 제일 간단합니다.

[7/6 추가] 환자 구분 도입 — patients / caregivers / caregiver_patients
- 다대다로 만들어서 "한 보호자가 여러 환자"뿐 아니라 "한 환자를 여러 보호자가 같이 케어"도 커버함.
- 서버 최초 기동 시 테스트용 환자 1명 + 보호자 1명을 자동으로 만들어둠 (database.py의 seed_demo_data 참고)

[7/6 추가 2, 7/9 확장] 로그인/회원가입 — 보호자뿐 아니라 환자 본인도 로그인 대상
- 처음엔 "환자는 앱을 직접 쓰지 않는 케어 대상"으로 보고 Caregiver만 로그인하게 했었지만,
  실제로는 환자 본인도 서비스 이용 대상이라 로그인이 필요함 — Patient에도 email/hashed_password를
  두고, routers/auth_router.py가 caregiver/patient 양쪽 다 로그인을 지원하도록 확장함(auth.py의
  JWT에 role 클레임 추가). caregiver_id를 쿼리 파라미터로 넘기던 기존 방식(monitoring_router.py)은
  이번 변경 범위 밖이라 그대로 둠 — 로그인 자체를 붙이는 것과, 기존 엔드포인트들이 실제 토큰을
  쓰도록 바꾸는 건 별도 작업.

[7/9 추가] 개인정보(이름·전화번호) 암호화 — 2026-07-08 멘토링 확정 방침 반영
- name/phone을 평문 컬럼으로 두지 않고 name_encrypted/phone_encrypted(Fernet 대칭키 암호화)로
  저장한다. phone은 로그인/검색에도 쓰이므로 조회용 HMAC-SHA256 해시(phone_hash)를 별도로 둠.
- .name/.phone은 이제 실제 컬럼이 아니라 파이썬 프로퍼티(security.py의 encrypt_pii/decrypt_pii/
  hash_phone 사용) — 기존 코드에서 `caregiver.name`처럼 읽던 곳은 그대로 동작하고(투명하게 복호화),
  `Patient(name=..., phone=...)`처럼 생성자에 바로 넘기던 곳만 `patient.name = ...` 형태로 바꾸면 됨
  (프로퍼티는 생성자 kwarg로는 못 받음 — 아래 각 라우터의 create_* 함수 참고).
- PII_ENCRYPTION_KEY/PII_HASH_SECRET 환경변수가 없으면 security.py가 서버 기동 시점에 즉시 에러를
  내므로, backend/.env에 반드시 채워야 함(생성 방법은 security.py 상단 주석 참고).
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from core.security import decrypt_pii, encrypt_pii, hash_phone


# ── 환자 [7/6 추가, 7/9 로그인 대상으로 전환 + PII 암호화] ──
class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    # [7/9] 평문 name 대신 암호화 저장 — 아래 .name 프로퍼티로 투명하게 암복호화.
    # 기본값 ""은 "Patient(**kwargs) 생성 후 patient.name = ... 로 설정"하는 2단계 생성
    # 패턴을 쓰기 위한 것일 뿐, 실제로 빈 문자열로 남겨두면 안 됨(항상 .name으로 설정).
    name_encrypted: str = Field(default="")
    note: Optional[str] = None  # 특이사항 (예: "치매 초기", "혼자 거주" 등 자유 텍스트)
    phone_encrypted: Optional[str] = None  # [7/8 추가, 7/9 암호화] 회원가입(SignUp.tsx) 연락처
    phone_hash: Optional[str] = Field(default=None, index=True)  # [7/9] 로그인/검색용, 복호화 대상 아님
    # [7/8 추가] 회원가입 시 아이디(이메일/전화번호 둘 다 로그인 식별자로 허용).
    # [2026-07-14] 유니크 제약이 없어서 같은 이메일로 중복 가입이 조용히 허용되던 버그를
    # 고쳤다 — 항상 security.normalize_email()로 정규화한 값만 여기 저장한다는 전제.
    email: Optional[str] = Field(default=None, unique=True, index=True)
    birth_date: Optional[str] = None  # [7/8 추가] 생년월일 (자유 텍스트, 예: "1945.03.15")
    # [7/8 추가, 7/9 실제 로그인 대상으로 전환] 환자 본인 계정 비밀번호 — Caregiver.hashed_password와 동일 원칙
    hashed_password: Optional[str] = None
    push_enabled: bool = True  # [7/8 추가] 회원가입 알림 수신 설정 (Caregiver와 동일한 3종)
    sms_enabled: bool = False
    email_opt_in: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def name(self) -> str:
        return decrypt_pii(self.name_encrypted)

    @name.setter
    def name(self, value: str) -> None:
        self.name_encrypted = encrypt_pii(value)

    @property
    def phone(self) -> Optional[str]:
        return decrypt_pii(self.phone_encrypted) if self.phone_encrypted else None

    @phone.setter
    def phone(self, value: Optional[str]) -> None:
        if value:
            self.phone_encrypted = encrypt_pii(value)
            self.phone_hash = hash_phone(value)
        else:
            self.phone_encrypted = None
            self.phone_hash = None


# ── 보호자·요양보호사·단체(기관) 등 [7/6 추가, 7/8 단체 지원 확장, 7/9 PII 암호화] ──
class Caregiver(SQLModel, table=True):
    __tablename__ = "caregivers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name_encrypted: str = Field(default="")  # [7/9] Patient.name_encrypted와 동일한 원칙 — .name 프로퍼티 참고
    email: Optional[str] = Field(default=None, unique=True, index=True)  # 회원가입 화면의 "아이디" 입력이 여기 저장됨
    hashed_password: Optional[str] = None
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker / organization
    phone_encrypted: Optional[str] = None  # [7/8 추가, 7/9 암호화] 회원가입 연락처
    phone_hash: Optional[str] = Field(default=None, index=True)  # [7/9] 로그인/검색용, 복호화 대상 아님
    birth_date: Optional[str] = None  # [7/8 추가] 생년월일 (자유 텍스트)
    push_enabled: bool = True  # [7/8 추가] 회원가입 "Push 알림 허용" (필수 체크)
    sms_enabled: bool = False  # [7/8 추가] 회원가입 "문자(SMS) 수신 허용" (선택)
    email_opt_in: bool = False  # [7/8 추가] 회원가입 "이메일 수신 허용" (선택, 계정 아이디용 email과는 별개 동의 플래그)
    # [7/8 추가] relation_type == "organization"일 때만 채워지는 단체(기관) 전용 필드들
    org_name: Optional[str] = None  # 기관명
    org_type: Optional[str] = None  # 요양원 / 재가센터 / 협회 / 보건소 / 기타
    business_reg_no: Optional[str] = None  # 사업자등록번호
    # [7/9] manager_name/manager_phone(기관 소속 실무 담당자 연락처)은 로그인 계정 본인의 PII가
    # 아니라 부가 정보라 이번 암호화 범위에서는 뺐음 — 필요하면 팀 논의 후 별도로 암호화 추가.
    manager_name: Optional[str] = None  # 담당자 이름 (name과 별개 — 기관 소속 실무 담당자)
    manager_phone: Optional[str] = None  # 담당자 전화번호
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def name(self) -> str:
        return decrypt_pii(self.name_encrypted)

    @name.setter
    def name(self, value: str) -> None:
        self.name_encrypted = encrypt_pii(value)

    @property
    def phone(self) -> Optional[str]:
        return decrypt_pii(self.phone_encrypted) if self.phone_encrypted else None

    @phone.setter
    def phone(self, value: Optional[str]) -> None:
        if value:
            self.phone_encrypted = encrypt_pii(value)
            self.phone_hash = hash_phone(value)
        else:
            self.phone_encrypted = None
            self.phone_hash = None


# ── 보호자-환자 연결 (다대다) [7/6 추가] ──
class CaregiverPatient(SQLModel, table=True):
    __tablename__ = "caregiver_patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    caregiver_id: int = Field(foreign_key="caregivers.id")
    patient_id: int = Field(foreign_key="patients.id")
    created_at: datetime = Field(default_factory=datetime.now)


# ── 업로드 원본 단위 (1건의 처방전 사진 = 1행) ──
class MedicalRecord(SQLModel, table=True):
    __tablename__ = "medical_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")  # [7/6 추가] 이 처방전이 누구 것인지
    image_path: str  # 저장된 이미지 파일 경로
    status: str = Field(default="processing")  # processing / review_required / completed / failed
    raw_text: Optional[str] = None  # OCR 원문 (완료 후 기록)
    failure_reason: Optional[str] = None  # 실패 시 사유
    created_at: datetime = Field(default_factory=datetime.now)
    # [7/9 추가] 보호자가 대신 업로드한 경우에만 채워짐 — 본인이 직접 올렸으면 None
    uploaded_by_caregiver_id: Optional[int] = Field(default=None, foreign_key="caregivers.id")


# ── OCR 추출 결과 (약품 1개 = 1행, 담당: 권순현) ──
class OcrResult(SQLModel, table=True):
    __tablename__ = "ocr_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: int = Field(foreign_key="medical_records.id")
    drug_name: str
    drug_code: str = ""  # [7/6 추가] HIRA 약가마스터 매칭용 코드 (ocr_interface.py의 OCRResult와 동기화)
    dosage: str = ""       # 미인식이면 빈 문자열
    frequency: str = ""
    diagnosis: str = ""
    drug_class: str = ""
    confidence: float = 0.0  # 0.0 ~ 1.0
    review_required: bool = False  # [7/6 추가] confidence 낮아서 보호자 확인 필요한지
    user_confirmed: bool = False
    matched_drug_name: str = ""    # drug_matcher: 기준 약품명 목록에서 가장 유사한 이름
    match_score: float = 0.0       # drug_matcher: SequenceMatcher 유사도 (0~1)
    needs_review: bool = False     # drug_matcher: match_score < 0.7 이면 True (review_required와 별개)


# ── RAG 가이드 결과 (담당: 김영혜) ──
class GuideResult(SQLModel, table=True):
    __tablename__ = "guide_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: int = Field(foreign_key="medical_records.id")
    # SQLite엔 JSON 타입이 없어서 문자열로 저장: json.dumps()로 넣고 json.loads()로 꺼냄
    medication_guide: str
    lifestyle_guide: str
    source_refs: str = "[]"
    created_at: datetime = Field(default_factory=datetime.now)


# ── 복약 일정 (담당: 박소정, 멘토 최우선 지정) ──
class MedicationSchedule(SQLModel, table=True):
    __tablename__ = "medication_schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")  # [7/6 변경] 고정값 1 → 실제 환자 FK
    drug_name: str
    time_slot: str  # [7/8 변경] "08:00" 같은 실제 시각 문자열 (기존 "아침"/"점심"/"저녁"에서 변경)
    dose_timing: Optional[str] = None  # [7/8 추가] 복용상태: 공복/아침 식후/점심 식전/점심 식후/저녁 식전/저녁 식후
    caregiver_alert: bool = True  # [7/8 추가] 이 일정 알림을 보호자에게도 보낼지
    memo: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    # [2026-07-14 추가] patient_medications 도입 이후 새 일정은 여기로 연결한다. 기존
    # /monitoring/schedules 플로우(drug_name 자유 텍스트, patient_medication_id 없음)는
    # 전혀 안 건드리고 전부 nullable로만 추가 — 과거 데이터도 그대로 유효하다.
    patient_medication_id: Optional[int] = Field(
        default=None, foreign_key="patient_medications.id", index=True
    )
    meal_relation: Optional[str] = None  # 식전 / 식후 / 취침 전 등
    instructions: Optional[str] = None
    timezone: Optional[str] = None
    # JSON 배열 문자열(예: '["mon","wed","fri"]') — SQLite엔 JSON 타입이 없어 문자열로 저장
    # (guide_results.source_refs와 동일한 관례).
    days_of_week: Optional[str] = None


# ── 복약 기록 (담당: 박소정) ──
class MedicationLog(SQLModel, table=True):
    __tablename__ = "medication_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="medication_schedules.id")
    status: str = "taken"  # taken(복용) / skipped(건너뜀)
    checked_at: datetime = Field(default_factory=datetime.now)
    note: Optional[str] = None
    # [7/9 추가] 이 체크를 누가 했는지 — 환자 본인(patient) vs 보호자 대신(caregiver)
    confirmed_by_type: str = "patient"
    confirmed_by_caregiver_id: Optional[int] = Field(default=None, foreign_key="caregivers.id")


# ── 환자 의약품 등록 [2026-07-14 추가, 담당: 김영혜] ──
# 여러 로컬 개발 환경이 공통 DB를 쓰도록 정리하면서 함께 요청된 기능 — "환자가 입력한
# 의약품"을 OCR 파이프라인(medical_records/ocr_results)과 별개로 등록/조회할 수 있게 한다.
# OcrResult(review_required/user_confirmed/matched_drug_name/match_score)와 동일한 원칙:
# AI/OCR이 추정한 값과 사용자가 최종 확인한 값을 한 행에서 덮어쓰지 않고 함께 보존한다.
class PatientMedication(SQLModel, table=True):
    __tablename__ = "patient_medications"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    # 의약품 마스터 테이블 자체가 이 프로젝트에 아직 없다(rag/의 CSV·정부 API 실시간 조회로
    # 대체 중 — CONTRACT.md 참고). 그래서 FK를 걸 대상이 없어 drug_id는 제약 없는 컬럼으로
    # 남겨둔다 — 나중에 마스터 테이블이 생기면 그때 foreign_key를 추가한다. 검색 결과가
    # 하나로 확정되지 않으면 drug_id/item_seq를 null로 두고 원문(source_raw_text)만 남긴다.
    drug_id: Optional[int] = Field(default=None, index=True)
    item_seq: Optional[str] = Field(default=None, index=True)  # 식약처 품목일련번호
    product_code: Optional[str] = None
    medication_name: str  # 환자가 최종 확인한 의약품명 (확정 데이터 — 필수)
    manufacturer_name: Optional[str] = None
    dosage_amount: Optional[str] = None
    dosage_unit: Optional[str] = None  # 정 / 캡슐 / mL 등
    frequency_per_day: Optional[int] = None
    administration_route: Optional[str] = None  # 경구 등
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    prescription_id: Optional[int] = Field(default=None, foreign_key="medical_records.id")
    source_type: str = "manual"  # manual / prescription_ocr / pill_image / api_search
    # AI/OCR이 맨 처음 추출한 원문 그대로 — medication_name(사용자 확정값)과 절대 덮어쓰지
    # 않고 나란히 보존해서, 나중에 "AI가 뭐라고 봤었는지" 추적 가능하게 한다.
    source_raw_text: Optional[str] = None
    verification_status: str = "unverified"  # unverified / matched / user_confirmed / pharmacist_confirmed
    is_active: bool = True  # 현재 복용 여부
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    deleted_at: Optional[datetime] = None  # soft delete (DELETE API가 실제로 지우지 않고 여기만 채움)


# ── 실제 복약 수행 기록 [2026-07-14 추가, 담당: 김영혜] ──
# MedicationLog(기존, MedicationSchedule.schedule_id 필수)와 별개 테이블 — 기존 스케줄
# 체크인 플로우는 그대로 두고, patient_medications 기반의 새 등록/기록 플로우를 위해 추가.
class MedicationRecord(SQLModel, table=True):
    __tablename__ = "medication_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_medication_id: int = Field(foreign_key="patient_medications.id", index=True)
    schedule_id: Optional[int] = Field(default=None, foreign_key="medication_schedules.id")
    scheduled_at: Optional[datetime] = None
    taken_at: Optional[datetime] = None  # 실제 복용 시간, 아직 안 먹었으면 None
    status: str = "scheduled"  # scheduled / taken / missed / skipped / duplicate_suspected
    verification_method: str = "self_report"  # self_report / caregiver / photo / device
    evidence_image_url: Optional[str] = None
    memo: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ══════════════════════════════════════════════════════════
# [7/7 추가] Figma 화면 전체 연결을 위한 신규 테이블
# ══════════════════════════════════════════════════════════

# ── 자가진단 결과 (담당: 박소정) — Check.tsx/AssessmentPage 저장용 ──
class CareLevelAssessment(SQLModel, table=True):
    __tablename__ = "care_level_assessments"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    cognitive_level: str = "normal"  # normal / mild / severe
    mobility_level: str = "normal"
    vision_level: str = "normal"
    medication_awareness: bool = True
    medication_willingness: bool = True
    care_level: str = "independent"  # independent / guardian_check / third_party_needed
    reason: str = ""
    evaluated_at: datetime = Field(default_factory=datetime.now)


# ── 보호자 초대 (담당: 박소정) — CaregiverPage/InvitePage 실제 연동용 ──
# [2026-07-15] 보안 검토 반영: 토큰 원문 대신 해시 저장(token_hash), 만료시각 추가(expires_at),
# invited_phone도 다른 PII와 동일하게 암호화(.invited_phone 프로퍼티로 투명하게 암복호화).
class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    inviter_caregiver_id: Optional[int] = Field(default=None, foreign_key="caregivers.id")
    relation_type: str = "guardian"
    invited_phone_encrypted: Optional[str] = None
    token_hash: str = Field(unique=True, index=True)
    status: str = "pending"  # pending / accepted / rejected / expired
    created_at: datetime = Field(default_factory=datetime.now)
    accepted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @property
    def invited_phone(self) -> Optional[str]:
        return decrypt_pii(self.invited_phone_encrypted) if self.invited_phone_encrypted else None

    @invited_phone.setter
    def invited_phone(self, value: Optional[str]) -> None:
        self.invited_phone_encrypted = encrypt_pii(value) if value else None

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.now() > self.expires_at


# ── refresh 토큰 회전/재사용 탐지 (2026-07-15 추가, 보안 검토 REQ-001 반영) ──
# JWT 자체엔 무효화 개념이 없어서, 발급마다 jti를 여기 기록해두고 회전(재발급) 시 이전
# jti를 revoke한다 — 탈취된 refresh 토큰이 만료 전까지 계속 유효하던 문제를 완화한다.
class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    jti: str = Field(primary_key=True)
    subject_id: int
    role: str
    revoked: bool = False
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)


# ── 알림 설정 (담당: 박소정) — NotificationPage 저장용 ──
class NotificationSetting(SQLModel, table=True):
    __tablename__ = "notification_settings"

    patient_id: int = Field(primary_key=True, foreign_key="patients.id")
    medication_reminder_enabled: bool = True
    care_alert_enabled: bool = True
    all_push_enabled: bool = True
    chatbot_name: str = Field(default="약콩이")  # [2026-07-14 추가] 챗봇 표시 이름 — 사용자가 마이페이지에서 변경 가능
    updated_at: datetime = Field(default_factory=datetime.now)


# ── 챗봇 대화 로그 (담당: 김영혜) — 고정 Q&A 방식, schedule_v6 Day6 계획 ──
class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    question_id: str  # 고정 질문 식별자 (q1, q2, q3...)
    question_text: str
    answer_text: str
    created_at: datetime = Field(default_factory=datetime.now)
