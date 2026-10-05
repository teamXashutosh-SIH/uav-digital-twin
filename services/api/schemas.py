from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: str
    engine_id: str
    mission_id: str
    sequence: int
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

    quality_flags: list
class FaultInjectionRequest(BaseModel):
    fault: str
    severity: float = 1.0
    engine_id: str = "ENGINE-001"


class NotificationResponse(BaseModel):
    id: int
    engine_id: str
    vehicle_id: str | None
    mission_id: str | None
    fault: str
    severity: float
    status: str
    started_at: datetime
    cleared_at: datetime | None
    created_at: datetime
    metadata: dict | None = None


class MissionStartRequest(BaseModel):
    mission_id: str | None = None
    vehicle_id: str = "UAV-DEMO-001"
    engine_id: str = "ENGINE-001"
    metadata: dict | None = None


class MissionEndRequest(BaseModel):
    engine_id: str = "ENGINE-001"
    mission_id: str | None = None


class MissionScenarioRequest(BaseModel):
    scenario: str
    engine_id: str = "ENGINE-001"
    mission_id: str | None = None
    duration: int | None = None