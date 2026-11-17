from datetime import datetime, timezone
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

OrganizationType = Literal["supplier", "factory", "warehouse", "store"]  # in supply-chain order
ShipmentStatus = Literal["pending", "in_transit", "delivered", "held"]


def supply_rank(kind: str) -> int:
    """Position in the chain, suppliers first. An unknown type sorts last."""
    order = get_args(OrganizationType)
    return order.index(kind) if kind in order else len(order)


class OrganizationContact(BaseModel):
    """Who to reach about a hold. All optional: many organizations were stored before these existed."""
    registration_no: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320, pattern=r"^\S+@\S+$")
    contact_phone: str | None = Field(default=None, max_length=50)


class OrganizationOut(OrganizationContact):
    model_config = ConfigDict(from_attributes=True)

    organization_id: int
    name: str
    type: str


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: int
    product_name: str
    organization_id: int
    produced_at: datetime
    status: str
    lot_code: str | None = None
    on_hold: bool = False  # under an approved containment decision that has not been lifted


class BatchCreate(BaseModel):
    batch_id: int
    product_name: str
    organization_id: int
    produced_at: datetime
    status: str = "normal"
    lot_code: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"\S")


class SensorReadingCreate(BaseModel):
    shipment_id: int
    timestamp: datetime
    # Bounds catch a broken sensor or a unit mix-up; no food shipment is monitored outside them.
    temperature: float | None = Field(default=None, ge=-60, le=80, allow_inf_nan=False)
    humidity: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @field_validator("timestamp")
    @classmethod
    def as_utc(cls, value: datetime) -> datetime:
        """Stored as naive UTC. A time without a zone is taken as UTC."""
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


class SensorReadingOut(SensorReadingCreate):
    model_config = ConfigDict(from_attributes=True)

    reading_id: int


class LabResultCreate(BaseModel):
    batch_id: int
    tested_at: datetime
    contaminant: str | None = None
    result: Literal["positive", "negative"]


class LabResultOut(LabResultCreate):
    model_config = ConfigDict(from_attributes=True)

    lab_result_id: int


class OrganizationCreate(OrganizationContact):
    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    type: OrganizationType


class ShipmentCreate(BaseModel):
    shipment_id: int = Field(gt=0)
    shipment_code: str = Field(min_length=1, max_length=100, pattern=r"\S")
    batch_id: int
    from_org_id: int
    to_org_id: int
    quantity: float = Field(gt=0, allow_inf_nan=False)
    quantity_unit: str = Field(min_length=1, max_length=40, pattern=r"\S")
    status: ShipmentStatus = "pending"
    departed_at: datetime | None = None
    eta: datetime | None = None


class RelationshipCreate(BaseModel):
    parent_batch_id: int
    child_batch_id: int
    quantity_used: float = Field(gt=0, allow_inf_nan=False)
    quantity_unit: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"\S")


class HoldReleaseCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500, pattern=r"\S")


class DecisionCreate(BaseModel):
    batch_ids: list[int] = Field(min_length=1, max_length=20)
    scope: Literal["targeted", "extended"]
    decision: Literal["approved", "rejected"]  # the officer is the signed-in user, never a name sent by the client
    reason:str = Field(min_length=1, max_length=500, pattern=r"\S")
    analysis_id: str | None = Field(default=None, max_length=100)  # the upload that led to this decision, if any
