"""Cart domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CartItem(BaseModel):
    name: str
    qty: int = Field(default=1, ge=1)


class Cart(BaseModel):
    id: str
    items: list[CartItem] = Field(default_factory=list)
