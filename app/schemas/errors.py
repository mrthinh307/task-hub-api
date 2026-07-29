from typing import Any

from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    type: str


class ErrorContent(BaseModel):
    code: int = Field(
        ge=400,
        le=599,
        description="HTTP status code associated with the error.",
    )
    message: str = Field(description="Human-readable error message.")
    details: (
        dict[str, Any] | list[ValidationErrorDetail] | list[dict[str, Any]] | None
    ) = Field(
        default=None,
        description="Structured context for the error, or null when unavailable.",
    )


class ErrorResponse(BaseModel):
    error: ErrorContent
