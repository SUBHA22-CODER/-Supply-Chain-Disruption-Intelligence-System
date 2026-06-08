import os
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TIMESTAMP

from database import IS_SQLITE

Base = declarative_base()

# Dynamic Type Mapping based on database engine
if IS_SQLITE:
    UUID_TYPE = String
    JSON_TYPE = JSON
    ARRAY_TYPE = JSON  # SQLite stores arrays as JSON arrays
    GEOMETRY_TYPE = String  # SQLite stores geom as WKT or simple string
else:
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB, ARRAY as PG_ARRAY
    from geoalchemy2 import Geometry as PG_Geometry
    UUID_TYPE = PG_UUID(as_uuid=True)
    JSON_TYPE = PG_JSONB
    ARRAY_TYPE = PG_ARRAY(PG_UUID(as_uuid=True))
    GEOMETRY_TYPE = PG_Geometry(geometry_type='POINT', srid=4326)

class SupplierNode(Base):
    __tablename__ = "supplier_nodes"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()) if IS_SQLITE else uuid.uuid4())
    name = Column(String, nullable=False)
    country = Column(String, nullable=False)
    tier = Column(Integer, nullable=False) # 1-3
    reliability_score = Column(Float, nullable=True)
    geom = Column(GEOMETRY_TYPE, nullable=True)
    metadata_col = Column('metadata', JSON_TYPE, nullable=True)

    sku_links = relationship("SupplierSKULink", back_populates="supplier")

class SKUCatalog(Base):
    __tablename__ = "sku_catalog"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()) if IS_SQLITE else uuid.uuid4())
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    criticality_score = Column(Float, nullable=False)

    supplier_links = relationship("SupplierSKULink", back_populates="sku")

class SupplierSKULink(Base):
    __tablename__ = "supplier_sku_links"

    supplier_id = Column(UUID_TYPE, ForeignKey("supplier_nodes.id"), primary_key=True)
    sku_id = Column(UUID_TYPE, ForeignKey("sku_catalog.id"), primary_key=True)
    lead_time_days = Column(Integer, nullable=False)
    capacity_units = Column(Integer, nullable=False)

    supplier = relationship("SupplierNode", back_populates="sku_links")
    sku = relationship("SKUCatalog", back_populates="supplier_links")

class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()) if IS_SQLITE else uuid.uuid4())
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False)
    event_type = Column(String, nullable=False)
    severity = Column(Float, nullable=False) # 0-1
    affected_supplier_ids = Column(ARRAY_TYPE, nullable=False)
    predicted = Column(Boolean, nullable=False, default=False)
    agent_action = Column(String, nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)

class RiskSignal(Base):
    __tablename__ = "risk_signals"

    supplier_id = Column(UUID_TYPE, primary_key=True)
    timestamp = Column(TIMESTAMP(timezone=True), primary_key=True)
    signal_type = Column(String, primary_key=True)
    value = Column(Float, nullable=False)
    source = Column(String, nullable=False)
