from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # supplier | factory | warehouse | store


class Batch(Base):
    __tablename__ = "batches"

    batch_id = Column(Integer, primary_key=True)
    product_name = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=False)
    produced_at = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="normal")

    organization = relationship("Organization")


class BatchRelationship(Base):
    __tablename__ = "batch_relationships"

    id = Column(Integer, primary_key=True)
    parent_batch_id = Column(Integer, ForeignKey("batches.batch_id"), nullable=False)
    child_batch_id = Column(Integer, ForeignKey("batches.batch_id"), nullable=False)
    quantity_used = Column(Float, nullable=False)


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.batch_id"), nullable=False)
    from_org_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=False)
    to_org_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=False)
    quantity = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending")
    departed_at = Column(DateTime, nullable=True)
    eta = Column(DateTime, nullable=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    reading_id = Column(Integer, primary_key=True)
    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)


class LabResult(Base):
    __tablename__ = "lab_results"

    lab_result_id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.batch_id"), nullable=False)
    tested_at = Column(DateTime, nullable=False)
    contaminant = Column(String, nullable=True)
    result = Column(String, nullable=False)  # positive | negative


class Analysis(Base):
    __tablename__ = "analyses"

    analysis_id = Column(String, primary_key=True)
    dataset_id = Column(String, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)
    findings = Column(JSON, nullable=False)
    distribution = Column(JSON, nullable=False)


class BatchLot(Base):
    """External lot identity without changing the existing batch primary keys."""
    __tablename__ = "batch_lots"
    __table_args__ = (UniqueConstraint("organization_id", "lot_code"),)

    batch_id = Column(Integer, ForeignKey("batches.batch_id"), primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=False)
    lot_code = Column(String, nullable=False)


class ShipmentManifest(Base):
    __tablename__ = "shipment_manifests"
    __table_args__ = (UniqueConstraint("from_org_id", "shipment_code"),)

    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), primary_key=True)
    from_org_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=False)
    shipment_code = Column(String, nullable=False)
    quantity_unit = Column(String, nullable=False)


class SyntheticBatch(Base):
    __tablename__ = "synthetic_batches"

    batch_id = Column(Integer, ForeignKey("batches.batch_id"), primary_key=True)
    scenario = Column(String, nullable=False)
