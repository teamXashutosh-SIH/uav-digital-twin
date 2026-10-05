from dataclasses import dataclass

from packages.simulation.mission_pipeline import (
    MissionAnalysisResult,
    MissionAnalysisStep,
)


@dataclass
class ReplayTelemetryPoint:
    """
    Telemetry values required by the mission replay UI.
    """

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


@dataclass
class ReplayHealthPoint:
    """
    Health information for one replay timestamp.
    """

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
    """
    Degradation information for one replay timestamp.
    """

    time_seconds: int

    degradation_index: float
    degradation_level: str

    trend: str
    trend_rate: float


@dataclass
class ReplayRULPoint:
    """
    RUL information for one replay timestamp.
    """

    time_seconds: int

    rul_hours: float
    rul_samples: float

    confidence: float
    status: str


@dataclass
class ReplayFaultEvent:
    """
    Consolidated fault diagnosis event detected during replay.

    A fault that persists across consecutive mission samples is
    represented as one event interval rather than many duplicate
    per-sample events.
    """

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
    """
    Operating-condition transition event.
    """

    time_seconds: int

    segment_name: str

    transition_samples_remaining: int

    throttle_change_pct: float
    altitude_change_m: float
    temperature_change_c: float


@dataclass
class MissionReplay:
    """
    Complete replay-ready representation of a mission.
    """

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


def _severity_rank(severity: str) -> int:
    """
    Return an ordering for severity aggregation.
    """

    ranks = {
        "HEALTHY": 0,
        "NORMAL": 0,
        "WARNING": 1,
        "CRITICAL": 2,
    }

    return ranks.get(
        str(severity).upper(),
        0,
    )


def _merge_evidence(
    existing: list[str],
    new_items: list[str],
) -> list[str]:
    """
    Merge evidence while preserving insertion order and
    avoiding duplicate messages.
    """

    merged = list(existing)

    for item in new_items:
        if item not in merged:
            merged.append(item)

    return merged


def _consolidate_fault_events(
    steps: list[MissionAnalysisStep],
) -> list[ReplayFaultEvent]:
    """
    Convert per-sample fault diagnoses into clean fault intervals.

    Consecutive samples are grouped only when all of the following
    remain the same:

    - fault type
    - mission segment

    A NO_SPECIFIC_FAULT sample closes the current event.

    Example:

        ABNORMAL_VIBRATION at 46, 47
        OVERHEATING at 48, 49, 50

    becomes:

        ABNORMAL_VIBRATION: 46-47
        OVERHEATING: 48-50
    """

    events: list[ReplayFaultEvent] = []

    active_event: ReplayFaultEvent | None = None

    for step in steps:

        fault = step.fault

        if fault.fault == "NO_SPECIFIC_FAULT":

            if active_event is not None:
                events.append(active_event)
                active_event = None

            continue

        current_time = int(
            step.mission_time_seconds
        )

        current_fault = fault.fault
        current_segment = step.segment_name

        if (
            active_event is not None
            and active_event.fault == current_fault
            and active_event.segment_name == current_segment
            and current_time
            == active_event.end_time_seconds + 1
        ):

            active_event.end_time_seconds = current_time

            active_event.duration_seconds = (
                active_event.end_time_seconds
                - active_event.time_seconds
                + 1
            )

            active_event.confidence = max(
                active_event.confidence,
                float(fault.confidence),
            )

            if (
                _severity_rank(fault.severity)
                > _severity_rank(
                    active_event.severity
                )
            ):
                active_event.severity = (
                    fault.severity
                )

            active_event.evidence = (
                _merge_evidence(
                    active_event.evidence,
                    list(fault.evidence),
                )
            )

            if fault.recommendation:
                active_event.recommendation = (
                    fault.recommendation
                )

            continue

        if active_event is not None:
            events.append(active_event)

        active_event = ReplayFaultEvent(
            time_seconds=current_time,
            end_time_seconds=current_time,
            duration_seconds=1,
            segment_name=current_segment,
            fault=current_fault,
            confidence=float(fault.confidence),
            severity=fault.severity,
            evidence=list(fault.evidence),
            recommendation=fault.recommendation,
        )

    if active_event is not None:
        events.append(active_event)

    return events


