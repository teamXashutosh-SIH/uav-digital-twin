from packages.digital_twin.core import DigitalTwinState


def build_ml_features(
    twin_state: DigitalTwinState,
    egt_trend_slope: float = 0.0,
    cht_trend_slope: float = 0.0,
) -> list[float]:
    """
    Build the ML feature vector from observed telemetry,
    Digital Twin residuals, and thermal trends.

    Development feature set for synthetic AeroTwin data.
    """

    telemetry = twin_state.observed
    deviation = twin_state.deviation

    return [
        # Raw telemetry
        telemetry.rpm,
        telemetry.cht_c,
        telemetry.egt_c,
        telemetry.oil_pressure_kpa,
        telemetry.oil_temperature_c,
        telemetry.fuel_flow_gph,
        telemetry.vibration_g,

        # Digital Twin residuals
        deviation.rpm,
        deviation.cht_c,
        deviation.egt_c,
        deviation.oil_pressure_kpa,
        deviation.oil_temperature_c,
        deviation.fuel_flow_gph,
        deviation.vibration_g,

        # Thermal trends
        egt_trend_slope,
        cht_trend_slope,
    ]