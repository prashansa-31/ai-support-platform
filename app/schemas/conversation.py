from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    SCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ConversationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ConversationCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )
    initial_message: str | None = Field(default=None, max_length=10_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Title must not be blank")

        return value

    @field_validator("initial_message")
    @classmethod
    def validate_initial_message(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Initial message cannot be blank")
        return value


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    priority: ConversationPriority | None = None

    @field_validator("status", "priority")
    @classmethod
    def reject_null_updates(cls, value):
        if value is None:
            raise ValueError("Update values cannot be null")
        return value


class ConversationAssignmentUpdate(BaseModel):
    assigned_to_id: str | None


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    assigned_to_id: str | None
    assigned_type: str = "ai"
    title: str
    status: ConversationStatus
    priority: ConversationPriority
    escalation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int
