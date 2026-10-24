"""Orders and payment settings (GR-32).

Money comes out as integer minor units plus the ISO currency and the same amount as text
("1598.00"), like the catalogue (GR-31). A request never carries a price: the server reads it
from the catalogue when the order is made. Response field names avoid the words the schema test
reserves for secrets, so the payment settings say whether keys are saved, never what they are.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

MAX_LINES = 50

OrderStatusName = Literal["draft", "awaiting_payment", "paid", "cancelled", "expired"]
OrderSourceName = Literal["inbox", "whatsapp"]
PaymentMethodName = Literal["razorpay", "upi"]


class AddressIn(RequestModel):
    """Where to deliver. Every part is optional (digital orders have none); it is saved as given."""

    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=12)
    country: str | None = Field(default=None, max_length=60)


class AddressOut(ResponseModel):
    name: str | None = None
    phone: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None


class OrderLineIn(RequestModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None  # required when the product has variants
    quantity: int = Field(default=1, ge=1, le=999)


class OrderCreate(RequestModel):
    conversation_id: uuid.UUID
    items: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)
    address: AddressIn | None = None
    note: str | None = Field(default=None, max_length=500)


class OrderLineOut(ResponseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    name: str
    variant_title: str | None = None
    sku: str | None = None
    quantity: int
    unit_price_minor: int
    unit_price: str
    line_total_minor: int
    line_total: str


class OrderContact(ResponseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None


class OrderOut(ResponseModel):
    id: uuid.UUID
    number: int
    status: OrderStatusName
    source: OrderSourceName
    currency: str
    total_minor: int
    total: str
    items: list[OrderLineOut]
    address: AddressOut | None = None
    note: str | None = None
    contact: OrderContact
    conversation_id: uuid.UUID | None = None
    payment_method: PaymentMethodName | None = None
    payment_link_url: str | None = None
    payment_reference: str | None = None
    link_expires_at: datetime | None = None
    paid_at: datetime | None = None
    paid_by_name: str | None = None  # a member, for a UPI order marked paid by hand
    cancelled_at: datetime | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class OrderLimits(ResponseModel):
    entitled: bool  # the plan includes commerce (PD-8: Pro and Max)
    razorpay_ready: bool
    upi_ready: bool


class OrderList(ResponseModel):
    items: list[OrderOut]
    total: int
    limits: OrderLimits


class PaymentRequest(RequestModel):
    method: PaymentMethodName
    send: bool = True  # also send it as a message on the order's conversation


class MarkPaid(RequestModel):
    """For a UPI order: the customer's payment reference, if they shared one."""

    reference: str | None = Field(default=None, max_length=200)


class RazorpayConnect(RequestModel):
    key_id: str = Field(min_length=8, max_length=64, pattern=r"^rzp_(test|live)_[A-Za-z0-9]+$")
    private_key: str = Field(min_length=8, max_length=128)
    webhook_key: str = Field(min_length=8, max_length=128)


class UpiSave(RequestModel):
    vpa: str = Field(min_length=5, max_length=100, pattern=r"^[A-Za-z0-9._-]{2,64}@[A-Za-z]{2,32}$")
    name: str = Field(min_length=1, max_length=60)


class PaymentSettings(ResponseModel):
    entitled: bool
    razorpay_connected: bool
    razorpay_key_id: str | None = None
    razorpay_test_mode: bool = False
    razorpay_error: str | None = None
    webhook_url: str | None = None  # where Razorpay posts; shown once connected
    webhook_events: list[str] = Field(default_factory=list)
    webhook_seen_at: datetime | None = None  # the last signed event we received
    upi_vpa: str | None = None
    upi_name: str | None = None
