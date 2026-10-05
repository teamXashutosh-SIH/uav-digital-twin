from dataclasses import dataclass


@dataclass
class EngineOperatingPoint:
    """
    Operating conditions used by the engine performance model.
    """

    throttle_pct: float
    altitude_m: float
    ambient_temperature_c: float


@dataclass
class EnginePerformanceState:
    """
    Expected engine behavior calculated from the
    development engine performance model.

    This is a synthetic/development model and is NOT
    a validated aircraft-engine thermodynamic model.
    """

    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_gph: float
    vibration_g: float


class EnginePerformanceModel:
    """
    Development engine performance model for AeroTwin.

    The model estimates nominal engine behavior from
    throttle, altitude and ambient temperature.

    This model is intentionally deterministic so that
    both the simulator and Digital Twin can use the
    same nominal performance assumptions.
    """

    def estimate(
        self,
        operating_point: EngineOperatingPoint,
    ) -> EnginePerformanceState:

        throttle_pct = (
            operating_point.throttle_pct
        )

        altitude_m = (
            operating_point.altitude_m
        )

        ambient_temperature_c = (
            operating_point.ambient_temperature_c
        )

        throttle = throttle_pct / 100.0

        expected_rpm = (
            1200.0
            + throttle_pct * 22.0
        )

        expected_cht = (
            ambient_temperature_c
            + 85.0
            + 100.0 * throttle
            + (altitude_m / 10000.0) * 10.0
        )

        expected_egt = (
            400.0
            + 450.0 * throttle
            + ambient_temperature_c * 0.5
        )

        expected_oil_pressure = (
            280.0
            + expected_rpm * 0.08
        )

        expected_oil_temperature = (
            70.0
            + throttle_pct * 0.35
        )

        expected_fuel_flow = (
            2.5
            + throttle_pct * 0.12
        )

        expected_vibration = 0.25

        return EnginePerformanceState(
            rpm=expected_rpm,
            cht_c=expected_cht,
            egt_c=expected_egt,
            oil_pressure_kpa=(
                expected_oil_pressure
            ),
            oil_temperature_c=(
                expected_oil_temperature
            ),
            fuel_flow_gph=(
                expected_fuel_flow
            ),
            vibration_g=(
                expected_vibration
            ),
        )