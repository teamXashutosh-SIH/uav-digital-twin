from dataclasses import dataclass

from packages.digital_twin.core import DigitalTwinState


@dataclass
class HealthAssessment:
    health_score: float
    status: str
    anomaly_score: float

    rpm_status: str
    cht_status: str
    egt_status: str
    oil_pressure_status: str
    oil_temperature_status: str
    fuel_flow_status: str
    vibration_status: str


class EngineHealthMonitor:
    """
    Rule-based engine health assessment.

    Development implementation for the AeroTwin demonstrator.

    Thresholds are engineering assumptions for synthetic data and
    are NOT validated aircraft-engine limits.

    Important:
    Different engine parameters have different meanings when they
    deviate from the Digital Twin expected state. Therefore the
    monitor uses direction-aware rules instead of treating every
    positive and negative deviation identically.
    """

    @staticmethod
    def _status(
        deviation: float,
        warning: float,
        critical: float,
    ) -> str:
        """
        Generic two-sided deviation status.

        Used for parameters where both positive and negative
        deviations can indicate abnormal behaviour.
        """
        magnitude = abs(deviation)

        if magnitude >= critical:
            return "CRITICAL"

        if magnitude >= warning:
            return "WARNING"

        return "NORMAL"

    @staticmethod
    def _positive_status(
        deviation: float,
        warning: float,
        critical: float,
    ) -> str:
        """
        One-sided status.

        Used when an increase above the Digital Twin expectation
        is the concerning direction.

        Negative deviation alone is not considered a fault.
        """
        if deviation >= critical:
            return "CRITICAL"

        if deviation >= warning:
            return "WARNING"

        return "NORMAL"

    @staticmethod
    def _negative_status(
        deviation: float,
        warning: float,
        critical: float,
    ) -> str:
        """
        One-sided status.

        Used when a decrease below the Digital Twin expectation
        is the concerning direction.
        """
        if deviation <= -critical:
            return "CRITICAL"

        if deviation <= -warning:
            return "WARNING"

        return "NORMAL"

    @staticmethod
    def health_score_for(
        critical_count: int,
        warning_count: int,
    ) -> float:
        score = (
            100.0
            - critical_count * 25.0
            - warning_count * 8.0
        )
        return max(10.0, min(100.0, score))

    def assess(self, twin_state: DigitalTwinState) -> HealthAssessment:

        d = twin_state.deviation

        # ---------------------------------------------------------
        # RPM
        # ---------------------------------------------------------
        # RPM can be abnormal in either direction.
        rpm_status = self._status(
            d.rpm,
            warning=100.0,
            critical=200.0,
        )

        # ---------------------------------------------------------
        # CHT
        # ---------------------------------------------------------
        # High CHT relative to the Digital Twin expectation is the
        # important thermal-health direction.
        #
        # A lower-than-expected CHT can occur during throttle
        # reduction, cooldown, startup settling, etc.
        cht_status = self._positive_status(
            d.cht_c,
            warning=8.0,
            critical=15.0,
        )

        # ---------------------------------------------------------
        # EGT
        # ---------------------------------------------------------
        # Elevated EGT is the concerning direction for combustion
        # and thermal degradation monitoring.
        egt_status = self._positive_status(
            d.egt_c,
            warning=20.0,
            critical=40.0,
        )

        # ---------------------------------------------------------
        # Oil Pressure
        # ---------------------------------------------------------
        # Low oil pressure is the concerning direction.
        oil_pressure_status = self._negative_status(
            d.oil_pressure_kpa,
            warning=30.0,
            critical=60.0,
        )

        # ---------------------------------------------------------
        # Oil Temperature
        # ---------------------------------------------------------
        # Elevated oil temperature is the concerning direction.
        oil_temperature_status = self._positive_status(
            d.oil_temperature_c,
            warning=8.0,
            critical=15.0,
        )

        # ---------------------------------------------------------
        # Fuel Flow
        # ---------------------------------------------------------
        # Both unusually high and unusually low fuel flow can be
        # useful indicators, so retain two-sided monitoring here.
        fuel_flow_status = self._status(
            d.fuel_flow_gph,
            warning=1.0,
            critical=2.0,
        )

        # ---------------------------------------------------------
        # Vibration
        # ---------------------------------------------------------
        # Excess vibration is the concerning direction.
        #
        # A negative deviation means vibration is lower than the
        # expected model value and is not treated as a fault.
        vibration_status = self._positive_status(
            d.vibration_g,
            warning=0.10,
            critical=0.20,
        )

        statuses = [
            rpm_status,
            cht_status,
            egt_status,
            oil_pressure_status,
            oil_temperature_status,
            fuel_flow_status,
            vibration_status,
        ]

        critical_count = statuses.count("CRITICAL")
        warning_count = statuses.count("WARNING")

        # ---------------------------------------------------------
        # Development anomaly score
        # ---------------------------------------------------------
        anomaly_score = min(
            1.0,
            (
                critical_count * 0.35
                + warning_count * 0.10
            ),
        )

        health_score = self.health_score_for(
            critical_count=critical_count,
            warning_count=warning_count,
        )

        if critical_count > 0:
            overall_status = "CRITICAL"
        elif warning_count > 0:
            overall_status = "WARNING"
        else:
            overall_status = "HEALTHY"

        return HealthAssessment(
            health_score=health_score,
            status=overall_status,
            anomaly_score=anomaly_score,

            rpm_status=rpm_status,
            cht_status=cht_status,
            egt_status=egt_status,
            oil_pressure_status=oil_pressure_status,
            oil_temperature_status=oil_temperature_status,
            fuel_flow_status=fuel_flow_status,
            vibration_status=vibration_status,
        )