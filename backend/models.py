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
- 로그인이 아직 없어서 "본인이 로그인해서 자기 환자를 본다"는 안 됨.
  대신 caregiver_id를 쿼리 파라미터로 넘겨서 "이 보호자가 담당하는 환자 목록"을 조회하는 방식.
- 다대다로 만들어서 "한 보호자가 여러 환자"뿐 아니라 "한 환자를 여러 보호자가 같이 케어"도 커버함.
- 서버 최초 기동 시 테스트용 환자 1명 + 보호자 1명을 자동으로 만들어둠 (database.py의 seed_demo_data 참고)

[7/6 추가 2] 로그인/회원가입 도입 — caregivers에 email/hashed_password 추가
- 환자(Patient)는 앱을 직접 쓰지 않는 케어 대상이라 로그인 계정이 없음.
- 보호자·요양보호사(Caregiver)만 로그인해서 자기가 담당하는 환자 목록을 봄
  (caregiver_id를 쿼리 파라미터로 넘기던 방식 → JWT 토큰에서 caregiver를 구함).
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# ── 환자 [7/6 추가] ──
class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    note: Optional[str] = None  # 특이사항 (예: "치매 초기", "혼자 거주" 등 자유 텍스트)
    phone: Optional[str] = None  # [7/8 추가] 회원가입(SignUp.tsx) 연락처
    email: Optional[str] = None  # [7/8 추가] 회원가입 시 아이디 — 로그인 미구현이라 단순 저장용, unique 제약 없음
    birth_date: Optional[str] = None  # [7/8 추가] 생년월일 (자유 텍스트, 예: "1945.03.15")
    # [7/8 추가] "환자 본인"으로 가입할 때만 채워짐 — 실제 로그인 화면은 아직 없지만
    # Caregiver.hashed_password와 동일한 원칙으로 나중에 로그인 붙일 때 바로 쓸 수 있게 real hash로 저장
    hashed_password: Optional[str] = None
    push_enabled: bool = True  # [7/8 추가] 회원가입 알림 수신 설정 (Caregiver와 동일한 3종)
    sms_enabled: bool = False
    email_opt_in: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


# ── 보호자·요양보호사·단체(기관) 등 [7/6 추가, 7/8 단체 지원 확장] ──
class Caregiver(SQLModel, table=True):
    __tablename__ = "caregivers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    # [7/6 보류] 로그인 붙일 때(auth_router.py)만 채워지는 필드 — 지금은 로그인 없이
    # /caregivers로 그냥 만들 수 있어야 해서 nullable로 둠. 회원가입 화면의 "아이디" 입력이 여기 저장됨.
    email: Optional[str] = Field(default=None, unique=True, index=True)
    hashed_password: Optional[str] = None
    relation_type: str = "guardian"  # guardian / caregiver / life_support_worker / social_worker / organization
    phone: Optional[str] = None  # [7/8 추가] 회원가입 연락처
    birth_date: Optional[str] = None  # [7/8 추가] 생년월일 (자유 텍스트)
    push_enabled: bool = True  # [7/8 추가] 회원가입 "Push 알림 허용" (필수 체크)
    sms_enabled: bool = False  # [7/8 추가] 회원가입 "문자(SMS) 수신 허용" (선택)
    email_opt_in: bool = False  # [7/8 추가] 회원가입 "이메일 수신 허용" (선택, 계정 아이디용 email과는 별개 동의 플래그)
    # [7/8 추가] relation_type == "organization"일 때만 채워지는 단체(기관) 전용 필드들
    org_name: Optional[str] = None  # 기관명
    org_type: Optional[str] = None  # 요양원 / 재가센터 / 협회 / 보건소 / 기타
    business_reg_no: Optional[str] = None  # 사업자등록번호
    manager_name: Optional[str] = None  # 담당자 이름 (name과 별개 — 기관 소속 실무 담당자)
    manager_phone: Optional[str] = None  # 담당자 전화번호
    created_at: datetime = Field(default_factory=datetime.now)


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


# ── 복약 기록 (담당: 박소정) ──
class MedicationLog(SQLModel, table=True):
    __tablename__ = "medication_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(foreign_key="medication_schedules.id")
    status: str = "taken"  # taken(복용) / skipped(건너뜀)
    checked_at: datetime = Field(default_factory=datetime.now)
    note: Optional[str] = None


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
class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patients.id")
    inviter_caregiver_id: Optional[int] = Field(default=None, foreign_key="caregivers.id")
    relation_type: str = "guardian"
    invited_phone: Optional[str] = None
    token: str = Field(unique=True, index=True)
    status: str = "pending"  # pending / accepted / rejected / expired
    created_at: datetime = Field(default_factory=datetime.now)
    accepted_at: Optional[datetime] = None


# ── 알림 설정 (담당: 박소정) — NotificationPage 저장용 ──
class NotificationSetting(SQLModel, table=True):
    __tablename__ = "notification_settings"

    patient_id: int = Field(primary_key=True, foreign_key="patients.id")
    medication_reminder_enabled: bool = True
    care_alert_enabled: bool = True
    all_push_enabled: bool = True
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
