from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from .db import Base
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    pw = Column(String(255), nullable=False)
    settings = Column(JSON, default=dict)
    created = Column(DateTime, default=datetime.utcnow)
class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(120), nullable=False)
    vtype = Column(String(10), default="fuel")      # fuel | ev
    capacity = Column(Float, default=0)
    efficiency = Column(Float, nullable=False)      # km/l or kWh/100km
    cost_per_km = Column(Float, default=0)
    status = Column(String(20), default="available")
class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String(120), nullable=False)
    status = Column(String(20), default="planned", index=True)
    objective = Column(String(20), default="distance")
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True, index=True)
    demand = Column(Float, default=0)
    distance_km = Column(Float, default=0)
    duration_min = Column(Float, default=0)
    cost = Column(Float, nullable=True)
    st = Column(Float, index=True)
    en = Column(Float)
    data = Column(JSON, default=dict)               # points, route result, assumptions, source metadata
    created = Column(DateTime, default=datetime.utcnow, index=True)
