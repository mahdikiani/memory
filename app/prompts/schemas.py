"""Promptic Prompt Schemas."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Self

import uuid6
from pydantic import BaseModel, Field, field_validator, model_validator


class BaseEntitySchema(BaseModel):
    """Base entity schema for the promptic."""

    uid: str = Field(
        default_factory=lambda: str(uuid6.uuid7()),
        json_schema_extra={"index": True, "unique": True},
        description="Unique identifier for the entity",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.tz),
        json_schema_extra={"index": True},
        description="Date and time the entity was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.tz),
        json_schema_extra={"index": True},
        description="Date and time the entity was last updated",
    )
    is_deleted: bool = Field(
        default=False,
        description="Whether the entity has been deleted",
    )
    meta_data: dict | None = Field(
        default=None,
        description="Additional metadata for the entity",
    )


class Role(StrEnum):
    """The role of the message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ContentType(StrEnum):
    """The type of the content part."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"


class ModelConfig(BaseModel):
    """The model configuration."""

    temperature: float = 0.1
    top_p: float = 1


class ContentPart(BaseModel):
    """The content part of the message."""

    type: ContentType = Field(
        ContentType.TEXT, description="The type of the content part"
    )
    text: str | None = None
    file_url: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        """Validate the content part."""
        if self.text is None and self.file_url is None:
            raise ValueError("Either text or file_url must be provided")
        return self


class MessageBlock(BaseModel):
    """The message block."""

    role: Role = Field(Role.SYSTEM, description="The role of the message")
    content: str | list[ContentPart]

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, v: str | list[ContentPart]) -> list[ContentPart]:
        """Normalize the content text."""
        if isinstance(v, str):
            return [ContentPart(type=ContentType.TEXT, text=v)]
        return v


class PromptSchema(BaseEntitySchema):
    """The prompt schema from promptic."""

    name: str
    workspace_id: str | None = Field(None, description="The workspace ID")
    tags: list[str] = Field(default_factory=list)
    current_version_id: str | None = Field(
        None, description="اگه مقدار نداشته باشه آخرین نسخه پرونده رو برمی‌گرداند"
    )
    messages: list[MessageBlock] = Field(default_factory=list)
    model_name: str = "google/gemini-2.5-flash"
    params: ModelConfig = Field(default_factory=ModelConfig)
