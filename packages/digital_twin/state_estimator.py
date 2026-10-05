from dataclasses import dataclass

from packages.digital_twin.core import DigitalTwinState
from packages.health.engine_health import (
    IntegratedHealthAssessment,
)


@dataclass
class EngineState:
    """
    Structured representation of the current engine condition.

    The state is derived from the integrated Health Engine
    assessment together with the current Digital Twin state.

    Development/demo state model.
    """

    operating_mode: str
    overall_health: str
    thermal_state: str
    lubrication_state: str
    combustion_state: str
    mechanical_state: str
    electrical_state: str
    sensor_confidence: str


class EngineStateEstimator:
    """
    Converts the integrated Health Engine assessment into
    a higher-level structured engine state.

    The Health Engine remains the source of truth for
    parameter health thresholds.

    The Digital Twin state supplies the current telemetry
    needed for operating mode, electrical state and
    sensor-confidence interpretation.
    """

    def estimate(
        self,
        assessment: IntegratedHealthAssessment,
        twin_state: DigitalTwinState,
    ) -> EngineState:

        health = assessment.health
        telemetry = twin_state.observed

        # =====================================================
        # OPERATING MODE
        # =====================================================

        throttle = telemetry.throttle_pct

        if throttle < 20:
            operating_mode = "IDLE"

        elif throttle < 45:
            operating_mode = "LOW_LOAD"

        elif throttle < 75:
            operating_mode = "CRUISE"

        else:
            operating_mode = "HIGH_LOAD"

        # =====================================================
        # THERMAL STATE
        # =====================================================

        thermal_states = [
            health.cht_status,
            health.egt_status,
            health.oil_temperature_status,
        ]

        thermal_trend_states = [
            assessment.egt_trend.severity,
            assessment.cht_trend.severity,
        ]

        if "CRITICAL" in thermal_states:

            thermal_state = "CRITICAL"

        elif "CRITICAL" in thermal_trend_states:

            thermal_state = "CRITICAL"

        elif "WARNING" in thermal_states:

            thermal_state = "WARNING"

        elif "WARNING" in thermal_trend_states:

            thermal_state = "WARNING"

        else:

            thermal_state = "NORMAL"

        # =====================================================
        # LUBRICATION STATE
        # =====================================================

        lubrication_states = [
            health.oil_pressure_status,
            health.oil_temperature_status,
        ]

        if "CRITICAL" in lubrication_states:

            lubrication_state = "CRITICAL"

        elif "WARNING" in lubrication_states:

            lubrication_state = "WARNING"

        else:

            lubrication_state = "NORMAL"

        # =====================================================
        # COMBUSTION STATE
        # =====================================================

        combustion_states = [
            health.egt_status,
            health.rpm_status,
            assessment.egt_trend.severity,
        ]

        if "CRITICAL" in combustion_states:

            combustion_state = "CRITICAL"

        elif "WARNING" in combustion_states:

            combustion_state = "WARNING"

        else:

            combustion_state = "NORMAL"

        # =====================================================
        # MECHANICAL STATE
        # =====================================================

        mechanical_states = [
            health.vibration_status,
        ]

        if "CRITICAL" in mechanical_states:

            mechanical_state = "CRITICAL"

        elif "WARNING" in mechanical_states:

            mechanical_state = "WARNING"

        else:

            mechanical_state = "NORMAL"

        # =====================================================
        # ELECTRICAL STATE
        # =====================================================

        battery_voltage = telemetry.battery_voltage_v
        alternator_current = telemetry.alternator_current_a

        if (
            battery_voltage < 21.0
            or alternator_current < 3.0
        ):

            electrical_state = "CRITICAL"

        elif (
            battery_voltage < 23.0
            or alternator_current < 5.0
        ):

            electrical_state = "WARNING"

        else:

            electrical_state = "NORMAL"

        # =====================================================
        # SENSOR CONFIDENCE
        # =====================================================

        quality_flags = telemetry.quality_flags

        if quality_flags:

            sensor_confidence = "MEDIUM"

        else:

            sensor_confidence = "HIGH"

        # =====================================================
        # OVERALL HEALTH
        # =====================================================

        overall_health = health.status

        # =====================================================
        # RETURN ENGINE STATE
        # =====================================================

        return EngineState(

            operating_mode=(
                operating_mode
            ),

            overall_health=(
                overall_health
            ),

            thermal_state=(
                thermal_state
            ),

            lubrication_state=(
                lubrication_state
            ),

            combustion_state=(
                combustion_state
            ),

            mechanical_state=(
                mechanical_state
            ),

            electrical_state=(
                electrical_state
            ),

            sensor_confidence=(
                sensor_confidence
            ),
        )