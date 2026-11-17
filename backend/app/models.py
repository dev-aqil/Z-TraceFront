from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # supplier | factory | warehouse | store
    # Who to reach about a hold. Added after the first release, so all optional (see database.add_missing_columns).
    registration_no = Column(String, nullable=True)  # the premises or company registration number
    address = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)


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
    quantity_unit = Column(String, nullable=True)  # null on links stored before units were recorded


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


class ContainmentDecision(Base):
    """Append-only officer decisions on a trace's containment recommendation. The hold itself is simulated."""
    __tablename__ = "containment_decisions"

    decision_id = Column(Integer, primary_key=True)
    selection = Column(String, nullable=False, index=True)  # sorted batch IDs under investigation, comma-separated
    scope = Column(String, nullable=False)  # targeted | extended
    decision = Column(String, nullable=False)  # approved | rejected
    batch_ids = Column(JSON, nullable=False)
    shipment_ids = Column(JSON, nullable=False)
    officer = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=False)


class HoldRelease(Base):
    """An approved decision holds its lots until an officer lifts it. Decisions themselves are never changed."""
    __tablename__ = "hold_releases"

    decision_id = Column(Integer, ForeignKey("containment_decisions.decision_id"), primary_key=True)
    officer = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=False)


class HoldAcknowledgement(Base):
    """An affected organization confirming it has seen a hold."""
    __tablename__ = "hold_acknowledgements"

    decision_id = Column(Integer, ForeignKey("containment_decisions.decision_id"), primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=False)


class DecisionSource(Base):
    """The upload analysis a decision started from. A separate table so existing decision tables are never altered."""
    __tablename__ = "decision_sources"

    decision_id = Column(Integer, ForeignKey("containment_decisions.decision_id"), primary_key=True)
    analysis_id = Column(String, ForeignKey("analyses.analysis_id"), nullable=False)


class User(Base):
    """A person who signs in. A company user acts for one organization; a regulator has none."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, unique=True)  # stored in lower case
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # regulator | company
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=True)
    failed_logins = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    token_hash = Column(String, primary_key=True)  # SHA-256 of the cookie value; the value itself is never stored
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class Entry(Base):
    """Append-only record of who stored which record, and for which organization they acted at the time."""
    __tablename__ = "entries"
    __table_args__ = (Index("ix_entries_record", "kind", "record_id"),)

    entry_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.organization_id"), nullable=True)  # null: a regulator
    kind = Column(String, nullable=False)  # the table the record is in
    record_id = Column(String, nullable=False)
    entered_at = Column(DateTime(timezone=True), nullable=False)
