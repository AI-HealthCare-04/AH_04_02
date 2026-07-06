from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class UserRole(StrEnum):
    MEDICATION_SUBJECT = "MEDICATION_SUBJECT"  # 환자
    GUARDIAN = "GUARDIAN"  # 보호자
    CAREGIVER = "CAREGIVER"  # 요양보호사
    LIFE_SUPPORT_WORKER = "LIFE_SUPPORT_WORKER"  # 생활지원사
    SOCIAL_WORKER = "SOCIAL_WORKER"  # 사회복지사


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=40)
    hashed_password = fields.CharField(max_length=128)
    name = fields.CharField(max_length=20)
    gender = fields.CharEnumField(enum_type=Gender)
    role = fields.CharEnumField(enum_type=UserRole)
    birthday = fields.DateField()
    phone_number = fields.CharField(max_length=11)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
