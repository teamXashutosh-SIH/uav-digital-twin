from dataclasses import dataclass
from collections import deque


@dataclass
class RULResult:
    """
    Remaining Useful Life estimation result.

    This is a development/demo prognostics model based on
    the synthetic degradation trajectory.

    It is NOT a validated aircraft-engine RUL model.

    The reported RUL is an operating-hour-equivalent
    demonstration estimate based on configurable assumptions.
    """

    rul_samples: float
    rul_hours: float

    degradation_index: float
    degradation_rate: float

    confidence: float
    status: str


class EngineRULEstimator:
    """
    Development/demo RUL estimator.

    The estimator observes the evolution of the engine
    degradation index and estimates the remaining distance
    to a configurable critical degradation level.

    IMPORTANT:

    This is NOT a physics-validated or field-validated
    aircraft-engine prognostics model.

    The conversion from degradation progression to
    operating hours is a demonstration assumption.
    """

    def __init__(
        self,
        history_size: int = 60,
        sample_interval_seconds: float = 1.0,
        critical_degradation: float = 1.0,
        minimum_rul_hours: float = 100.0,
        maximum_rul_hours: float = 5000.0,
    ):

        self.history_size = history_size

        self.sample_interval_seconds = (
            sample_interval_seconds
        )

        self.critical_degradation = (
            critical_degradation
        )

        self.minimum_rul_hours = (
            minimum_rul_hours
        )

        self.maximum_rul_hours = (
            maximum_rul_hours
        )

        self.degradation_history = deque(
            maxlen=history_size
        )

    @staticmethod
    def _calculate_rate(
        history,
    ) -> float:
        """
        Calculate the linear degradation slope
        per observation.
        """

        if len(history) < 5:
            return 0.0

        values = list(history)

        n = len(values)

        x_mean = (
            sum(range(n))
            / n
        )

        y_mean = (
            sum(values)
            / n
        )

        numerator = 0.0
        denominator = 0.0

        for i, value in enumerate(values):

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

    def _calculate_confidence(self) -> float:

        samples = len(
            self.degradation_history
        )

        if samples < 5:
            return 0.20

        if samples < 10:
            return 0.40

        if samples < 20:
            return 0.60

        if samples < 40:
            return 0.80

        return 0.90

    def _calculate_rul_hours(
        self,
        degradation_index: float,
        degradation_rate: float,
    ) -> float:
        """
        Convert the degradation trajectory into a
        demonstration operating-hour estimate.

        The raw sample-based extrapolation is NOT treated
        as real engine hours.

        Instead, a configurable demonstration horizon is
        used to map degradation progression into an
        operating-hour-equivalent value.
        """

        if degradation_index <= 0.05:
            return self.maximum_rul_hours

        if degradation_rate <= 0.000001:
            return self.maximum_rul_hours

        remaining_degradation = max(
            0.0,
            self.critical_degradation
            - degradation_index,
        )

        raw_samples = (
            remaining_degradation
            / degradation_rate
        )

        raw_seconds = (
            raw_samples
            * self.sample_interval_seconds
        )

        raw_hours = (
            raw_seconds
            / 3600.0
        )

        # The simulator operates at a very high
        # demonstration sampling rate compared with
        # real maintenance/prognostic time scales.
        #
        # Therefore we do NOT expose raw_hours directly.
        #
        # Instead, scale the trajectory into a
        # configurable operating-hour-equivalent range.
        #
        # This keeps the demo numerically meaningful while
        # clearly remaining an assumption-based estimate.

        normalized_progress = (
            degradation_index
        )

        remaining_fraction = max(
            0.0,
            1.0 - normalized_progress,
        )

        estimated_hours = (
            self.minimum_rul_hours
            + (
                remaining_fraction
                * (
                    self.maximum_rul_hours
                    - self.minimum_rul_hours
                )
            )
        )

        # If degradation is clearly increasing,
        # allow the trend to reduce the estimate.
        #
        # This is intentionally conservative but still
        # bounded by the demonstration assumptions.

        trend_factor = min(
            1.0,
            degradation_rate
            / 0.02,
        )

        estimated_hours *= (
            1.0
            - 0.50 * trend_factor
        )

        # Keep the result within the configured
        # demonstration range.

        estimated_hours = max(
            self.minimum_rul_hours,
            min(
                estimated_hours,
                self.maximum_rul_hours,
            ),
        )

        return float(
            estimated_hours
        )

    @staticmethod
    def _classify_status(
        degradation_index: float,
        degradation_rate: float,
        rul_hours: float,
    ) -> str:

        if degradation_index >= 0.90:
            return "CRITICAL"

        if degradation_index >= 0.70:
            return "WARNING"

        if (
            degradation_rate > 0.005
            and degradation_index >= 0.20
        ):
            return "DEGRADING"

        return "STABLE"

    def update(
        self,
        degradation_index: float,
    ) -> RULResult:
        """
        Update the RUL estimator with the latest
        degradation index.
        """

        degradation_index = max(
            0.0,
            min(
                self.critical_degradation,
                float(
                    degradation_index
                ),
            ),
        )

        self.degradation_history.append(
            degradation_index
        )

        degradation_rate = (
            self._calculate_rate(
                self.degradation_history
            )
        )

        rul_hours = (
            self._calculate_rul_hours(
                degradation_index=(
                    degradation_index
                ),
                degradation_rate=(
                    degradation_rate
                ),
            )
        )

        # Keep the sample estimate as an internal
        # trajectory indicator rather than pretending
        # it represents actual aircraft operating hours.

        if degradation_rate > 0.000001:

            remaining_degradation = max(
                0.0,
                self.critical_degradation
                - degradation_index,
            )

            rul_samples = (
                remaining_degradation
                / degradation_rate
            )

        else:

            rul_samples = float(
                self.history_size * 10
            )

        rul_samples = max(
            0.0,
            min(
                rul_samples,
                100000.0,
            ),
        )

        confidence = (
            self._calculate_confidence()
        )

        status = (
            self._classify_status(
                degradation_index=(
                    degradation_index
                ),
                degradation_rate=(
                    degradation_rate
                ),
                rul_hours=rul_hours,
            )
        )

        return RULResult(
            rul_samples=float(
                rul_samples
            ),

            rul_hours=float(
                rul_hours
            ),

            degradation_index=float(
                degradation_index
            ),

            degradation_rate=float(
                degradation_rate
            ),

            confidence=float(
                confidence
            ),

            status=status,
        )