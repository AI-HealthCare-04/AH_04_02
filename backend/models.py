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

from core.security import decrypt_pii, encrypt_pii, hash_phone
from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


# ── 환자 [7/6 추가, 7/9 로그인 대상으로 전환 + PII 암호화] ──
class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: int | None = Field(default=None, primary_key=True)
    # [7/9] 평문 name 대신 암호화 저장 — 아래 .name 프로퍼티로 투명하게 암복호화.
    # 기본값 ""은 "Patient(**kwargs) 생성 후 patient.name = ... 로 설정"하는 2단계 생성
    # 패턴을 쓰기 위한 것일 뿐, 실제로 빈 문자열로 남겨두면 안 됨(항상 .name으로 설정).
    name_encrypted: str = Field(default="")
    note: str | None = None  # 특이사항 (예: "치매 초기", "혼자 거주" 등 자유 텍스트)
    phone_encrypted: str | None = None  # [7/8 추가, 7/9 암호화] 회원가입(SignUp.tsx) 연락처
    phone_hash: str | None = Field(default=None, index=True)  # [7/9] 로그인/검색용, 복호화 대상 아님
    # [7/8 추가] 회원가입 시 아이디(이메일/전화번호 둘 다 로그인 식별자로 허용).
    # [2026-07-14] 유니크 제약이 없어서 같은 이메일로 중복 가입이 조용히 허용되던 버그를
    # 고쳤다 — 항상 security.normalize_email()로 정규화한 값만 여기 저장한다는 전제.
    email: str | None = Field(default=None, unique=True, index=True)
    birth_date: str | None = None  # [7/8 추가] 생년월일 (자유 텍스트, 예: "1945.03.15")
    # [2026-07-22 추가] 환자 관리 테이블(PatientManagement.tsx, Figma 목업)의 "성별" 컬럼용 —
    # "male"/"female"만 받는다(가입 화면 select). 민감정보라 name/phone처럼 암호화할지도
    # 고려했으나, 팀 논의 없이 임의로 결정하지 않고 우선 평문 컬럼으로 추가 — 필요시 재검토.
    gender: str | None = None
    # [7/8 추가, 7/9 실제 로그인 대상으로 전환] 환자 본인 계정 비밀번호 — Caregiver.hashed_password와 동일 원칙
    hashed_password: str | None = None
    push_enabled: bool = True  # [7/8 추가] 회원가입 알림 수신 설정 (Caregiver와 동일한 3종)
    sms_enabled: bool = False
    email_opt_in: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    # [2026-07-15 추가, REQ-039] 로그인 실패 추적 + 계정 잠금. 5회 실패 시 locked_at이
    # 채워지고, 잠긴 동안은 비밀번호가 맞아도 로그인이 거부된다(비밀번호 재설정으로만 해제).
    failed_login_attempts: int = Field(default=0)
    locked_at: datetime | None = None
    # [2026-07-15 추가, REQ-035] 회원 탈퇴 — 즉시 비활성화하고 30일 뒤 실제 삭제(purge
    # 스크립트가 처리). deactivated_at이 채워지면 로그인 자체가 막힌다. 30일 안에는
    # withdraw/cancel로 취소 가능(둘 다 None으로 되돌림).
    deactivated_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None
    # [2026-07-16 추가] 회원가입 직후 자가진단 설문(식사 시간) — MedicationSchedule의
    # dose_timing(식전/식후) 알림 시각을 정할 때 이 식사 시간을 기준으로 삼기 위함.
    # time_slot과 동일한 관례로 "HH:MM" 문자열, 시간 자체를 안 채우면 None.
    breakfast_time: str | None = None
    breakfast_regular: bool | None = None
    lunch_time: str | None = None
    lunch_regular: bool | None = None
    dinner_time: str | None = None
    dinner_regular: bool | None = None
    # [2026-07-20 추가, REQ-007a] 보호자 연결 권유 안내를 사용자가 마지막으로 닫은 시각.
    # None이거나 기록된 시각 + 30일 < now()이면 "지금 안내를 표시해야 한다"고 판단.
    # 서비스 차단 없이 안내만 표시하는 용도 — should_alert_now는 API에서 계산해 반환.
    caregiver_alert_dismissed_at: datetime | None = Field(default=None)

    @property
    def name(self) -> str:
        return decrypt_pii(self.name_encrypted)

    @name.setter
    def name(self, value: str) -> None:
        self.name_encrypted = encrypt_pii(value)

    @property
    def phone(self) -> str | None:
        return decrypt_pii(self.phone_encrypted) if self.phone_encrypted else None

    @phone.setter
    def phone(self, value: str | None) -> None:
        if value:
            self.phone_encrypted = encrypt_pii(value)
            self.phone_hash = hash_phone(value)
        else:
            self.phone_encrypted = None
            self.phone_hash = None


