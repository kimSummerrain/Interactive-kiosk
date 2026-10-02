from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AgeGroup = Literal["10_40", "41_50"]
OrderStatus = Literal["pending", "preparing", "completed", "cancelled"]


class OrderItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    menu_id: str = Field(min_length=1, max_length=80)
    qty: int = Field(strict=True, ge=1, le=99)


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    order_mode: Literal["eathere", "takeout"]
    payment_method: Literal["card", "voucher", "counter"] = "counter"
    age_group: Optional[AgeGroup] = None
    items: List[OrderItemInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_items(self):
        ids = [item.menu_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("동일한 메뉴는 하나의 항목으로 합쳐 주세요.")
        return self


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[OrderStatus] = None
    payment_status: Optional[Literal["paid"]] = None

    @model_validator(mode="after")
    def not_empty(self):
        if self.status is None and self.payment_status is None:
            raise ValueError("변경할 상태가 필요합니다.")
        return self


class Menu(BaseModel):
    menu_id: str
    name: str
    price: int
    image: str
    category: Literal["coffee", "smoothie", "tea"]


class MenuList(BaseModel):
    menus: List[Menu]


class Recommendation(MenuList):
    age_group: AgeGroup


class OrderItem(BaseModel):
    menu_id: str
    name: str
    price: int
    qty: int


class Order(BaseModel):
    id: int
    order_number: str
    created_at: datetime
    order_mode: Literal["eathere", "takeout"]
    payment_method: Literal["card", "voucher", "counter"]
    payment_status: Literal["unpaid", "paid"]
    status: OrderStatus
    total: int
    items: List[OrderItem]


class OrderResult(BaseModel):
    result: Literal["OK"] = "OK"
    order: Order


class OrderList(BaseModel):
    orders: List[Order]
    total: int
    page: int
    page_size: int


class SalesMenu(BaseModel):
    menu_id: str
    name: str
    quantity: int
    revenue: int


class SalesDay(BaseModel):
    date: str
    orders: int
    revenue: int


class SalesSummary(BaseModel):
    order_count: int
    paid_count: int
    pending_count: int
    cancelled_count: int
    revenue: int
    daily: List[SalesDay]
    top_menus: List[SalesMenu]
