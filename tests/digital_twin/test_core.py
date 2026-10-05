from datetime import datetime, timezone

from packages.contracts.telemetry import EngineTelemetry, QualityFlag
from packages.digital_twin.core import EngineDigitalTwin


def test_digital_twin_comparison():

    telemetry = EngineTelemetry(
        vehicle_id="UAV-DEMO-001",
        engine_id="ENGINE-001",
        mission_id="MISSION-DEMO-001",

        sequence=1,
        timestamp=datetime.now(timezone.utc),

        rpm=2520.0,
        cht_c=170.0,
        egt_c=690.0,

        oil_pressure_kpa=485.0,
        oil_temperature_c=92.0,

        fuel_flow_gph=9.7,
        vibration_g=0.32,

        battery_voltage_v=24.0,
        alternator_current_a=10.0,

        injection_timing_deg=25.0,

        altitude_m=2000.0,
        ambient_temperature_c=25.0,
        throttle_pct=60.0,

        quality_flags=[QualityFlag.SIMULATED],
    )

    twin = EngineDigitalTwin()

    state = twin.compare(telemetry)

    print("\n--- DIGITAL TWIN TEST ---")

    print(f"Observed RPM:   {state.observed.rpm:.2f}")
    print(f"Expected RPM:   {state.expected.rpm:.2f}")
    print(f"RPM deviation:  {state.deviation.rpm:.2f}")

    print(f"Observed EGT:   {state.observed.egt_c:.2f}")
    print(f"Expected EGT:   {state.expected.egt_c:.2f}")
    print(f"EGT deviation:  {state.deviation.egt_c:.2f}")

    print(f"Observed CHT:   {state.observed.cht_c:.2f}")
    print(f"Expected CHT:   {state.expected.cht_c:.2f}")
    print(f"CHT deviation:  {state.deviation.cht_c:.2f}")

    assert state.expected.rpm > 0
    assert state.expected.egt_c > 0
    assert state.expected.cht_c > 0

    print("\nDigital Twin comparison successful.")