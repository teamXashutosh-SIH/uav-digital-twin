from services.simulator.engine_simulator import EngineSimulator
from packages.digital_twin.core import EngineDigitalTwin
from packages.health.monitor import EngineHealthMonitor


def test_overheating_end_to_end():

    simulator = EngineSimulator(seed=42)
    twin = EngineDigitalTwin()
    monitor = EngineHealthMonitor()

    print("\n--- AEROTWIN END-TO-END OVERHEATING TEST ---")

    # ---------------------------------------------------------
    # NORMAL ENGINE
    # ---------------------------------------------------------

    normal_telemetry = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
    )

    normal_twin_state = twin.compare(normal_telemetry)
    normal_health = monitor.assess(normal_twin_state)

    print("\nNORMAL ENGINE")
    print(f"CHT:           {normal_telemetry.cht_c:.2f} °C")
    print(f"EGT:           {normal_telemetry.egt_c:.2f} °C")
    print(f"Health Score:  {normal_health.health_score:.1f}%")
    print(f"Status:        {normal_health.status}")

    # ---------------------------------------------------------
    # OVERHEATING ENGINE
    # ---------------------------------------------------------

    faulty_telemetry = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
        fault="overheating",
        fault_severity=1.0,
    )

    faulty_twin_state = twin.compare(faulty_telemetry)
    faulty_health = monitor.assess(faulty_twin_state)

    print("\nOVERHEATING ENGINE")
    print(f"CHT:           {faulty_telemetry.cht_c:.2f} °C")
    print(f"EGT:           {faulty_telemetry.egt_c:.2f} °C")
    print(f"CHT deviation: {faulty_twin_state.deviation.cht_c:.2f} °C")
    print(f"EGT deviation: {faulty_twin_state.deviation.egt_c:.2f} °C")
    print(f"Health Score:  {faulty_health.health_score:.1f}%")
    print(f"Status:        {faulty_health.status}")

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    assert faulty_telemetry.cht_c > normal_telemetry.cht_c
    assert faulty_telemetry.egt_c > normal_telemetry.egt_c

    assert faulty_twin_state.deviation.cht_c > (
        normal_twin_state.deviation.cht_c
    )

    assert faulty_twin_state.deviation.egt_c > (
        normal_twin_state.deviation.egt_c
    )

    print("\nEnd-to-end overheating detection successful.")