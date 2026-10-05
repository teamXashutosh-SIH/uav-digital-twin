from datetime import datetime, timezone

from packages.contracts.telemetry import EngineTelemetry, QualityFlag
from packages.digital_twin.core import EngineDigitalTwin
from services.ml.features import build_ml_features


def test_ml_feature_vector():

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

    features = build_ml_features(
        twin_state=twin_state,
        egt_trend_slope=3.5,
        cht_trend_slope=1.2,
    )

    print("\n--- ML FEATURE ENGINEERING TEST ---")

    print(f"Feature count: {len(features)}")
    print("Feature vector:")
    print(features)

    assert len(features) == 16

    assert features[0] == telemetry.rpm
    assert features[1] == telemetry.cht_c
    assert features[2] == telemetry.egt_c

    assert features[9] == twin_state.deviation.egt_c

    assert features[14] == 3.5
    assert features[15] == 1.2

    print("\nML feature engineering successful.")