def build_mission_replay(
    mission: MissionAnalysisResult,
) -> MissionReplay:
    """
    Convert detailed mission analysis into a replay-ready
    structure.

    Development/demo implementation.

    Fault diagnoses are consolidated into event intervals so
    the dashboard receives meaningful events rather than one
    duplicate event for every telemetry sample.
    """

    if not mission.steps:
        raise ValueError(
            "Cannot build replay from an empty mission."
        )

    telemetry_points = []

    health_points = []

    degradation_points = []

    rul_points = []

    transition_events = []

    segments = []

    for step in mission.steps:

        telemetry = step.twin_state.observed

        # -------------------------------------------------
        # Mission segments
        # -------------------------------------------------

        if step.segment_name not in segments:
            segments.append(
                step.segment_name
            )

        # -------------------------------------------------
        # Telemetry
        # -------------------------------------------------

        telemetry_points.append(
            ReplayTelemetryPoint(
                time_seconds=(
                    step.mission_time_seconds
                ),

                rpm=float(
                    telemetry.rpm
                ),

                cht_c=float(
                    telemetry.cht_c
                ),

                egt_c=float(
                    telemetry.egt_c
                ),

                oil_pressure_kpa=float(
                    telemetry.oil_pressure_kpa
                ),

                oil_temperature_c=float(
                    telemetry.oil_temperature_c
                ),

                fuel_flow_gph=float(
                    telemetry.fuel_flow_gph
                ),

                vibration_g=float(
                    telemetry.vibration_g
                ),

                battery_voltage_v=float(
                    telemetry.battery_voltage_v
                ),

                alternator_current_a=float(
                    telemetry.alternator_current_a
                ),

                throttle_pct=float(
                    telemetry.throttle_pct
                ),

                altitude_m=float(
                    telemetry.altitude_m
                ),
            )
        )

        # -------------------------------------------------
        # Health
        # -------------------------------------------------

        health = step.health.health

        health_points.append(
            ReplayHealthPoint(
                time_seconds=(
                    step.mission_time_seconds
                ),

                status=health.status,

                health_score=float(
                    health.health_score
                ),

                anomaly_score=float(
                    health.anomaly_score
                ),

                operating_mode=(
                    step.engine_state
                    .operating_mode
                ),

                thermal_state=(
                    step.engine_state
                    .thermal_state
                ),

                lubrication_state=(
                    step.engine_state
                    .lubrication_state
                ),

                combustion_state=(
                    step.engine_state
                    .combustion_state
                ),

                mechanical_state=(
                    step.engine_state
                    .mechanical_state
                ),

                electrical_state=(
                    step.engine_state
                    .electrical_state
                ),

                sensor_confidence=(
                    step.engine_state
                    .sensor_confidence
                ),
            )
        )

        # -------------------------------------------------
        # Degradation
        # -------------------------------------------------

        degradation = step.degradation

        degradation_points.append(
            ReplayDegradationPoint(
                time_seconds=(
                    step.mission_time_seconds
                ),

                degradation_index=float(
                    degradation.degradation_index
                ),

                degradation_level=(
                    degradation.degradation_level
                ),

                trend=(
                    degradation.trend
                ),

                trend_rate=float(
                    degradation.trend_rate
                ),
            )
        )

        # -------------------------------------------------
        # RUL
        # -------------------------------------------------

        rul = step.rul

        rul_points.append(
            ReplayRULPoint(
                time_seconds=(
                    step.mission_time_seconds
                ),

                rul_hours=float(
                    rul.rul_hours
                ),

                rul_samples=float(
                    rul.rul_samples
                ),

                confidence=float(
                    rul.confidence
                ),

                status=(
                    rul.status
                ),
            )
        )

        # -------------------------------------------------
        # Operating-condition transitions
        # -------------------------------------------------

        condition = (
            step.operating_condition
        )

        if condition.is_transition:

            transition_events.append(
                ReplayTransitionEvent(
                    time_seconds=(
                        step.mission_time_seconds
                    ),

                    segment_name=(
                        step.segment_name
                    ),

                    transition_samples_remaining=(
                        condition
                        .transition_samples_remaining
                    ),

                    throttle_change_pct=float(
                        condition
                        .throttle_change_pct
                    ),

                    altitude_change_m=float(
                        condition
                        .altitude_change_m
                    ),

                    temperature_change_c=float(
                        condition
                        .temperature_change_c
                    ),
                )
            )

    # -----------------------------------------------------
    # Consolidated fault events
    # -----------------------------------------------------

    fault_events = _consolidate_fault_events(
        mission.steps
    )

    return MissionReplay(
        scenario_id=(
            mission.scenario_id
        ),

        scenario_name=(
            mission.scenario_name
        ),

        duration_seconds=(
            mission.mission_duration_seconds
        ),

        total_samples=(
            mission.total_samples
        ),

        segments=segments,

        telemetry=telemetry_points,

        health=health_points,

        degradation=degradation_points,

        rul=rul_points,

        fault_events=fault_events,

        transition_events=(
            transition_events
        ),
    )