# ── 보호자·요양보호사·단체(기관) 등 [7/6 추가, 7/8 단체 지원 확장, 7/9 PII 암호화] ──
class Caregiver(SQLModel, table=True):
    __tablename__ = "caregivers"

    id: int | None = Field(default=None, primary_key=True)
    name_encrypted: str = Field(default="")  # [7/9] Patient.name_encrypted와 동일한 원칙 — .name 프로퍼티 참고
    # [2026-07-23 수정] 같은 사람이 보호자(가족)이면서 동시에 기관(요양보호사 등) 소속일
    # 수 있어(phone_hash와 동일한 이유), 테이블 전체 유니크 대신 relation_type끼리만
    # 중복을 막는다 — 실제 검사는 monitoring_router.py 애플리케이션 레벨에서 한다.
    email: str | None = Field(default=None, index=True)  # 회원가입 화면의 "아이디" 입력이 여기 저장됨
    hashed_password: str | None = None
    # 직접 가입(routers/monitoring_router.py CaregiverCreate)은 guardian/organization만
    # 허용하고, 보호자 초대(routers/care_router.py InvitationCreate)는 Connect.tsx UI에 맞춰
    # guardian/caregiver/life_support_worker/social_worker를 허용한다. DB 컬럼 자체는 그냥
    # VARCHAR라 여기서는 강제 안 되므로, 각 입력 스키마에서 Literal로 검증한다.
    relation_type: str = "guardian"
    phone_encrypted: str | None = None  # [7/8 추가, 7/9 암호화] 회원가입 연락처
    phone_hash: str | None = Field(default=None, index=True)  # [7/9] 로그인/검색용, 복호화 대상 아님
    birth_date: str | None = None  # [7/8 추가] 생년월일 (자유 텍스트)
    push_enabled: bool = True  # [7/8 추가] 회원가입 "Push 알림 허용" (필수 체크)
    sms_enabled: bool = False  # [7/8 추가] 회원가입 "문자(SMS) 수신 허용" (선택)
    email_opt_in: bool = False  # [7/8 추가] 회원가입 "이메일 수신 허용" (선택, 계정 아이디용 email과는 별개 동의 플래그)
    # [7/8 추가] relation_type == "organization"일 때만 채워지는 단체(기관) 전용 필드들
    org_name: str | None = None  # 기관명
    org_type: str | None = None  # 요양원 / 재가센터 / 협회 / 보건소 / 기타
    business_reg_no: str | None = None  # 사업자등록번호
    # [7/9] manager_name/manager_phone(기관 소속 실무 담당자 연락처)은 로그인 계정 본인의 PII가
    # 아니라 부가 정보라 이번 암호화 범위에서는 뺐음 — 필요하면 팀 논의 후 별도로 암호화 추가.
    manager_name: str | None = None  # 담당자 이름 (name과 별개 — 기관 소속 실무 담당자)
    manager_phone: str | None = None  # 담당자 전화번호
    created_at: datetime = Field(default_factory=datetime.now)
    # [2026-07-15 추가, REQ-039] Patient와 동일한 로그인 잠금 원칙 — 아래 Patient 클래스 참고.
    failed_login_attempts: int = Field(default=0)
    locked_at: datetime | None = None
    # [2026-07-15 추가, REQ-035] Patient와 동일한 탈퇴·유예삭제 원칙 — 아래 Patient 클래스 참고.
    deactivated_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None

    @property
    def name(self) -> str:
        return decrypt_pii(self.name_encrypted)

    @name.setter
    def name(self, value: str) -> None:
        self.name_encrypted = encrypt_pii(value)

    @property
    def phone(self) -> str | None:
        return decrypt_pii(self.phone_encrypted) if self.phone_encrypted else None

    @phone.setter
    def phone(self, value: str | None) -> None:
        if value:
            self.phone_encrypted = encrypt_pii(value)
            self.phone_hash = hash_phone(value)
        else:
            self.phone_encrypted = None
            self.phone_hash = None


