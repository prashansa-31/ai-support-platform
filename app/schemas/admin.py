from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserRole(str, Enum):
    CUSTOMER = "customer"
    SUPPORT = "support"
    ADMIN = "admin"


class AdminUserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("role", "is_active")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Provided fields cannot be null")
        return value
