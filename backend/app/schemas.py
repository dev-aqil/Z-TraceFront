from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class BatchCreate(BaseModel):
    batch_id: int
    product_name: str
    organization_id: int
    produced_at: datetime
    status: str = "normal"


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
    result: str


class LabResultOut(LabResultCreate):
    model_config = ConfigDict(from_attributes=True)

    lab_result_id: int
