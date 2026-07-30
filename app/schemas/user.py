from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.enums import UserRole
from app.utils.validators import validate_bcrypt_password_length


class UserProfileResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8)

    model_config = ConfigDict(extra="forbid")

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Full name must not be null")
        normalized = value.strip()
        if not normalized:
            raise ValueError("Full name must not be blank")
        return normalized

    @field_validator("current_password")
    @classmethod
    def reject_null_current_password(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Current password must not be null")
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("New password must not be null")
        return validate_bcrypt_password_length(value)

    @model_validator(mode="after")
    def validate_update_fields(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided")

        password_fields = {"current_password", "new_password"}
        provided_password_fields = password_fields & self.model_fields_set
        if provided_password_fields and provided_password_fields != password_fields:
            raise ValueError(
                "Current password and new password must be provided together"
            )
        return self
