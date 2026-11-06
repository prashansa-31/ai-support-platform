from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message content cannot be empty")

        return value


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str | None
    role: str
    content: str
    sequence_number: int
    token_count: int
    metadata_json: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class AIAnswerResponse(BaseModel):
    question: MessageResponse
    answer: MessageResponse
