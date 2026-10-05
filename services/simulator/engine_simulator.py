import math
import random
import time
from datetime import datetime, timezone

from packages.contracts.telemetry import (
    EngineTelemetry,
    QualityFlag,
)

from packages.digital_twin.performance_model import (
    EngineOperatingPoint,
    EnginePerformanceModel,
)


class EngineSimulator:
    """
    Synthetic UAV piston-engine telemetry simulator.

    The simulator uses the same nominal engine performance
    model as the Digital Twin and adds sensor noise and
    controlled fault effects.

    Development/demo model only.
    This is NOT a validated aircraft-engine thermodynamic model.
    """

    SUPPORTED_FAULTS = {
        "overheating",
        "low_oil_pressure",
        "abnormal_vibration",
        "combustion_anomaly",
        "sensor_drift",
    }

    def __init__(
        self,
        seed: int = 42,
    ):

        self.random = random.Random(seed)

        self.performance_model = (
            EnginePerformanceModel()
        )

        self.sequence = 0

        # Initial internal thermal/RPM state.
        self.rpm = 2400.0
        self.cht_c = 165.0
        self.egt_c = 690.0

        self.active_fault = None
        self.fault_severity = 0.0
        self.fault_duration = 0

    # =========================================================
    # FAULT CONTROL
    # =========================================================

    def inject_fault(
        self,
        fault: str,
        severity: float = 1.0,
    ) -> None:

        if fault not in self.SUPPORTED_FAULTS:
            raise ValueError(
                f"Unsupported fault '{fault}'. "
                f"Supported faults: "
                f"{sorted(self.SUPPORTED_FAULTS)}"
            )

        severity = max(0.0, min(1.0, severity))
        if self.active_fault == fault:
            self.fault_severity = severity
            return

        self.active_fault = fault

        self.fault_severity = severity

        self.fault_duration = 0

    def clear_fault(self) -> None:

        self.active_fault = None

        self.fault_severity = 0.0

        self.fault_duration = 0

    # =========================================================
    # MAIN SIMULATION STEP
    # =========================================================

    def step(
        self,
        throttle_pct: float = 60.0,
        altitude_m: float = 2000.0,
        ambient_temperature_c: float = 25.0,
        fault: str | None = None,
        fault_severity: float = 0.0,
        vehicle_id: str = "UAV-DEMO-001",
        engine_id: str = "ENGINE-001",
        mission_id: str = "MISSION-DEMO-001",
        timestamp: datetime | None = None,
    ) -> EngineTelemetry:

        # -----------------------------------------------------
        # COMMON ENGINE PERFORMANCE MODEL
        # -----------------------------------------------------

        operating_point = EngineOperatingPoint(
            throttle_pct=throttle_pct,
            altitude_m=altitude_m,
            ambient_temperature_c=(
                ambient_temperature_c
            ),
        )

        nominal_state = (
            self.performance_model.estimate(
                operating_point
            )
        )

        # -----------------------------------------------------
        # NORMAL RPM DYNAMICS
        # -----------------------------------------------------

        self.rpm += (
            nominal_state.rpm
            - self.rpm
        ) * 0.15

        self.rpm += self.random.gauss(
            0,
            8.0,
        )

        # -----------------------------------------------------
        # ACTIVE FAULT
        # -----------------------------------------------------

        active_fault = (
            fault
            if fault is not None
            else self.active_fault
        )

        active_severity = (
            fault_severity
            if fault is not None
            else self.fault_severity
        )

        if active_fault is not None:
            self.fault_duration += 1

        progression = min(
            self.fault_duration / 20.0,
            1.0,
        )

        # -----------------------------------------------------
        # FAULT EFFECTS
        # -----------------------------------------------------

        overheating_cht = 0.0
        overheating_egt = 0.0
        overheating_oil = 0.0
        overheating_vibration = 0.0

        oil_pressure_drop = 0.0

        vibration_increase = 0.0

        combustion_egt_change = 0.0
        combustion_rpm_drop = 0.0

        sensor_egt_drift = 0.0

        if active_fault == "overheating":

            overheating_cht = (
                80.0
                * active_severity
                * progression
            )

            overheating_egt = (
                180.0
                * active_severity
                * progression
            )

            overheating_oil = (
                35.0
                * active_severity
                * progression
            )

            overheating_vibration = (
                0.30
                * active_severity
                * progression
            )

        elif active_fault == "low_oil_pressure":

            oil_pressure_drop = (
                180.0
                * active_severity
                * progression
            )

        elif active_fault == "abnormal_vibration":

            vibration_increase = (
                0.60
                * active_severity
                * progression
            )

        elif active_fault == "combustion_anomaly":

            combustion_egt_change = (
                120.0
                * active_severity
                * progression
            )

            combustion_rpm_drop = (
                180.0
                * active_severity
                * progression
            )

        elif active_fault == "sensor_drift":

            sensor_egt_drift = (
                100.0
                * active_severity
                * progression
            )

        # -----------------------------------------------------
        # THERMAL STATE
        # -----------------------------------------------------

        target_cht = (
            nominal_state.cht_c
            + overheating_cht
        )

        target_egt = (
            nominal_state.egt_c
            + overheating_egt
            + combustion_egt_change
        )

        self.cht_c += (
            target_cht
            - self.cht_c
        ) * 0.35

        self.egt_c += (
            target_egt
            - self.egt_c
        ) * 0.35

        self.cht_c += self.random.gauss(
            0,
            0.6,
        )

        self.egt_c += self.random.gauss(
            0,
            2.5,
        )

        # -----------------------------------------------------
        # COMBUSTION RPM EFFECT
        # -----------------------------------------------------

        self.rpm -= (
            combustion_rpm_drop
            * 0.20
        )

        # -----------------------------------------------------
        # OIL SYSTEM
        # -----------------------------------------------------

        oil_pressure_kpa = (
            nominal_state.oil_pressure_kpa
            + (
                self.rpm
                - nominal_state.rpm
            ) * 0.08
            - oil_pressure_drop
            + self.random.gauss(
                0,
                5.0,
            )
        )

        oil_temperature_c = (
            nominal_state.oil_temperature_c
            + overheating_oil
            + self.random.gauss(
                0,
                1.0,
            )
        )

        # -----------------------------------------------------
        # FUEL SYSTEM
        # -----------------------------------------------------

        fuel_flow_gph = (
            nominal_state.fuel_flow_gph
            + self.random.gauss(
                0,
                0.08,
            )
        )

        # -----------------------------------------------------
        # VIBRATION
        # -----------------------------------------------------

        vibration_g = (
            nominal_state.vibration_g
            + abs(
                math.sin(
                    self.sequence * 0.1
                )
            ) * 0.08
            + overheating_vibration
            + vibration_increase
            + self.random.gauss(
                0,
                0.01,
            )
        )

        # -----------------------------------------------------
        # ELECTRICAL
        # -----------------------------------------------------

        battery_voltage_v = (
            24.0
            + self.random.gauss(
                0,
                0.15,
            )
        )

        alternator_current_a = (
            8.0
            + throttle_pct * 0.04
            + self.random.gauss(
                0,
                0.3,
            )
        )

        injection_timing_deg = (
            25.0
            + self.random.gauss(
                0,
                0.2,
            )
        )

        # -----------------------------------------------------
        # SENSOR DRIFT
        # -----------------------------------------------------

        measured_egt = (
            self.egt_c
            + sensor_egt_drift
        )

        # -----------------------------------------------------
        # TELEMETRY
        # -----------------------------------------------------

        telemetry = EngineTelemetry(
            vehicle_id=vehicle_id,

            engine_id=engine_id,

            mission_id=mission_id,

            sequence=self.sequence,

            timestamp=timestamp or datetime.now(timezone.utc),

            rpm=self.rpm,

            cht_c=self.cht_c,

            egt_c=measured_egt,

            oil_pressure_kpa=(
                oil_pressure_kpa
            ),

            oil_temperature_c=(
                oil_temperature_c
            ),

            fuel_flow_gph=(
                fuel_flow_gph
            ),

            vibration_g=(
                vibration_g
            ),

            battery_voltage_v=(
                battery_voltage_v
            ),

            alternator_current_a=(
                alternator_current_a
            ),

            injection_timing_deg=(
                injection_timing_deg
            ),

            altitude_m=altitude_m,

            ambient_temperature_c=(
                ambient_temperature_c
            ),

            throttle_pct=throttle_pct,

            quality_flags=[
                QualityFlag.SIMULATED
            ],
        )

        self.sequence += 1

        return telemetry


# =============================================================
# STANDALONE TEST
# =============================================================

if __name__ == "__main__":

    simulator = EngineSimulator()

    for _ in range(10):

        telemetry = simulator.step()

        print(
            telemetry.model_dump_json(
                indent=2
            )
        )

        time.sleep(1)