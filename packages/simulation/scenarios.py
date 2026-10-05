from dataclasses import dataclass


@dataclass(frozen=True)
class MissionSegment:
    """
    Defines one segment of a UAV engine mission.

    Development/demo mission model.
    """

    name: str

    duration_seconds: int

    throttle_pct: float

    altitude_m: float

    ambient_temperature_c: float

    fault: str | None = None

    fault_severity: float = 0.0


@dataclass(frozen=True)
class MissionScenario:
    """
    Complete mission scenario consisting of multiple
    operating segments.

    Development/demo simulation model.
    """

    scenario_id: str

    name: str

    description: str

    segments: tuple[MissionSegment, ...]


SCENARIOS = {
    "normal_mission": MissionScenario(
        scenario_id="normal_mission",
        name="Normal Mission",
        description=(
            "Nominal UAV mission with climb, cruise "
            "and descent segments."
        ),
        segments=(
            MissionSegment(
                name="CLIMB",
                duration_seconds=30,
                throttle_pct=75.0,
                altitude_m=3000.0,
                ambient_temperature_c=20.0,
            ),
            MissionSegment(
                name="CRUISE",
                duration_seconds=60,
                throttle_pct=60.0,
                altitude_m=5000.0,
                ambient_temperature_c=15.0,
            ),
            MissionSegment(
                name="DESCENT",
                duration_seconds=30,
                throttle_pct=40.0,
                altitude_m=2000.0,
                ambient_temperature_c=22.0,
            ),
        ),
    ),

    "hot_weather": MissionScenario(
        scenario_id="hot_weather",
        name="Hot Weather",
        description=(
            "High ambient-temperature mission "
            "representing hot-weather operation."
        ),
        segments=(
            MissionSegment(
                name="HOT_CLIMB",
                duration_seconds=40,
                throttle_pct=75.0,
                altitude_m=2500.0,
                ambient_temperature_c=45.0,
            ),
            MissionSegment(
                name="HOT_CRUISE",
                duration_seconds=60,
                throttle_pct=65.0,
                altitude_m=4000.0,
                ambient_temperature_c=42.0,
            ),
        ),
    ),

    "high_altitude": MissionScenario(
        scenario_id="high_altitude",
        name="High Altitude",
        description=(
            "Mission segment at elevated altitude "
            "with reduced ambient pressure assumptions."
        ),
        segments=(
            MissionSegment(
                name="HIGH_ALTITUDE_CLIMB",
                duration_seconds=45,
                throttle_pct=80.0,
                altitude_m=8000.0,
                ambient_temperature_c=5.0,
            ),
            MissionSegment(
                name="HIGH_ALTITUDE_CRUISE",
                duration_seconds=75,
                throttle_pct=65.0,
                altitude_m=10000.0,
                ambient_temperature_c=-5.0,
            ),
        ),
    ),

    "rapid_throttle": MissionScenario(
        scenario_id="rapid_throttle",
        name="Rapid Throttle Changes",
        description=(
            "Mission with repeated rapid throttle "
            "changes to stress the engine."
        ),
        segments=(
            MissionSegment(
                name="LOW_LOAD",
                duration_seconds=15,
                throttle_pct=30.0,
                altitude_m=2000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="HIGH_LOAD",
                duration_seconds=15,
                throttle_pct=90.0,
                altitude_m=2000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="LOW_LOAD",
                duration_seconds=15,
                throttle_pct=35.0,
                altitude_m=2000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="HIGH_LOAD",
                duration_seconds=15,
                throttle_pct=95.0,
                altitude_m=2000.0,
                ambient_temperature_c=25.0,
            ),
        ),
    ),

    "overheating": MissionScenario(
        scenario_id="overheating",
        name="Developing Overheating",
        description=(
            "Mission in which an overheating condition "
            "develops progressively."
        ),
        segments=(
            MissionSegment(
                name="NORMAL",
                duration_seconds=30,
                throttle_pct=60.0,
                altitude_m=3000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="OVERHEATING_DEVELOPMENT",
                duration_seconds=60,
                throttle_pct=70.0,
                altitude_m=3000.0,
                ambient_temperature_c=30.0,
                fault="overheating",
                fault_severity=0.75,
            ),
        ),
    ),

    "low_oil_pressure": MissionScenario(
        scenario_id="low_oil_pressure",
        name="Low Oil Pressure",
        description=(
            "Mission in which lubrication-system "
            "pressure progressively deteriorates."
        ),
        segments=(
            MissionSegment(
                name="NORMAL",
                duration_seconds=30,
                throttle_pct=60.0,
                altitude_m=2500.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="LOW_OIL_PRESSURE",
                duration_seconds=60,
                throttle_pct=65.0,
                altitude_m=2500.0,
                ambient_temperature_c=25.0,
                fault="low_oil_pressure",
                fault_severity=0.75,
            ),
        ),
    ),

    "abnormal_vibration": MissionScenario(
        scenario_id="abnormal_vibration",
        name="Abnormal Vibration",
        description=(
            "Mission with progressively increasing "
            "mechanical vibration."
        ),
        segments=(
            MissionSegment(
                name="NORMAL",
                duration_seconds=30,
                throttle_pct=60.0,
                altitude_m=2500.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="VIBRATION_DEVELOPMENT",
                duration_seconds=60,
                throttle_pct=65.0,
                altitude_m=2500.0,
                ambient_temperature_c=25.0,
                fault="abnormal_vibration",
                fault_severity=0.80,
            ),
        ),
    ),

    "combustion_anomaly": MissionScenario(
        scenario_id="combustion_anomaly",
        name="Combustion Anomaly",
        description=(
            "Mission with a developing combustion "
            "abnormality."
        ),
        segments=(
            MissionSegment(
                name="NORMAL",
                duration_seconds=30,
                throttle_pct=60.0,
                altitude_m=3000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="COMBUSTION_ANOMALY",
                duration_seconds=60,
                throttle_pct=70.0,
                altitude_m=3000.0,
                ambient_temperature_c=25.0,
                fault="combustion_anomaly",
                fault_severity=0.75,
            ),
        ),
    ),

    "sensor_drift": MissionScenario(
        scenario_id="sensor_drift",
        name="EGT Sensor Drift",
        description=(
            "Mission with progressive EGT sensor "
            "measurement drift."
        ),
        segments=(
            MissionSegment(
                name="NORMAL",
                duration_seconds=30,
                throttle_pct=60.0,
                altitude_m=3000.0,
                ambient_temperature_c=25.0,
            ),
            MissionSegment(
                name="SENSOR_DRIFT",
                duration_seconds=60,
                throttle_pct=60.0,
                altitude_m=3000.0,
                ambient_temperature_c=25.0,
                fault="sensor_drift",
                fault_severity=0.75,
            ),
        ),
    ),
}


def get_scenario(
    scenario_id: str,
) -> MissionScenario:

    if scenario_id not in SCENARIOS:
        available = ", ".join(
            sorted(SCENARIOS.keys())
        )

        raise ValueError(
            f"Unknown scenario '{scenario_id}'. "
            f"Available scenarios: {available}"
        )

    return SCENARIOS[scenario_id]


def list_scenarios() -> list[dict]:

    return [
        {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "segments": len(
                scenario.segments
            ),
        }
        for scenario in SCENARIOS.values()
    ]