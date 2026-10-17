from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrganizationOut(BaseModel):
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
    temperature: float | None = None
    humidity: float | None = None


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


class OrganizationCreate(BaseModel):
    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    type: Literal["supplier", "factory", "warehouse", "store"]


class ShipmentCreate(BaseModel):
    shipment_id: int = Field(gt=0)
    shipment_code: str = Field(min_length=1, max_length=100, pattern=r"\S")
    batch_id: int
    from_org_id: int
    to_org_id: int
    quantity: float = Field(gt=0, allow_inf_nan=False)
    quantity_unit: str = Field(min_length=1, max_length=40, pattern=r"\S")
    status: Literal["pending", "in_transit", "delivered", "held"] = "pending"
    departed_at: datetime | None = None
    eta: datetime | None = None


class RelationshipCreate(BaseModel):
    parent_batch_id: int
    child_batch_id: int
    quantity_used: float = Field(gt=0, allow_inf_nan=False)


class DecisionCreate(BaseModel):
    batch_ids: list[int] = Field(min_length=1, max_length=20)
    scope: Literal["targeted", "extended"]
    decision: Literal["approved", "rejected"]
    officer: str = Field(min_length=1, max_length=100, pattern=r"\S")
    reason: str = Field(min_length=1, max_length=500, pattern=r"\S")
    analysis_id: str | None = Field(default=None, max_length=100)  # the upload that led to this decision, if any