def replay_to_dict(
    replay: MissionReplay,
) -> dict:
    """
    Convert the replay structure into a JSON-friendly
    dictionary for FastAPI and the dashboard.
    """

    return {
        "mission": {
            "scenario_id": (
                replay.scenario_id
            ),

            "scenario_name": (
                replay.scenario_name
            ),

            "duration_seconds": (
                replay.duration_seconds
            ),

            "total_samples": (
                replay.total_samples
            ),

            "segments": (
                replay.segments
            ),
        },

        "telemetry": [
            {
                "time_seconds": p.time_seconds,
                "rpm": p.rpm,
                "cht_c": p.cht_c,
                "egt_c": p.egt_c,

                "oil_pressure_kpa": (
                    p.oil_pressure_kpa
                ),

                "oil_temperature_c": (
                    p.oil_temperature_c
                ),

                "fuel_flow_gph": (
                    p.fuel_flow_gph
                ),

                "vibration_g": (
                    p.vibration_g
                ),

                "battery_voltage_v": (
                    p.battery_voltage_v
                ),

                "alternator_current_a": (
                    p.alternator_current_a
                ),

                "throttle_pct": (
                    p.throttle_pct
                ),

                "altitude_m": (
                    p.altitude_m
                ),
            }

            for p in replay.telemetry
        ],

        "health": [
            {
                "time_seconds": p.time_seconds,

                "status": p.status,

                "health_score": (
                    p.health_score
                ),

                "anomaly_score": (
                    p.anomaly_score
                ),

                "operating_mode": (
                    p.operating_mode
                ),

                "thermal_state": (
                    p.thermal_state
                ),

                "lubrication_state": (
                    p.lubrication_state
                ),

                "combustion_state": (
                    p.combustion_state
                ),

                "mechanical_state": (
                    p.mechanical_state
                ),

                "electrical_state": (
                    p.electrical_state
                ),

                "sensor_confidence": (
                    p.sensor_confidence
                ),
            }

            for p in replay.health
        ],

        "degradation": [
            {
                "time_seconds": p.time_seconds,

                "degradation_index": (
                    p.degradation_index
                ),

                "degradation_level": (
                    p.degradation_level
                ),

                "trend": p.trend,

                "trend_rate": (
                    p.trend_rate
                ),
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
                "time_seconds": (
                    event.time_seconds
                ),

                "end_time_seconds": (
                    event.end_time_seconds
                ),

                "duration_seconds": (
                    event.duration_seconds
                ),

                "segment_name": (
                    event.segment_name
                ),

                "fault": event.fault,

                "confidence": (
                    event.confidence
                ),

                "severity": (
                    event.severity
                ),

                "evidence": event.evidence,

                "recommendation": (
                    event.recommendation
                ),
            }

            for event in replay.fault_events
        ],

        "transition_events": [
            {
                "time_seconds": (
                    event.time_seconds
                ),

                "segment_name": (
                    event.segment_name
                ),

                "transition_samples_remaining": (
                    event.transition_samples_remaining
                ),

                "throttle_change_pct": (
                    event.throttle_change_pct
                ),

                "altitude_change_m": (
                    event.altitude_change_m
                ),

                "temperature_change_c": (
                    event.temperature_change_c
                ),
            }

            for event in replay.transition_events
        ],
    }