# ── 보호자-환자 연결 (다대다) [7/6 추가] ──
class CaregiverPatient(SQLModel, table=True):
    __tablename__ = "caregiver_patients"

    id: int | None = Field(default=None, primary_key=True)
    caregiver_id: int = Field(foreign_key="caregivers.id")
    patient_id: int = Field(foreign_key="patients.id")
    created_at: datetime = Field(default_factory=datetime.now)
    # [2026-07-20 추가, REQ-004] 연결 해제 상태 관리
    # active: 정상 연결 / revocation_pending: third_party_needed 환자의 해제 승인 대기
    # / revoked: 해제 완료
    status: str = Field(default="active")
    revoked_at: datetime | None = Field(default=None)
    # revocation_requested_by: 요청자 ID (caregiver일 때는 caregivers.id, patient일 때는 patients.id)
    # FK를 caregivers.id로 고정하면 환자 요청을 표현 못 해서 FK 없이 앱 레벨 검증만 사용한다.
    revocation_requested_by: int | None = Field(default=None)
    # requested_by_role: 요청자가 caregiver인지 patient인지 구분 — 자기승인 가드에 사용
    requested_by_role: str | None = Field(default=None)  # "caregiver" | "patient"
    # [2026-07-23 추가] 기관이 연결을 끊을 때 반드시 남겨야 하는 사유 — 환자/보호자가 승인
    # 여부를 판단하는 근거가 된다.
    revocation_reason: str | None = Field(default=None)
    # [2026-07-23 추가] 승인 대기 시작 시각 — 2주(14일) 안에 상대가 응답하지 않으면 요청자가
    # 스스로 확정(자동 승인)할 수 있게 하는 타임아웃 기준점.
    revocation_requested_at: datetime | None = Field(default=None)


# [2026-07-23 추가, 2026-07-24 확장] 환자-보호자 관계에 생긴 일(연결/해제/해제 요청 처리 결과)을
# 상대에게 알려주는 용도. CaregiverPatient 링크 자체는 해제 승인 시 revoked(요청자가 그 환자에
# 대한 접근권을 잃을 수 있음), 거부 시 revocation_requested_by 등이 지워지므로 결과를 별도로
# 스냅샷 남겨야 나중에도 확인할 수 있다. patient_name/counterpart_name은 접근권 상실·개인정보
# 변경에 영향받지 않도록 그 시점 값을 복사해서 저장한다.
# [2026-07-24 추가] 처음엔 "해제 요청 승인/거부 결과"만 다뤘지만(RevocationNotice, approved: bool),
# 연결이 새로 생기거나(초대 수락) 기관 승인 절차 없이 즉시 해제될 때도 상대에게 알림이 필요해져서
# event 필드로 일반화했다 — "linked" | "unlinked" | "revocation_approved" | "revocation_rejected".
class RelationNotice(SQLModel, table=True):
    __tablename__ = "revocation_notices"

    id: int | None = Field(default=None, primary_key=True)
    recipient_role: str  # "caregiver" | "patient"
    recipient_id: int
    patient_id: int
    patient_name: str
    counterpart_name: str  # 상대(연결/해제/승인·거부를 한 사람)의 이름
    event: str  # "linked" | "unlinked" | "revocation_approved" | "revocation_rejected"
    reason: str | None = None  # revocation 계열에서만 채워짐(기관이 남긴 해제 사유)
    created_at: datetime = Field(default_factory=datetime.now)
    read_at: datetime | None = None


# ── 비밀번호 재설정 임시코드 [2026-07-15 추가, REQ-039] ──
# Patient/Caregiver 둘 다 로그인 대상이라 subject_type으로 구분한다(다형 참조) — FK를
# 어느 한쪽 테이블로 고정할 수 없어 애플리케이션 레벨에서만 유효성을 검증한다.
class PasswordResetCode(SQLModel, table=True):
    __tablename__ = "password_reset_codes"

    id: int | None = Field(default=None, primary_key=True)
    subject_type: str  # "patient" | "caregiver"
    subject_id: int = Field(index=True)
    code_hash: str = Field(index=True)  # HMAC-SHA256(정규화된 임시번호) — 평문 저장 안 함
    expires_at: datetime  # 발급 후 10분
    used_at: datetime | None = None  # 채워지면 재사용 불가
    # [2026-07-15 추가] 팀원 리뷰(PR #48)에서 지적된 무제한 시도 문제 수정 — 이 코드로
    # /password-reset/verify를 시도한 횟수. MAX_RESET_CODE_VERIFY_ATTEMPTS(auth_router.py)
    # 넘으면 코드를 강제로 무효화(used_at 채움)해서 브루트포스를 막는다.
    attempts: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)


