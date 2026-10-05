from datetime import datetime, timezone

from packages.contracts.telemetry import EngineTelemetry, QualityFlag
from packages.digital_twin.core import EngineDigitalTwin
from packages.health.monitor import EngineHealthMonitor


def test_healthy_engine():

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

    twin_state = twin.compare(telemetry)

    monitor = EngineHealthMonitor()

    assessment = monitor.assess(twin_state)

    print("\n--- HEALTH MONITORING TEST ---")

    print(f"Health Score:   {assessment.health_score:.1f}%")
    print(f"Status:         {assessment.status}")
    print(f"Anomaly Score:  {assessment.anomaly_score:.2f}")

    print(f"RPM:            {assessment.rpm_status}")
    print(f"CHT:            {assessment.cht_status}")
    print(f"EGT:            {assessment.egt_status}")
    print(f"Oil Pressure:   {assessment.oil_pressure_status}")
    print(f"Oil Temperature:{assessment.oil_temperature_status}")
    print(f"Fuel Flow:      {assessment.fuel_flow_status}")
    print(f"Vibration:      {assessment.vibration_status}")

    assert 0.0 <= assessment.health_score <= 100.0
    assert 0.0 <= assessment.anomaly_score <= 1.0
    assert assessment.status in {
        "HEALTHY",
        "WARNING",
        "CRITICAL",
    }

    print("\nHealth monitoring successful.")