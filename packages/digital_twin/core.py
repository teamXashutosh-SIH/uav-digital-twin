from dataclasses import dataclass

from packages.contracts.telemetry import (
    EngineTelemetry,
)

from packages.digital_twin.performance_model import (
    EngineOperatingPoint,
    EnginePerformanceModel,
)


@dataclass
class ExpectedEngineState:
    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_gph: float
    vibration_g: float


@dataclass
class EngineDeviation:
    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_gph: float
    vibration_g: float


@dataclass
class DigitalTwinState:
    observed: EngineTelemetry
    expected: ExpectedEngineState
    deviation: EngineDeviation


class EngineDigitalTwin:
    """
    Development Digital Twin model for the AeroTwin
    demonstrator.

    The Digital Twin combines:
      1. A steady-state engine performance model.
      2. A dynamic expected-state model.

    The dynamic layer prevents large false deviations during
    legitimate operating-point transitions such as rapid
    throttle changes.

    This is a synthetic/development model and is NOT
    a validated aircraft-engine thermodynamic model.
    """

    # Dynamic response coefficients.
    #
    # These mirror the response behavior used by the
    # development simulator:
    #
    # RPM:
    #     new = old + 0.15 * (target - old)
    #
    # Thermal state:
    #     new = old + 0.35 * (target - old)
    #
    RPM_RESPONSE = 0.15
    THERMAL_RESPONSE = 0.35

    def __init__(self):

        self.performance_model = (
            EnginePerformanceModel()
        )

        # Dynamic expected-state memory.
        self._expected_rpm = None
        self._expected_cht = None
        self._expected_egt = None

        self._expected_oil_pressure = None
        self._expected_oil_temperature = None
        self._expected_fuel_flow = None
        self._expected_vibration = None

        self._initialized = False

    def reset(self) -> None:
        """
        Reset the Digital Twin dynamic state.

        A reset is required between independent mission
        simulations so that one mission does not influence
        another mission's expected state.
        """

        self._expected_rpm = None
        self._expected_cht = None
        self._expected_egt = None

        self._expected_oil_pressure = None
        self._expected_oil_temperature = None
        self._expected_fuel_flow = None
        self._expected_vibration = None

        self._initialized = False

    def _steady_state(
        self,
        throttle_pct: float,
        altitude_m: float,
        ambient_temperature_c: float,
    ):
        """
        Calculate the steady-state nominal target from
        the common development performance model.
        """

        operating_point = EngineOperatingPoint(
            throttle_pct=throttle_pct,
            altitude_m=altitude_m,
            ambient_temperature_c=(
                ambient_temperature_c
            ),
        )

        return self.performance_model.estimate(
            operating_point
        )

    def estimate_expected_state(
        self,
        throttle_pct: float,
        altitude_m: float,
        ambient_temperature_c: float,
    ) -> ExpectedEngineState:

        performance_state = self._steady_state(
            throttle_pct=throttle_pct,
            altitude_m=altitude_m,
            ambient_temperature_c=(
                ambient_temperature_c
            ),
        )

        # -----------------------------------------------------
        # FIRST SAMPLE
        # -----------------------------------------------------
        #
        # We initialize the dynamic Digital Twin state to the
        # steady-state target. This avoids an artificial
        # startup transient.
        #

        if not self._initialized:

            self._expected_rpm = performance_state.rpm
            self._expected_cht = performance_state.cht_c
            self._expected_egt = performance_state.egt_c

            self._expected_oil_pressure = (
                performance_state.oil_pressure_kpa
            )

            self._expected_oil_temperature = (
                performance_state.oil_temperature_c
            )

            self._expected_fuel_flow = (
                performance_state.fuel_flow_gph
            )

            self._expected_vibration = (
                performance_state.vibration_g
            )

            self._initialized = True

        # -----------------------------------------------------
        # DYNAMIC EXPECTED STATE
        # -----------------------------------------------------
        #
        # The Digital Twin does NOT instantly jump to the new
        # operating point.
        #
        # Instead, it follows the target just as a physical
        # engine responds over time.
        #

        self._expected_rpm += (
            performance_state.rpm
            - self._expected_rpm
        ) * self.RPM_RESPONSE

        self._expected_cht += (
            performance_state.cht_c
            - self._expected_cht
        ) * self.THERMAL_RESPONSE

        self._expected_egt += (
            performance_state.egt_c
            - self._expected_egt
        ) * self.THERMAL_RESPONSE

        # Oil pressure is strongly coupled to RPM in the
        # development performance model.
        target_oil_pressure = (
            performance_state.oil_pressure_kpa
        )

        self._expected_oil_pressure += (
            target_oil_pressure
            - self._expected_oil_pressure
        ) * self.RPM_RESPONSE

        self._expected_oil_temperature += (
            performance_state.oil_temperature_c
            - self._expected_oil_temperature
        ) * self.THERMAL_RESPONSE

        # Fuel flow follows throttle more directly than the
        # thermal variables.
        self._expected_fuel_flow += (
            performance_state.fuel_flow_gph
            - self._expected_fuel_flow
        ) * self.RPM_RESPONSE

        # Vibration has no dynamic thermal component in the
        # current development model, so it can follow the
        # nominal target directly.
        self._expected_vibration = (
            performance_state.vibration_g
        )

        return ExpectedEngineState(
            rpm=self._expected_rpm,
            cht_c=self._expected_cht,
            egt_c=self._expected_egt,
            oil_pressure_kpa=(
                self._expected_oil_pressure
            ),
            oil_temperature_c=(
                self._expected_oil_temperature
            ),
            fuel_flow_gph=(
                self._expected_fuel_flow
            ),
            vibration_g=(
                self._expected_vibration
            ),
        )

    def compare(
        self,
        telemetry: EngineTelemetry,
    ) -> DigitalTwinState:

        expected = self.estimate_expected_state(
            throttle_pct=telemetry.throttle_pct,
            altitude_m=telemetry.altitude_m,
            ambient_temperature_c=(
                telemetry.ambient_temperature_c
            ),
        )

        deviation = EngineDeviation(
            rpm=(
                telemetry.rpm
                - expected.rpm
            ),

            cht_c=(
                telemetry.cht_c
                - expected.cht_c
            ),

            egt_c=(
                telemetry.egt_c
                - expected.egt_c
            ),

            oil_pressure_kpa=(
                telemetry.oil_pressure_kpa
                - expected.oil_pressure_kpa
            ),

            oil_temperature_c=(
                telemetry.oil_temperature_c
                - expected.oil_temperature_c
            ),

            fuel_flow_gph=(
                telemetry.fuel_flow_gph
                - expected.fuel_flow_gph
            ),

            vibration_g=(
                telemetry.vibration_g
                - expected.vibration_g
            ),
        )

        return DigitalTwinState(
            observed=telemetry,
            expected=expected,
            deviation=deviation,
        )