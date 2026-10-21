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
    option_ids: List[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def distinct_options(self):
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("옵션은 중복 선택할 수 없습니다.")
        return self


class OrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    order_mode: Literal["eathere", "takeout"]
    payment_method: Literal["card", "voucher", "counter"] = "counter"
    age_group: Optional[AgeGroup] = None
    items: List[OrderItemInput] = Field(min_length=1, max_length=50)
    quote_id: Optional[UUID] = None

    @model_validator(mode="after")
    def unique_items(self):
        ids = [(item.menu_id, tuple(sorted(item.option_ids))) for item in self.items]
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
    available: bool = True
    stock: Optional[int] = None
    options: List[dict] = Field(default_factory=list)


class MenuList(BaseModel):
    menus: List[Menu]


class Recommendation(MenuList):
    age_group: AgeGroup


class OrderItem(BaseModel):
    menu_id: str
    name: str
    price: int
    qty: int
    options: List[dict] = Field(default_factory=list)


class MenuUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    price: Optional[int] = Field(default=None, strict=True, ge=0, le=1000000)
    available: Optional[bool] = Field(default=None, strict=True)
    stock: Optional[int] = Field(default=None, strict=True, ge=0, le=1000000)
    stock_note: Optional[str] = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def valid_update(self):
        if "stock_note" in self.model_fields_set:
            if "stock" not in self.model_fields_set or not (self.stock_note or "").strip():
                raise ValueError("조정 사유는 stock 변경과 함께 입력하세요.")
        if not self.model_fields_set or any(getattr(self, k) is None for k in self.model_fields_set if k != "stock"):
            raise ValueError("변경할 값을 입력하세요. stock의 null만 무제한을 의미합니다.")
        return self


class OptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=100)
    price: int = Field(strict=True, ge=0, le=1000000)
    available: bool = Field(default=True, strict=True)


class MenuCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    menu_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1, max_length=100)
    price: int = Field(strict=True, ge=0, le=1000000)
    stock: Optional[int] = Field(default=None, strict=True, ge=0, le=1000000)
    available: bool = Field(default=True, strict=True)


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


class HourlyMetrics(BaseModel):
    order_count: int
    paid_order_count: int
    ordered_quantity: int
    sold_quantity: int
    revenue: int


class HourlyMenu(HourlyMetrics):
    menu_id: str
    name: str


class SalesHour(HourlyMetrics):
    hour: int
    menus: List[HourlyMenu]


class HourlySales(BaseModel):
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    basis: Literal["order_created_at"] = "order_created_at"
    start: str
    end: str
    start_hour: int
    end_hour: int
    menu_id: Optional[str]
    totals: HourlyMetrics
    hours: List[SalesHour]


StockReason = Literal["order", "cancel", "owner_adjustment"]


class StockMovement(BaseModel):
    id: int
    menu_id: str
    order_id: Optional[int]
    delta: int
    reason: StockReason
    note: str
    created_at: datetime


class StockMovementList(BaseModel):
    movements: List[StockMovement]
    total: int
    page: int
    page_size: int
