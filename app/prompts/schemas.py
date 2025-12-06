"""Promptic Prompt Schemas."""

from enum import StrEnum
from typing import Self

from fastapi_mongo_base.schemas import BaseEntitySchema
from pydantic import BaseModel, Field, field_validator, model_validator


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