# ── 회원 탈퇴 감사기록 [2026-07-15 추가, REQ-035] ──
# 이름·전화번호 등 실제 PII는 담지 않는 비식별 기록 — subject_id만 참조하고, 개인정보가
# 실제로 삭제된 뒤(completed)에도 이 행 자체는 증빙으로 계속 보존한다.
class PrivacyPurgeAudit(SQLModel, table=True):
    __tablename__ = "privacy_purge_audits"

    id: int | None = Field(default=None, primary_key=True)
    subject_type: str  # "patient" | "caregiver"
    subject_id: int = Field(index=True)
    requested_at: datetime = Field(default_factory=datetime.now)
    deactivated_at: datetime
    scheduled_purge_at: datetime  # deactivated_at + 30일 — purge 스크립트가 이 값 기준으로 찾음
    status: str = Field(default="pending")  # pending / completed / cancelled
    completed_at: datetime | None = None


# ── 업로드 원본 단위 (1건의 처방전 사진 = 1행) ──
class MedicalRecord(SQLModel, table=True):
    __tablename__ = "medical_records"

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")  # [7/6 추가] 이 처방전이 누구 것인지
    image_path: str  # 저장된 이미지 파일 경로
    status: str = Field(default="processing")  # processing / review_required / completed / failed
    # [2026-07-16] MySQL은 SQLModel의 기본 str 컬럼을 varchar(255)로 만들어서, 실제 OCR
    # 원문(255자를 쉽게 넘김)을 저장할 때 "Data too long" 에러로 처방전 인식이 통째로
    # 실패했다 — SQLite는 길이 제한이 없어 로컬 테스트에서는 안 보였던 버그.
    raw_text: str | None = Field(default=None, sa_column=Column(Text))  # OCR 원문 (완료 후 기록)
    failure_reason: str | None = None  # 실패 시 사유
    created_at: datetime = Field(default_factory=datetime.now)
    # [7/9 추가] 보호자가 대신 업로드한 경우에만 채워짐 — 본인이 직접 올렸으면 None
    uploaded_by_caregiver_id: int | None = Field(default=None, foreign_key="caregivers.id")
    # [2026-07-16 추가] 등록내역 삭제 기능 — PatientMedication.deleted_at과 동일한 soft-delete
    # 관례. OCR·가이드 등 연결 데이터를 실제로 지우지 않고 목록/조회에서만 감춘다.
    deleted_at: datetime | None = Field(default=None)
    # [2026-07-21 추가] 등록내역 목록에서 즐겨찾기처럼 위쪽에 고정하는 기능.
    pinned: bool = False
    # [2026-07-23 추가] raw_text에서 뽑아낸 조제일자("YYYY-MM-DD") — 재처방인지(같은 약,
    # 다른 날짜) 판단하는 근거. 날짜를 못 찾으면 None(기존처럼 이름만으로 중복 판정).
    prescription_date: str | None = Field(default=None)


