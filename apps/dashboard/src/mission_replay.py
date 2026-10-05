from dataclasses import dataclass

from packages.simulation.mission_pipeline import MissionAnalysisResult


@dataclass
class ReplayTelemetryPoint:
    time_seconds: int
    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_gph: float
    vibration_g: float
    battery_voltage_v: float
    alternator_current_a: float
    throttle_pct: float
    altitude_m: float
    ambient_temperature_c: float
    expected_rpm: float
    expected_cht_c: float
    expected_egt_c: float
    expected_oil_pressure_kpa: float
    expected_oil_temperature_c: float
    expected_fuel_flow_gph: float
    expected_vibration_g: float


@dataclass
class ReplayHealthPoint:
    time_seconds: int
    status: str
    health_score: float
    anomaly_score: float
    operating_mode: str
    thermal_state: str
    lubrication_state: str
    combustion_state: str
    mechanical_state: str
    electrical_state: str
    sensor_confidence: str


@dataclass
class ReplayDegradationPoint:
    time_seconds: int
    degradation_index: float
    degradation_level: str
    trend: str
    trend_rate: float


@dataclass
class ReplayRULPoint:
    time_seconds: int
    rul_hours: float
    rul_samples: float
    confidence: float
    status: str


@dataclass
class ReplayFaultEvent:
    time_seconds: int
    end_time_seconds: int
    duration_seconds: int
    segment_name: str
    fault: str
    confidence: float
    severity: str
    evidence: list[str]
    recommendation: str


@dataclass
class ReplayTransitionEvent:
    time_seconds: int
    segment_name: str
    transition_samples_remaining: int
    throttle_change_pct: float
    altitude_change_m: float
    temperature_change_c: float


@dataclass
class MissionReplay:
    scenario_id: str
    scenario_name: str
    duration_seconds: int
    total_samples: int
    segments: list[str]
    telemetry: list[ReplayTelemetryPoint]
    health: list[ReplayHealthPoint]
    degradation: list[ReplayDegradationPoint]
    rul: list[ReplayRULPoint]
    fault_events: list[ReplayFaultEvent]
    transition_events: list[ReplayTransitionEvent]


def _severity_rank(value: str) -> int:
    return {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}.get(str(value).upper(), 0)


def _merge_evidence(existing: list[str], new_items: list[str]) -> list[str]:
    result = list(existing)
    for item in new_items:
        if item and item not in result:
            result.append(item)
    return result


def _consolidate_fault_events(events: list[ReplayFaultEvent]) -> list[ReplayFaultEvent]:
    if not events:
        return []

    consolidated: list[ReplayFaultEvent] = []
    current = events[0]

    for event in events[1:]:
        contiguous = (
            event.fault == current.fault
            and event.segment_name == current.segment_name
            and event.time_seconds == current.end_time_seconds + 1
        )
        if contiguous:
            current = ReplayFaultEvent(
                time_seconds=current.time_seconds,
                end_time_seconds=event.end_time_seconds,
                duration_seconds=event.end_time_seconds - current.time_seconds + 1,
                segment_name=current.segment_name,
                fault=current.fault,
                confidence=max(current.confidence, event.confidence),
                severity=(
                    event.severity
                    if _severity_rank(event.severity) > _severity_rank(current.severity)
                    else current.severity
                ),
                evidence=_merge_evidence(current.evidence, event.evidence),
                recommendation=event.recommendation or current.recommendation,
            )
        else:
            consolidated.append(current)
            current = event

    consolidated.append(current)
    return consolidated


