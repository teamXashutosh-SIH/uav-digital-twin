from services.simulator.engine_simulator import EngineSimulator


def test_overheating_fault():

    simulator = EngineSimulator(seed=42)

    normal = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
    )

    faulty = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
        fault="overheating",
        fault_severity=1.0,
    )

    print("\n--- OVERHEATING FAULT TEST ---")

    print(f"Normal CHT:  {normal.cht_c:.2f} °C")
    print(f"Fault CHT:   {faulty.cht_c:.2f} °C")

    print(f"Normal EGT:  {normal.egt_c:.2f} °C")
    print(f"Fault EGT:   {faulty.egt_c:.2f} °C")

    assert faulty.cht_c > normal.cht_c
    assert faulty.egt_c > normal.egt_c

    print("\nOverheating fault injection successful.")