# ── OCR 추출 결과 (약품 1개 = 1행, 담당: 권순현) ──
class OcrResult(SQLModel, table=True):
    __tablename__ = "ocr_results"

    id: int | None = Field(default=None, primary_key=True)
    record_id: int = Field(foreign_key="medical_records.id")
    drug_name: str
    drug_code: str = ""  # [7/6 추가] HIRA 약가마스터 매칭용 코드 (ocr_interface.py의 OCRResult와 동기화)
    dosage: str = ""       # 미인식이면 빈 문자열 (1회 복용량 — 예: "1정", "2캡슐". mg 등 성분 함량은 drug_name에 있음)
    frequency: str = ""    # 1일 투여횟수 (예: "1일 3회")
    total_days: str = ""   # [2026-07-18 추가] 총 투약일수 (예: "30일")
    diagnosis: str = ""
    drug_class: str = ""
    confidence: float = 0.0  # 0.0 ~ 1.0
    review_required: bool = False  # [7/6 추가] confidence 낮아서 보호자 확인 필요한지
    user_confirmed: bool = False
    matched_drug_name: str = ""    # drug_matcher: 기준 약품명 목록에서 가장 유사한 이름
    match_score: float = 0.0       # drug_matcher: SequenceMatcher 유사도 (0~1)
    needs_review: bool = False     # drug_matcher: match_score < 0.7 이면 True (review_required와 별개)

    @property
    def display_name(self) -> str:
        """화면 표시·RAG/DUR 조회에 쓸 이름 — 확신 있게 매칭됐으면(matched_drug_name,
        needs_review=False) 그 정확한 전체명을, 아니면 원문(drug_name)을 그대로 쓴다.
        drug_name/matched_drug_name 자체의 의미는 그대로 유지하고(원문 vs 매칭명 분리),
        "어느 걸 보여줄지"만 이 한 곳에서 판단해 records_router.py/rag_router.py가
        각자 다른 규칙을 쓰는 걸 막는다."""
        if self.matched_drug_name and not self.needs_review:
            return self.matched_drug_name
        return self.drug_name


# ── RAG 가이드 결과 (담당: 김영혜) ──
class GuideResult(SQLModel, table=True):
    __tablename__ = "guide_results"

    id: int | None = Field(default=None, primary_key=True)
    record_id: int = Field(foreign_key="medical_records.id")
    # SQLite엔 JSON 타입이 없어서 문자열로 저장: json.dumps()로 넣고 json.loads()로 꺼냄
    # [2026-07-16] raw_text와 동일한 이유로 Text 명시 — 기본 str이면 MySQL에서 varchar(255)가
    # 되어 실제 가이드 JSON(255자를 훨씩 넘김) 저장이 실패/잘림. 어제 멘토링에서 나온
    # "가이드 콘텐츠가 부족하다"는 문제의 원인 중 하나였을 가능성이 높다.
    medication_guide: str = Field(sa_column=Column(Text, nullable=False))
    lifestyle_guide: str = Field(sa_column=Column(Text, nullable=False))
    source_refs: str = Field(default="[]", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.now)


# ── 복약 일정 (담당: 박소정, 멘토 최우선 지정) ──
class MedicationSchedule(SQLModel, table=True):
    __tablename__ = "medication_schedules"

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")  # [7/6 변경] 고정값 1 → 실제 환자 FK
    drug_name: str
    time_slot: str  # [7/8 변경] "08:00" 같은 실제 시각 문자열 (기존 "아침"/"점심"/"저녁"에서 변경)
    dose_timing: str | None = None  # [7/8 추가] 복용상태: 공복/아침 식후/점심 식전/점심 식후/저녁 식전/저녁 식후
    caregiver_alert: bool = True  # [7/8 추가] 이 일정 알림을 보호자에게도 보낼지
    memo: str | None = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    # [2026-07-14 추가] patient_medications 도입 이후 새 일정은 여기로 연결한다. 기존
    # /monitoring/schedules 플로우(drug_name 자유 텍스트, patient_medication_id 없음)는
    # 전혀 안 건드리고 전부 nullable로만 추가 — 과거 데이터도 그대로 유효하다.
    patient_medication_id: int | None = Field(
        default=None, foreign_key="patient_medications.id", index=True
    )
    meal_relation: str | None = None  # 식전 / 식후 / 취침 전 등
    instructions: str | None = None
    timezone: str | None = None
    # JSON 배열 문자열(예: '["mon","wed","fri"]') — SQLite엔 JSON 타입이 없어 문자열로 저장
    # (guide_results.source_refs와 동일한 관례).
    days_of_week: str | None = None
    # [2026-07-20 추가] 처방전에서 자동 생성된 일정(records_router.py의 _create_schedules_
    # from_ocr)만 이 값을 채운다 — 처방전을 soft-delete할 때 관련 일정도 같이 비활성화하기
    # 위해 필요(안 그러면 삭제한 처방전의 약이 대시보드/알림에 계속 남는다). monitoring_router.py
    # 로 직접 만든 일정은 처방전과 무관하니 그대로 None.
    record_id: int | None = Field(default=None, foreign_key="medical_records.id", index=True)


