"""Mixins for SurrealDB entities."""

from datetime import datetime, timezone
from enum import IntEnum

from pydantic import BaseModel, Field, field_validator

from db.models import RecordId


class TenantSurrealMixin(BaseModel):
    """Tenant mixin for SurrealDB entities."""

    tenant_id: RecordId = Field(..., description="Tenant ID")


class PermissionEnum(IntEnum):
    """Permission levels for file access control."""

    NONE = 0
    READ = 10
    WRITE = 20
    MANAGE = 30
    DELETE = 40
    OWNER = 100


class PermissionSchema(BaseModel):
    """Schema for file access permissions."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),  # noqa: UP017
        json_schema_extra={"index": True},
        description="Date and time the entity was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),  # noqa: UP017
        json_schema_extra={"index": True},
        description="Date and time the entity was last updated",
    )
    meta_data: dict | None = Field(
        default=None,
        description="Additional metadata for the entity",
    )

    permission: PermissionEnum = Field(default=PermissionEnum.NONE)

    @field_validator("permission", mode="before")
    @classmethod
    def validate_permission(cls, v: str | PermissionEnum) -> PermissionEnum:
        """Validate permission."""
        if isinstance(v, str):
            return PermissionEnum[v.upper()]
        return v

    @property
    def read(self) -> bool:
        """Check if the user has read permission."""
        return self.permission >= PermissionEnum.READ

    @property
    def write(self) -> bool:
        """Check if the user has write permission."""
        return self.permission >= PermissionEnum.WRITE

    @property
    def manage(self) -> bool:
        """Check if the user has manage permission."""
        return self.permission >= PermissionEnum.MANAGE

    @property
    def delete(self) -> bool:
        """Check if the user has delete permission."""
        return self.permission >= PermissionEnum.DELETE

    @property
    def owner(self) -> bool:
        """Check if the user has owner permission."""
        return self.permission >= PermissionEnum.OWNER


class UserPermission(PermissionSchema):
    """User permission model."""

    user_id: str = Field(..., description="User ID")


class GroupPermission(PermissionSchema):
    """Group permission model."""

    group_id: str = Field(..., description="Group ID")


class AuthorizationMixin(BaseModel):
    """Authorization mixin for SurrealDB entities."""

    user_permissions: list[UserPermission] = Field(
        default_factory=list, description="User permissions"
    )
    group_permissions: list[GroupPermission] = Field(
        default_factory=list, description="Group permissions"
    )
    public_permission: PermissionSchema = Field(
        default=PermissionSchema(permission=PermissionEnum.READ),
        description="Public permission",
    )
