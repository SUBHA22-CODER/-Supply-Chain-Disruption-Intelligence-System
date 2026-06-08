"""Pydantic schemas for Kafka message validation."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union
from datetime import datetime


class WeatherEvent(BaseModel):
    supplier_id: str
    timestamp: datetime
    temp: float
    description: str
    wind_speed: float = Field(ge=0)


class NewsEvent(BaseModel):
    supplier_id: str
    timestamp: datetime
    keyword: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)


class SatelliteSignal(BaseModel):
    supplier_id: str
    timestamp: datetime
    risk_score: float = Field(ge=0.0, le=1.0)


class ProcessedRiskScore(BaseModel):
    supplier_id: str
    timestamp: datetime
    composite_score: float = Field(ge=0.0, le=1.0)
    weather_risk: Optional[float] = None
    news_risk: Optional[float] = None
    satellite_risk: Optional[float] = None