# [2026-07-24 추가] 이 일정의 알림을 받을 보호자를 일정별로 명시적으로 골라둔다 —
# 예전엔 caregiver_alert=True면 "환자와 연결된 caregiver 중 가장 먼저 연결된 1명"에게만
# 갔다(core/scheduler.py._recipients 참고, 실제 주/부 보호자 구분이 없어 생긴 임의의
# 단순화였음) — 2번째·3번째로 연결된 보호자·지원인력에게는 애초에 안 갔고, 화면 라벨
# "보호자에게도 알림"도 실제로 누가 받는지 보여주지 못했다. 이 테이블에 행이 있으면
# 그 caregiver_id들에게만, 행이 하나도 없으면(과거 데이터·아직 이 화면을 안 거친 일정)
# 이 환자와 연결된 caregiver 전원에게 보낸다(안전한 방향의 기본값 — 아무도 못 받는
# 것보다 전원이 받는 게 낫다는 판단). schedule.caregiver_alert가 False면 이 테이블과
# 무관하게 아무에게도 안 감(기존 kill switch 그대로 유지).
class ScheduleCaregiverAlert(SQLModel, table=True):
    __tablename__ = "schedule_caregiver_alerts"

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="medication_schedules.id", index=True)
    caregiver_id: int = Field(foreign_key="caregivers.id", index=True)


# ── 복약 기록 (담당: 박소정) ──
class MedicationLog(SQLModel, table=True):
    __tablename__ = "medication_logs"

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="medication_schedules.id")
    status: str = "taken"  # taken(복용) / skipped(건너뜀)
    checked_at: datetime = Field(default_factory=datetime.now)
    note: str | None = None
    # [7/9 추가] 이 체크를 누가 했는지 — 환자 본인(patient) vs 보호자 대신(caregiver)
    confirmed_by_type: str = "patient"
    confirmed_by_caregiver_id: int | None = Field(default=None, foreign_key="caregivers.id")


# ── 복약 알림 발송 기록 [2026-07-19 추가, REQ-026a/007/026c/026d, 담당: 김영혜] ──
# core/scheduler.py의 인프로세스 스케줄러가 매 tick마다 "이 스케줄이 이 시각에 이미
# 처리됐는지"를 판단하는 기준. UniqueConstraint가 실제 중복 방지 장치다 — 서버가
# 재시작되거나(놓친 tick 따라잡기용 유예 윈도우 있음), 팀원 여러 명이 각자 로컬에서
# 서버를 띄워 같은 공유 DB를 보더라도(shared-dev-db-setup.md), 같은
# (schedule_id, due_date, time_slot, kind) 조합은 DB 유니크 제약이 막아줘서 한 번만
# 처리된다 — 스케줄러 자체의 "정확히 한 번" 보장이 아니라 DB가 최종 중재자.
# kind를 제약에 포함한 이유: 같은 스케줄/같은 날 "reminder"(정시 알림)와 "missed"
# (놓침 판정)가 서로 다른 사건이라 둘 다 한 번씩은 남아야 한다.
class NotificationLog(SQLModel, table=True):
    __tablename__ = "notification_logs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "due_date", "time_slot", "kind", name="uq_notification_instance"),
    )

    id: int | None = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="medication_schedules.id", index=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    due_date: str = Field(index=True)  # "2026-07-19" — date.isoformat(), MedicationLog와 동일 관례
    time_slot: str  # 발생 시점의 schedule.time_slot 스냅샷 (나중에 스케줄이 바뀌어도 기록은 안 바뀜)
    kind: str = "reminder"  # reminder(정시 알림) / missed(놓침 판정)
    # [2026-07-19] "성공적으로 보냈다"와 "이 스케줄은 알림이 꺼져 있어서 일부러 안 보냈다"를
    # 구분해야 한다 — NotificationSetting.medication_reminder_enabled가 꺼져 있으면
    # suppressed로 남기고 이메일은 실제로 보내지 않는다(사용자가 끈 알림을 무시하고
    # 보내면 REQ-026a의 opt-out을 어기는 것이 된다).
    status: str = "pending"  # pending / sent / suppressed / failed
    channels: str = "[]"  # JSON 배열, 예: '["inapp","email:patient","email:caregiver:3"]'
    fired_at: datetime = Field(default_factory=datetime.now)
    acknowledged_at: datetime | None = None  # 환자가 인앱 알림을 확인 처리하면 채워짐


