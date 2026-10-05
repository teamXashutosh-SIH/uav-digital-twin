from services.simulator.engine_simulator import EngineSimulator
from services.ml.anomaly_detector import EngineAnomalyDetector


def telemetry_features(telemetry):

    return [
        telemetry.rpm,
        telemetry.cht_c,
        telemetry.egt_c,
        telemetry.oil_pressure_kpa,
        telemetry.oil_temperature_c,
        telemetry.fuel_flow_gph,
        telemetry.vibration_g,
    ]


def test_anomaly_detector():

    simulator = EngineSimulator(seed=42)

    normal_data = []

    # ---------------------------------------------------------
    # Generate normal operating data
    # ---------------------------------------------------------

    for _ in range(100):

        telemetry = simulator.step(
            throttle_pct=60.0,
            altitude_m=2000.0,
            ambient_temperature_c=25.0,
        )

        normal_data.append(
            telemetry_features(telemetry)
        )

    # ---------------------------------------------------------
    # Train ML model
    # ---------------------------------------------------------

    detector = EngineAnomalyDetector()

    detector.fit(normal_data)

    # ---------------------------------------------------------
    # Normal sample
    # ---------------------------------------------------------

    normal_sample = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
    )

    normal_result = detector.predict(
        telemetry_features(normal_sample)
    )

    # ---------------------------------------------------------
    # Overheating sample
    # ---------------------------------------------------------

    faulty_sample = simulator.step(
        throttle_pct=60.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
        fault="overheating",
        fault_severity=1.0,
    )

    faulty_result = detector.predict(
        telemetry_features(faulty_sample)
    )

    print("\n--- ML ANOMALY DETECTION TEST ---")

    print("\nNORMAL SAMPLE")
    print(
        f"Anomaly Score: "
        f"{normal_result.anomaly_score:.3f}"
    )
    print(
        f"Anomaly:       "
        f"{normal_result.is_anomaly}"
    )

    print("\nOVERHEATING SAMPLE")
    print(
        f"Anomaly Score: "
        f"{faulty_result.anomaly_score:.3f}"
    )
    print(
        f"Anomaly:       "
        f"{faulty_result.is_anomaly}"
    )

    assert 0.0 <= normal_result.anomaly_score <= 1.0
    assert 0.0 <= faulty_result.anomaly_score <= 1.0

    print("\nML anomaly detector executed successfully.")