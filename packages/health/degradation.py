from dataclasses import dataclass
from collections import deque

from packages.digital_twin.core import DigitalTwinState


@dataclass
class DegradationResult:
    """
    Represents the current estimated engine degradation.

    This is a development/demo degradation model based on
    synthetic telemetry and Digital Twin deviations.

    It is NOT a validated aircraft-engine prognostics model.
    """

    degradation_index: float
    degradation_level: str

    egt_indicator: float
    cht_indicator: float
    oil_pressure_indicator: float
    vibration_indicator: float
    performance_indicator: float

    trend: str
    trend_rate: float


class EngineDegradationTracker:
    """
    Tracks gradual engine degradation using recent Digital Twin
    deviation history.

    Operating-condition transitions are handled explicitly so
    short-lived throttle/RPM transients do not become persistent
    degradation.

    The tracker does not diagnose a specific fault.

    Instead, it looks for persistent deterioration in engine
    performance and operating parameters.
    """

    def __init__(
        self,
        history_size: int = 60,
    ):

        self.history_size = history_size

        self.egt_history = deque(
            maxlen=history_size
        )

        self.cht_history = deque(
            maxlen=history_size
        )

        self.oil_pressure_history = deque(
            maxlen=history_size
        )

        self.vibration_history = deque(
            maxlen=history_size
        )

        self.performance_history = deque(
            maxlen=history_size
        )

        self.degradation_history = deque(
            maxlen=history_size
        )

    # =========================================================
    # NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize(
        value: float,
        warning_limit: float,
        critical_limit: float,
    ) -> float:
        """
        Convert a deviation into a normalized degradation
        indicator between 0 and 1.
        """

        magnitude = abs(
            float(value)
        )

        if magnitude <= warning_limit:
            return 0.0

        if magnitude >= critical_limit:
            return 1.0

        return (
            magnitude
            - warning_limit
        ) / (
            critical_limit
            - warning_limit
        )

    # =========================================================
    # TREND CALCULATION
    # =========================================================

    @staticmethod
    def _calculate_trend(
        history,
    ) -> float:
        """
        Calculate a simple linear trend rate.

        Positive value:
            degradation is increasing.

        Negative value:
            degradation is decreasing.

        Zero:
            approximately stable.
        """

        if len(history) < 5:
            return 0.0

        values = list(history)

        n = len(values)

        x_mean = (
            sum(
                range(n)
            )
            / n
        )

        y_mean = (
            sum(values)
            / n
        )

        numerator = 0.0
        denominator = 0.0

        for i, value in enumerate(
            values
        ):

            numerator += (
                (i - x_mean)
                * (value - y_mean)
            )

            denominator += (
                (i - x_mean) ** 2
            )

        if denominator == 0:
            return 0.0

        return (
            numerator
            / denominator
        )

    # =========================================================
    # DEGRADATION LEVEL
    # =========================================================

    @staticmethod
    def _classify_level(
        degradation_index: float,
    ) -> str:

        if degradation_index >= 0.70:
            return "SEVERE"

        if degradation_index >= 0.45:
            return "MODERATE"

        if degradation_index >= 0.20:
            return "EARLY"

        return "NORMAL"

    # =========================================================
    # TRANSIENT DETECTION
    # =========================================================

    @staticmethod
    def _is_transient_dominated(
        twin_state: DigitalTwinState,
        is_transition: bool,
    ) -> bool:
        """
        Determine whether the current deviation pattern is
        dominated by a normal operating-point transition.

        A transition is considered transient-dominated only when
        RPM is strongly displaced while the independent thermal,
        lubrication and vibration signals remain reasonably normal.

        This prevents rapid throttle changes from being accumulated
        as long-term engine degradation.
        """

        if not is_transition:
            return False

        deviation = twin_state.deviation

        return (
            abs(deviation.rpm) > 200.0
            and abs(deviation.cht_c) < 25.0
            and abs(deviation.egt_c) < 80.0
            and abs(deviation.oil_temperature_c) < 15.0
            and deviation.oil_pressure_kpa > -60.0
            and deviation.vibration_g < 0.25
        )

    # =========================================================
    # UPDATE
    # =========================================================

    def update(
        self,
        twin_state: DigitalTwinState,
        is_transition: bool = False,
    ) -> DegradationResult:
        """
        Update degradation state using the latest Digital Twin
        comparison.

        `is_transition` provides operating-condition context.

        Normal transition-dominated deviations are discounted
        rather than being treated as persistent degradation.
        """

        deviation = twin_state.deviation

        # -----------------------------------------------------
        # INDIVIDUAL DEGRADATION INDICATORS
        # -----------------------------------------------------

        egt_indicator = self._normalize(
            value=deviation.egt_c,
            warning_limit=20.0,
            critical_limit=100.0,
        )

        cht_indicator = self._normalize(
            value=deviation.cht_c,
            warning_limit=10.0,
            critical_limit=50.0,
        )

        # For oil pressure, only a reduction from expected
        # pressure represents degradation.

        oil_pressure_drop = max(
            0.0,
            -deviation.oil_pressure_kpa,
        )

        oil_pressure_indicator = self._normalize(
            value=oil_pressure_drop,
            warning_limit=30.0,
            critical_limit=120.0,
        )

        vibration_indicator = self._normalize(
            value=deviation.vibration_g,
            warning_limit=0.10,
            critical_limit=0.50,
        )

        # Performance degradation is represented by persistent
        # RPM deviation from the Digital Twin expectation.

        performance_indicator = self._normalize(
            value=deviation.rpm,
            warning_limit=50.0,
            critical_limit=200.0,
        )

        # -----------------------------------------------------
        # TRANSIENT CONTEXT
        # -----------------------------------------------------

        transient_dominated = (
            self._is_transient_dominated(
                twin_state=twin_state,
                is_transition=is_transition,
            )
        )

        if transient_dominated:
            # RPM response is expected to be the largest
            # temporary deviation during a throttle transition.
            #
            # Do not accumulate that temporary RPM response
            # as long-term performance degradation.

            performance_indicator = 0.0

            # Small residual thermal/lubrication deviations
            # are discounted during a transient-dominated
            # operating-point change.
            egt_indicator *= 0.25
            cht_indicator *= 0.50
            oil_pressure_indicator *= 0.25

            # Vibration can respond slightly to rapid throttle,
            # therefore discount it but do not completely erase it.
            vibration_indicator *= 0.50

        # -----------------------------------------------------
        # STORE HISTORY
        # -----------------------------------------------------

        self.egt_history.append(
            egt_indicator
        )

        self.cht_history.append(
            cht_indicator
        )

        self.oil_pressure_history.append(
            oil_pressure_indicator
        )

        self.vibration_history.append(
            vibration_indicator
        )

        self.performance_history.append(
            performance_indicator
        )

        # -----------------------------------------------------
        # CURRENT DEGRADATION INDEX
        # -----------------------------------------------------

        degradation_index = (
            0.30 * egt_indicator
            + 0.20 * cht_indicator
            + 0.20 * oil_pressure_indicator
            + 0.15 * vibration_indicator
            + 0.15 * performance_indicator
        )

        degradation_index = max(
            0.0,
            min(
                1.0,
                degradation_index,
            ),
        )

        self.degradation_history.append(
            degradation_index
        )

        # -----------------------------------------------------
        # LONG-TERM TREND
        # -----------------------------------------------------

        trend_rate = self._calculate_trend(
            self.degradation_history
        )

        if trend_rate > 0.005:
            trend = "INCREASING"

        elif trend_rate < -0.005:
            trend = "DECREASING"

        else:
            trend = "STABLE"

        # -----------------------------------------------------
        # CLASSIFY DEGRADATION
        # -----------------------------------------------------

        degradation_level = self._classify_level(
            degradation_index
        )

        # -----------------------------------------------------
        # RESULT
        # -----------------------------------------------------

        return DegradationResult(

            degradation_index=(
                float(
                    degradation_index
                )
            ),

            degradation_level=(
                degradation_level
            ),

            egt_indicator=(
                float(
                    egt_indicator
                )
            ),

            cht_indicator=(
                float(
                    cht_indicator
                )
            ),

            oil_pressure_indicator=(
                float(
                    oil_pressure_indicator
                )
            ),

            vibration_indicator=(
                float(
                    vibration_indicator
                )
            ),

            performance_indicator=(
                float(
                    performance_indicator
                )
            ),

            trend=(
                trend
            ),

            trend_rate=(
                float(
                    trend_rate
                )
            ),
        )