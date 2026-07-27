from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderBase(BaseModel):
    user_id: int
    product_id: int
    quantity: int = Field(gt=0, default=1)


class OrderCreate(OrderBase):
    pass


class OrderUpdate(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    status: str | None = None


class OrderResponse(OrderBase):
    id: int
    total_price: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