# ── 환자 의약품 등록 [2026-07-14 추가, 담당: 김영혜] ──
# 여러 로컬 개발 환경이 공통 DB를 쓰도록 정리하면서 함께 요청된 기능 — "환자가 입력한
# 의약품"을 OCR 파이프라인(medical_records/ocr_results)과 별개로 등록/조회할 수 있게 한다.
# OcrResult(review_required/user_confirmed/matched_drug_name/match_score)와 동일한 원칙:
# AI/OCR이 추정한 값과 사용자가 최종 확인한 값을 한 행에서 덮어쓰지 않고 함께 보존한다.
class PatientMedication(SQLModel, table=True):
    __tablename__ = "patient_medications"

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id", index=True)
    # 의약품 마스터 테이블 자체가 이 프로젝트에 아직 없다(rag/의 CSV·정부 API 실시간 조회로
    # 대체 중 — CONTRACT.md 참고). 그래서 FK를 걸 대상이 없어 drug_id는 제약 없는 컬럼으로
    # 남겨둔다 — 나중에 마스터 테이블이 생기면 그때 foreign_key를 추가한다. 검색 결과가
    # 하나로 확정되지 않으면 drug_id/item_seq를 null로 두고 원문(source_raw_text)만 남긴다.
    drug_id: int | None = Field(default=None, index=True)
    item_seq: str | None = Field(default=None, index=True)  # 식약처 품목일련번호
    product_code: str | None = None
    medication_name: str  # 환자가 최종 확인한 의약품명 (확정 데이터 — 필수)
    manufacturer_name: str | None = None
    dosage_amount: str | None = None
    dosage_unit: str | None = None  # 정 / 캡슐 / mL 등
    frequency_per_day: int | None = None
    administration_route: str | None = None  # 경구 등
    start_date: str | None = None
    end_date: str | None = None
    prescription_id: int | None = Field(default=None, foreign_key="medical_records.id")
    source_type: str = "manual"  # manual / prescription_ocr / pill_image / api_search
    # AI/OCR이 맨 처음 추출한 원문 그대로 — medication_name(사용자 확정값)과 절대 덮어쓰지
    # 않고 나란히 보존해서, 나중에 "AI가 뭐라고 봤었는지" 추적 가능하게 한다.
    source_raw_text: str | None = None
    verification_status: str = "unverified"  # unverified / matched / user_confirmed / pharmacist_confirmed
    is_active: bool = True  # 현재 복용 여부
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    deleted_at: datetime | None = None  # soft delete (DELETE API가 실제로 지우지 않고 여기만 채움)