def build_mission_replay(mission: MissionAnalysisResult) -> MissionReplay:
    if not mission.steps:
        raise ValueError("Cannot build replay from an empty mission.")

    telemetry_points = []
    health_points = []
    degradation_points = []
    rul_points = []
    fault_events = []
    transition_events = []
    segments = []

    for step in mission.steps:
        telemetry = step.twin_state.observed
        expected = step.twin_state.expected

        if step.segment_name not in segments:
            segments.append(step.segment_name)

        telemetry_points.append(
            ReplayTelemetryPoint(
                time_seconds=int(step.mission_time_seconds),
                rpm=float(telemetry.rpm),
                cht_c=float(telemetry.cht_c),
                egt_c=float(telemetry.egt_c),
                oil_pressure_kpa=float(telemetry.oil_pressure_kpa),
                oil_temperature_c=float(telemetry.oil_temperature_c),
                fuel_flow_gph=float(telemetry.fuel_flow_gph),
                vibration_g=float(telemetry.vibration_g),
                battery_voltage_v=float(telemetry.battery_voltage_v),
                alternator_current_a=float(telemetry.alternator_current_a),
                throttle_pct=float(telemetry.throttle_pct),
                altitude_m=float(telemetry.altitude_m),
                ambient_temperature_c=float(telemetry.ambient_temperature_c),
                expected_rpm=float(expected.rpm),
                expected_cht_c=float(expected.cht_c),
                expected_egt_c=float(expected.egt_c),
                expected_oil_pressure_kpa=float(expected.oil_pressure_kpa),
                expected_oil_temperature_c=float(expected.oil_temperature_c),
                expected_fuel_flow_gph=float(expected.fuel_flow_gph),
                expected_vibration_g=float(expected.vibration_g),
            )
        )

        health = step.health.health
        health_points.append(
            ReplayHealthPoint(
                time_seconds=int(step.mission_time_seconds),
                status=health.status,
                health_score=float(health.health_score),
                anomaly_score=float(health.anomaly_score),
                operating_mode=step.engine_state.operating_mode,
                thermal_state=step.engine_state.thermal_state,
                lubrication_state=step.engine_state.lubrication_state,
                combustion_state=step.engine_state.combustion_state,
                mechanical_state=step.engine_state.mechanical_state,
                electrical_state=step.engine_state.electrical_state,
                sensor_confidence=step.engine_state.sensor_confidence,
            )
        )

        degradation = step.degradation
        degradation_points.append(
            ReplayDegradationPoint(
                time_seconds=int(step.mission_time_seconds),
                degradation_index=float(degradation.degradation_index),
                degradation_level=degradation.degradation_level,
                trend=degradation.trend,
                trend_rate=float(degradation.trend_rate),
            )
        )

        rul = step.rul
        rul_points.append(
            ReplayRULPoint(
                time_seconds=int(step.mission_time_seconds),
                rul_hours=float(rul.rul_hours),
                rul_samples=float(rul.rul_samples),
                confidence=float(rul.confidence),
                status=rul.status,
            )
        )

        fault = step.fault
        if fault.fault != "NO_SPECIFIC_FAULT":
            time_seconds = int(step.mission_time_seconds)
            fault_events.append(
                ReplayFaultEvent(
                    time_seconds=time_seconds,
                    end_time_seconds=time_seconds,
                    duration_seconds=1,
                    segment_name=step.segment_name,
                    fault=fault.fault,
                    confidence=float(fault.confidence),
                    severity=fault.severity,
                    evidence=list(fault.evidence),
                    recommendation=fault.recommendation,
                )
            )

        condition = step.operating_condition
        if condition.is_transition:
            transition_events.append(
                ReplayTransitionEvent(
                    time_seconds=int(step.mission_time_seconds),
                    segment_name=step.segment_name,
                    transition_samples_remaining=int(condition.transition_samples_remaining),
                    throttle_change_pct=float(condition.throttle_change_pct),
                    altitude_change_m=float(condition.altitude_change_m),
                    temperature_change_c=float(condition.temperature_change_c),
                )
            )

    fault_events = _consolidate_fault_events(fault_events)

    return MissionReplay(
        scenario_id=mission.scenario_id,
        scenario_name=mission.scenario_name,
        duration_seconds=int(mission.mission_duration_seconds),
        total_samples=int(mission.total_samples),
        segments=segments,
        telemetry=telemetry_points,
        health=health_points,
        degradation=degradation_points,
        rul=rul_points,
        fault_events=fault_events,
        transition_events=transition_events,
    )


def replay_to_dict(replay: MissionReplay) -> dict:
    return {
        "mission": {
            "scenario_id": replay.scenario_id,
            "scenario_name": replay.scenario_name,
            "duration_seconds": replay.duration_seconds,
            "total_samples": replay.total_samples,
            "segments": replay.segments,
        },
        "telemetry": [
            {
                "time_seconds": p.time_seconds,
                "rpm": p.rpm,
                "cht_c": p.cht_c,
                "egt_c": p.egt_c,
                "oil_pressure_kpa": p.oil_pressure_kpa,
                "oil_temperature_c": p.oil_temperature_c,
                "fuel_flow_gph": p.fuel_flow_gph,
                "vibration_g": p.vibration_g,
                "battery_voltage_v": p.battery_voltage_v,
                "alternator_current_a": p.alternator_current_a,
                "throttle_pct": p.throttle_pct,
                "altitude_m": p.altitude_m,
                "ambient_temperature_c": p.ambient_temperature_c,
                "expected_rpm": p.expected_rpm,
                "expected_cht_c": p.expected_cht_c,
                "expected_egt_c": p.expected_egt_c,
                "expected_oil_pressure_kpa": p.expected_oil_pressure_kpa,
                "expected_oil_temperature_c": p.expected_oil_temperature_c,
                "expected_fuel_flow_gph": p.expected_fuel_flow_gph,
                "expected_vibration_g": p.expected_vibration_g,
            }
            for p in replay.telemetry
        ],
        "health": [
            {
                "time_seconds": p.time_seconds,
                "status": p.status,
                "health_score": p.health_score,
                "anomaly_score": p.anomaly_score,
                "operating_mode": p.operating_mode,
                "thermal_state": p.thermal_state,
                "lubrication_state": p.lubrication_state,
                "combustion_state": p.combustion_state,
                "mechanical_state": p.mechanical_state,
                "electrical_state": p.electrical_state,
                "sensor_confidence": p.sensor_confidence,
            }
            for p in replay.health
        ],
        "degradation": [
            {
                "time_seconds": p.time_seconds,
                "degradation_index": p.degradation_index,
                "degradation_level": p.degradation_level,
                "trend": p.trend,
                "trend_rate": p.trend_rate,
            }
            for p in replay.degradation
        ],
        "rul": [
            {
                "time_seconds": p.time_seconds,
                "rul_hours": p.rul_hours,
                "rul_samples": p.rul_samples,
                "confidence": p.confidence,
                "status": p.status,
            }
            for p in replay.rul
        ],
        "fault_events": [
            {
                "time_seconds": event.time_seconds,
                "end_time_seconds": event.end_time_seconds,
                "duration_seconds": event.duration_seconds,
                "segment_name": event.segment_name,
                "fault": event.fault,
                "confidence": event.confidence,
                "severity": event.severity,
                "evidence": event.evidence,
                "recommendation": event.recommendation,
            }
            for event in replay.fault_events
        ],
        "transition_events": [
            {
                "time_seconds": event.time_seconds,
                "segment_name": event.segment_name,
                "transition_samples_remaining": event.transition_samples_remaining,
                "throttle_change_pct": event.throttle_change_pct,
                "altitude_change_m": event.altitude_change_m,
                "temperature_change_c": event.temperature_change_c,
            }
            for event in replay.transition_events
        ],
    }
