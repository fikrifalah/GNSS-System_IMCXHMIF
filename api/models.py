from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, UniqueConstraint, DateTime, Text
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Station(Base):
    __tablename__ = "stations"

    id = Column(String(50), primary_key=True, index=True) # e.g. "rover-01"
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False) # "base" or "rover"
    reference_lat = Column(Float, nullable=True)
    reference_lon = Column(Float, nullable=True)
    reference_height = Column(Float, nullable=True)
    location = Column(String(100), nullable=True) # e.g. "Lereng Barat"
    peta_x = Column(Float, nullable=True) # Map position X (0-1)
    peta_y = Column(Float, nullable=True) # Map position Y (0-1)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions = relationship("Session", back_populates="station", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="station", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="station", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(50), primary_key=True, index=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False)
    session_start = Column(DateTime(timezone=True), nullable=False)
    session_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, default="pending") # "pending", "processing", "done", "failed"
    rinex_path = Column(String(255), nullable=False)

    # Unique constraint on station_id and session_start
    __table_args__ = (
        UniqueConstraint("station_id", "session_start", name="uq_station_session_start"),
    )

    # Relationships
    station = relationship("Station", back_populates="sessions")
    positions = relationship("Position", back_populates="session")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(50), ForeignKey("sessions.id"), nullable=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    
    # Displacements from reference position in meters
    east_displacement = Column(Float, nullable=False)
    north_displacement = Column(Float, nullable=False)
    up_displacement = Column(Float, nullable=False)
    
    fix_type = Column(String(20), nullable=False) # "RTK_FIX", "RTK_FLOAT", "NO_FIX"
    satellites = Column(Integer, nullable=False)
    hdop = Column(Float, nullable=False)
    battery_voltage = Column(Float, nullable=True)

    # Relationships
    station = relationship("Station", back_populates="positions")
    session = relationship("Session", back_populates="positions")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(50), primary_key=True, index=True)
    station_id = Column(String(50), ForeignKey("stations.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    severity = Column(String(20), nullable=False) # "BAHAYA", "WASPADA", "INFORMASI"
    message = Column(String(255), nullable=False) # judul
    description = Column(Text, nullable=True) # deskripsi
    details = Column(Text, nullable=True) # detail
    resolved = Column(Boolean, nullable=False, default=False)

    # Relationships
    station = relationship("Station", back_populates="alerts")


class Config(Base):
    __tablename__ = "config"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(String(255), nullable=False)