# ── 실제 복약 수행 기록 [2026-07-14 추가, 담당: 김영혜] ──
# MedicationLog(기존, MedicationSchedule.schedule_id 필수)와 별개 테이블 — 기존 스케줄
# 체크인 플로우는 그대로 두고, patient_medications 기반의 새 등록/기록 플로우를 위해 추가.
class MedicationRecord(SQLModel, table=True):
    __tablename__ = "medication_records"

    id: int | None = Field(default=None, primary_key=True)
    # [2026-07-20 변경] OCR 기반 스케줄은 PatientMedication이 없으므로 nullable —
    # schedule_id와 patient_medication_id 중 최소 하나는 있어야 한다(불변식, DB 레벨 제약은 아님).
    patient_medication_id: int | None = Field(
        default=None, foreign_key="patient_medications.id", index=True
    )
    schedule_id: int | None = Field(default=None, foreign_key="medication_schedules.id")
    scheduled_at: datetime | None = None
    taken_at: datetime | None = None  # 실제 복용 시간, 아직 안 먹었으면 None
    status: str = "scheduled"  # scheduled / taken / missed / skipped / duplicate_suspected
    verification_method: str = "self_report"  # self_report / caregiver / photo / device
    evidence_image_url: str | None = None
    memo: str | None = None
    # [2026-07-20 추가] MedicationLog와 동일한 필드명/타입 — 체크인 기록을 이 테이블로
    # 일원화하면서 "누가 체크했는지"(환자 본인 patient vs 보호자 대신 caregiver)를 보존한다.
    confirmed_by_type: str | None = None
    confirmed_by_caregiver_id: int | None = Field(default=None, foreign_key="caregivers.id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ══════════════════════════════════════════════════════════
# [7/7 추가] Figma 화면 전체 연결을 위한 신규 테이블
# ══════════════════════════════════════════════════════════

# ── 보호자 초대 (담당: 박소정) — CaregiverPage/InvitePage 실제 연동용 ──
# [2026-07-15] 보안 검토 반영: 토큰 원문 대신 해시 저장(token_hash), 만료시각 추가(expires_at),
# invited_phone도 다른 PII와 동일하게 암호화(.invited_phone 프로퍼티로 투명하게 암복호화).
class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: int | None = Field(default=None, primary_key=True)
    # 보호자→환자 초대(relation_type="patient")는 아직 환자 계정이 없어 nullable — 수락 시점에 채워진다.
    patient_id: int | None = Field(default=None, foreign_key="patients.id")
    inviter_caregiver_id: int | None = Field(default=None, foreign_key="caregivers.id")
    relation_type: str = "guardian"
    invited_phone_encrypted: str | None = None
    # [2026-07-22 추가] 로그인한 보호자/기관이 "받은 초대" 목록을 조회할 때 자기 전화번호로
    # 찾아야 하는데, invited_phone_encrypted(Fernet)는 암호화할 때마다 값이 달라져 WHERE로
    # 못 찾는다 — Caregiver/Patient.phone과 동일하게 조회용 해시를 별도로 둔다.
    invited_phone_hash: str | None = Field(default=None, index=True)
    token_hash: str = Field(unique=True, index=True)
    status: str = "pending"  # pending / accepted / rejected / expired
    created_at: datetime = Field(default_factory=datetime.now)
    accepted_at: datetime | None = None
    expires_at: datetime | None = None

    @property
    def invited_phone(self) -> str | None:
        return decrypt_pii(self.invited_phone_encrypted) if self.invited_phone_encrypted else None

    @invited_phone.setter
    def invited_phone(self, value: str | None) -> None:
        self.invited_phone_encrypted = encrypt_pii(value) if value else None
        self.invited_phone_hash = hash_phone(value) if value else None

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

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    question_id: str  # 고정 질문 식별자 (q1, q2, q3...)
    question_text: str
    answer_text: str
    created_at: datetime = Field(default_factory=datetime.now)


# ── 가이드 결과 캐시 (REQ-020) ──
# 진단명·약물조합·출처 데이터 버전을 SHA-256 해시로 캐시 키를 만들어,
# 동일 조합의 반복 요청에서 LLM 재호출 없이 저장된 결과를 반환한다.
# TTL = 7일(기본). data_version 변경 시 사실상 새 키가 생성돼 구 캐시는 자연 만료된다.
class GuideCache(SQLModel, table=True):
    __tablename__ = "guide_cache"

    id: int | None = Field(default=None, primary_key=True)
    # SHA-256(diagnosis + "|" + sorted drug_names + "|" + data_version)
    cache_key: str = Field(unique=True, index=True)
    diagnosis: str | None = None
    drug_names: str = Field(default="[]", sa_column=Column(Text))  # JSON 배열
    data_version: str
    # (medication_guide, lifestyle_guide, source_refs) 튜플을 JSON 직렬화해 저장
    guide_result: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime


# ── 변경 이력 (REQ-081) ──
# 복약 일정·환자 정보를 보호자가 수정할 수 있어서, "어제 8시였던 게 왜 9시로 바뀌었는지"
# 환자가 확인할 방법이 있어야 한다는 요구로 추가했다(최소 버전 — 조회 화면은 아직 없고
# 테이블·기록만 남긴다). name/phone처럼 암호화 저장되는 PII는 before/after에 실제 값
# 대신 "***"만 남긴다 — 이 테이블은 name_encrypted 같은 암호화 보호가 없어서, 그대로
# 남기면 오히려 새로운 평문 PII 유출 경로가 된다(core/audit.py의 SENSITIVE_FIELDS 참고).
class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    table_name: str = Field(index=True)
    record_id: int = Field(index=True)
    actor_id: int
    actor_role: str  # "caregiver" | "patient"
    action: str = "update"
    before: str | None = Field(default=None, sa_column=Column(Text))  # JSON
    after: str | None = Field(default=None, sa_column=Column(Text))  # JSON
    created_at: datetime = Field(default_factory=datetime.now)
