from services.simulator.engine_simulator import EngineSimulator

from packages.digital_twin.core import EngineDigitalTwin
from packages.health.engine_health import EngineHealthEngine


def test_integrated_engine_health():

    simulator = EngineSimulator(seed=42)

    twin = EngineDigitalTwin()
    health_engine = EngineHealthEngine()

    egt_history = []
    cht_history = []

    print("\n--- INTEGRATED ENGINE HEALTH TEST ---")

    # Generate a short normal operating history.
    for _ in range(6):

        telemetry = simulator.step(
            throttle_pct=60.0,
            altitude_m=2000.0,
            ambient_temperature_c=25.0,
        )

        egt_history.append(telemetry.egt_c)
        cht_history.append(telemetry.cht_c)

    twin_state = twin.compare(telemetry)

    assessment = health_engine.assess(
        twin_state=twin_state,
        egt_history=egt_history,
        cht_history=cht_history,
    )

    print("\nENGINE HEALTH")
    print(f"Health Score:       {assessment.health.health_score:.1f}%")
    print(f"Status:             {assessment.health.status}")
    print(f"Anomaly Score:      {assessment.health.anomaly_score:.2f}")

    print("\nTHERMAL TRENDS")

    print(
        f"EGT: {assessment.egt_trend.direction} | "
        f"slope={assessment.egt_trend.slope:.3f} | "
        f"{assessment.egt_trend.severity}"
    )

    print(
        f"CHT: {assessment.cht_trend.direction} | "
        f"slope={assessment.cht_trend.slope:.3f} | "
        f"{assessment.cht_trend.severity}"
    )

    assert 0.0 <= assessment.health.health_score <= 100.0

    assert assessment.egt_trend.parameter == "EGT"
    assert assessment.cht_trend.parameter == "CHT"

    print("\nIntegrated health assessment successful.")