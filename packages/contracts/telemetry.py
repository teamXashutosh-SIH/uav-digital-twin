from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QualityFlag(str, Enum):
    MISSING = "missing"
    OUT_OF_RANGE = "out_of_range"
    STALE = "stale"
    SENSOR_SUSPECT = "sensor_suspect"
    SIMULATED = "simulated"
    INTERPOLATED = "interpolated"


class EngineTelemetry(BaseModel):
    schema_version: str = "1.0"

    vehicle_id: str
    engine_id: str
    mission_id: str

    sequence: int = Field(ge=0)
    timestamp: datetime

    rpm: float
    cht_c: float
    egt_c: float

    oil_pressure_kpa: float
    oil_temperature_c: float

    fuel_flow_gph: float
    vibration_g: float

    battery_voltage_v: float
    alternator_current_a: float

    injection_timing_deg: float

    altitude_m: float
    ambient_temperature_c: float
    throttle_pct: float

    quality_flags: list[QualityFlag] = []