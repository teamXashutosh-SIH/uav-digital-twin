from packages.simulation.mission_pipeline import MissionAnalysisPipeline
from packages.simulation.scenarios import (
    MissionScenario,
    MissionSegment,
)


def run_fault_mission(
    fault: str,
    severity: float,
) -> object:
    scenario = MissionScenario(
        scenario_id=f"{fault}_fault",
        name=f"{fault} Fault",
        description=f"Mission with injected {fault} condition.",
        segments=(
            MissionSegment(
                "CRUISE",
                20,
                60.0,
                0.0,
                25.0,
            ),
            MissionSegment(
                "FAULT",
                20,
                75.0,
                0.0,
                25.0,
                fault,
                severity,
            ),
            MissionSegment(
                "COOLDOWN",
                20,
                40.0,
                0.0,
                25.0,
            ),
        ),
    )

    return MissionAnalysisPipeline().run(scenario)


def test_overheating_fault_detection():
    result = run_fault_mission(
        "overheating",
        0.8,
    )

    detected_faults = {
        step.fault.fault
        for step in result.steps
    }

    assert "OVERHEATING" in detected_faults

    assert max(
        step.degradation.degradation_index
        for step in result.steps
    ) > 0.5

    assert min(
        step.rul.rul_hours
        for step in result.steps
    ) < 2000.0


def test_low_oil_pressure_fault_detection():
    result = run_fault_mission(
        "low_oil_pressure",
        0.8,
    )

    detected_faults = {
        step.fault.fault
        for step in result.steps
    }

    assert "LOW_OIL_PRESSURE" in detected_faults

    assert max(
        step.degradation.degradation_index
        for step in result.steps
    ) > 0.1


def test_abnormal_vibration_fault_detection():
    result = run_fault_mission(
        "abnormal_vibration",
        0.8,
    )

    detected_faults = {
        step.fault.fault
        for step in result.steps
    }

    assert "ABNORMAL_VIBRATION" in detected_faults

    assert max(
        step.degradation.degradation_index
        for step in result.steps
    ) > 0.1


def test_startup_initialization_does_not_create_false_failure():
    scenario = MissionScenario(
        scenario_id="startup_validation",
        name="Startup Validation",
        description="Verify Digital Twin initialization behavior.",
        segments=(
            MissionSegment(
                "STARTUP",
                1,
                30.0,
                0.0,
                25.0,
            ),
        ),
    )

    result = MissionAnalysisPipeline().run(scenario)

    first_health = result.steps[0].health.health

    assert first_health.health_score == 100.0
    assert first_health.status == "HEALTHY"
    assert first_health.anomaly_score == 0.0